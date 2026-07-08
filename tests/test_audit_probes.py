"""Testes de regressao da auditoria de 2026-07 (issues S1..S7).

Cada teste afirma o comportamento correto que foi quebrado (e corrigido) ou
confirmado na auditoria. Sao permanentes: se algum quebrar, uma correcao
da auditoria regrediu.
"""

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.db import get_db
from app.main import create_app
from conftest import stripe_signature

APPROVED_RULE = {
    "product_slug": "curso-x",
    "company_pct": "70",
    "pro_labore_pct": "30",
    "approved_by": "Henrique",
    "rationale": None,
    "active": True,
}


@pytest.fixture
def raw_client(fake_db):
    """Client que NAO explode em erro 500 — deixa a gente observar o status
    real que o Stripe receberia."""
    app = create_app()
    app.dependency_overrides[get_db] = lambda: fake_db
    return TestClient(app, raise_server_exceptions=False)


def post_signed(client, body: bytes):
    return client.post(
        "/webhooks/stripe",
        content=body,
        headers={
            "Stripe-Signature": stripe_signature(body),
            "Content-Type": "application/json",
        },
    )


def post_event(client, event: dict):
    return post_signed(client, json.dumps(event).encode())


def refund_event(event_id, amount_refunded_cents, charge_id="ch_1"):
    """Evento charge.refunded como o Stripe manda de verdade:
    amount_refunded e o TOTAL ACUMULADO reembolsado na charge."""
    return {
        "id": event_id,
        "type": "charge.refunded",
        "data": {
            "object": {
                "object": "charge",
                "id": charge_id,
                "amount_refunded": amount_refunded_cents,
                "currency": "brl",
                "metadata": {"product_slug": "curso-x"},
            }
        },
    }


# ---------------------------------------------------------------------------
# S1 — reembolso parcial multiplo (amount_refunded e CUMULATIVO no Stripe)
# ---------------------------------------------------------------------------


def test_s1_two_partial_refunds_record_only_the_actual_refunded_total(
    raw_client, fake_db
):
    """Charge de R$100; reembolso de R$25, depois MAIS R$25.
    Stripe manda: evento 1 amount_refunded=2500, evento 2 amount_refunded=5000.
    O ledger deve somar -50.00 (real), nao -75.00 (dobrado)."""
    fake_db.split_rules.append(dict(APPROVED_RULE))

    r1 = post_event(raw_client, refund_event("evt_r1", 2500))
    r2 = post_event(raw_client, refund_event("evt_r2", 5000))

    assert r1.status_code == 200
    assert r2.status_code == 200
    total = sum(float(e["gross_amount"]) for e in fake_db.ledger)
    assert total == -50.00, (
        f"ledger somou {total} — reembolso contado em dobro (S1 confirmado)"
    )


# ---------------------------------------------------------------------------
# S2 — payload assinado mas com corpo hostil nao pode virar 500
# ---------------------------------------------------------------------------


def test_s2_signed_but_invalid_json_returns_400_not_500(raw_client, fake_db):
    response = post_signed(raw_client, b"nao-e-json{{{")

    assert response.status_code == 400, (
        f"retornou {response.status_code} — 500 faz o Stripe reenviar para sempre"
    )
    assert fake_db.ledger == []


def test_s2_signed_json_array_returns_400_not_500(raw_client, fake_db):
    response = post_signed(raw_client, b"[1, 2, 3]")

    assert response.status_code == 400
    assert fake_db.ledger == []


def test_s2_signed_event_missing_data_object_returns_400_not_500(
    raw_client, fake_db
):
    event = {"id": "evt_broken", "type": "payment_intent.succeeded"}

    response = post_event(raw_client, event)

    assert response.status_code == 400
    assert fake_db.ledger == []


def test_s2_signed_event_missing_id_returns_400_not_500(raw_client, fake_db):
    event = {
        "type": "payment_intent.succeeded",
        "data": {"object": {"amount_received": 100, "metadata": {}}},
    }

    response = post_event(raw_client, event)

    assert response.status_code == 400
    assert fake_db.ledger == []


# ---------------------------------------------------------------------------
# S3 — relatorio nao pode misturar moedas num total unico
# ---------------------------------------------------------------------------


def _entry(event_id, currency, gross):
    return {
        "stripe_event_id": event_id,
        "product_slug": "curso-x",
        "event_type": "payment_succeeded",
        "gross_amount": gross,
        "currency": currency,
        "company_share": None,
        "pro_labore_share": None,
        "split_rule_applied": None,
        "status": "pending_classification",
        "raw_stripe_payload": {},
        "created_at": "2026-07-01T00:00:00+00:00",
    }


def test_s3_summary_separates_currencies(client, fake_db, auth_headers):
    fake_db.ledger.extend(
        [_entry("evt_brl", "brl", "100.00"), _entry("evt_usd", "usd", "100.00")]
    )

    body = client.get("/reports/summary", headers=auth_headers).json()

    # R$100 + US$100 nao sao "200.00" de coisa nenhuma.
    assert "by_currency" in body, (
        "summary mistura moedas num total unico (S3 confirmado)"
    )


# ---------------------------------------------------------------------------
# S4 — rotacao de secret: header com dois v1 (pratica oficial do Stripe)
# ---------------------------------------------------------------------------


def test_s4_accepts_header_with_two_v1_when_one_matches(raw_client, fake_db):
    payload = json.dumps(
        {
            "id": "evt_rot",
            "type": "product.created",
            "data": {"object": {"object": "product"}},
        }
    ).encode()
    ts = int(time.time())
    valid = stripe_signature(payload, timestamp=ts)  # "t=..,v1=<valida>"
    # Stripe na rotacao: assinatura valida primeiro, do secret antigo depois
    header = f"{valid},v1={'0' * 64}"

    response = raw_client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": header},
    )

    assert response.status_code == 200, (
        "assinatura valida rejeitada quando ha segundo v1 (S4 confirmado)"
    )


# ---------------------------------------------------------------------------
# S5 — parametro `since` com lixo deve ser rejeitado com 422 (nao 500 no banco)
# ---------------------------------------------------------------------------


def test_s5_summary_rejects_garbage_since(client, auth_headers):
    response = client.get(
        "/reports/summary", params={"since": "banana"}, headers=auth_headers
    )

    assert response.status_code == 422, (
        f"retornou {response.status_code} — 'since' invalido vai direto ao "
        "PostgREST e viraria 500 em producao (S5 confirmado)"
    )


def test_s5_summary_accepts_iso_date(client, auth_headers):
    response = client.get(
        "/reports/summary", params={"since": "2026-06-01"}, headers=auth_headers
    )

    assert response.status_code == 200


# ---------------------------------------------------------------------------
# S7 — amount_received=0 explicito nao pode cair no fallback `amount`
# ---------------------------------------------------------------------------


def test_s7_zero_amount_received_records_zero_not_amount(raw_client, fake_db):
    fake_db.split_rules.append(dict(APPROVED_RULE))
    event = {
        "id": "evt_zero",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "object": "payment_intent",
                "amount_received": 0,  # nada recebido ainda
                "amount": 5000,  # valor da intencao, NAO recebido
                "currency": "brl",
                "metadata": {"product_slug": "curso-x"},
            }
        },
    }

    response = post_event(raw_client, event)

    assert response.status_code == 200
    assert fake_db.ledger[0]["gross_amount"] == "0.00", (
        f"registrou {fake_db.ledger[0]['gross_amount']} — dinheiro nao recebido "
        "entrou no ledger (S7 confirmado)"
    )


# ---------------------------------------------------------------------------
# Sondas de confirmacao (esperado: PASSAR — comportamento ja correto)
# ---------------------------------------------------------------------------


def test_ok_rounding_odd_cents_shares_always_sum_to_gross(raw_client, fake_db):
    """R$0,03 com split 70/30: 0.021 -> 0.02 + 0.01 = 0.03. Nenhum centavo some."""
    fake_db.split_rules.append(dict(APPROVED_RULE))
    event = {
        "id": "evt_3c",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "amount_received": 3,
                "currency": "brl",
                "metadata": {"product_slug": "curso-x"},
            }
        },
    }

    post_event(raw_client, event)

    entry = fake_db.ledger[0]
    assert entry["company_share"] == "0.02"
    assert entry["pro_labore_share"] == "0.01"
    assert float(entry["company_share"]) + float(entry["pro_labore_share"]) == 0.03


def test_ok_invoice_paid_finds_slug_in_line_items(raw_client, fake_db):
    fake_db.split_rules.append(dict(APPROVED_RULE))
    event = {
        "id": "evt_inv",
        "type": "invoice.paid",
        "data": {
            "object": {
                "object": "invoice",
                "amount_paid": 9900,
                "currency": "brl",
                "metadata": {},
                "lines": {
                    "data": [{"metadata": {"product_slug": "curso-x"}}]
                },
            }
        },
    }

    post_event(raw_client, event)

    entry = fake_db.ledger[0]
    assert entry["product_slug"] == "curso-x"
    assert entry["status"] == "classified"
    assert entry["gross_amount"] == "99.00"


def test_ok_future_timestamp_rejected(raw_client, fake_db):
    payload = b"{}"
    future = int(time.time()) + 3600
    response = raw_client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": stripe_signature(payload, timestamp=future)},
    )

    assert response.status_code == 401
    assert fake_db.ledger == []


def test_ok_malformed_signature_headers_rejected(raw_client, fake_db):
    for header in ["", "t=abc,v1=def", "v1=soz1nho", "t=123", "lixo-total"]:
        response = raw_client.post(
            "/webhooks/stripe", content=b"{}", headers={"Stripe-Signature": header}
        )
        assert response.status_code == 401, f"header {header!r} nao foi rejeitado"
    assert fake_db.ledger == []


def test_ok_empty_api_key_rejected(client):
    response = client.get("/reports/summary", headers={"X-API-Key": ""})

    assert response.status_code == 401


def test_ok_split_rule_fractional_pcts_must_sum_exactly_100(
    client, fake_db, auth_headers
):
    ok = {
        "product_slug": "p1",
        "company_pct": "33.33",
        "pro_labore_pct": "66.67",
    }
    bad = {
        "product_slug": "p2",
        "company_pct": "33.30",
        "pro_labore_pct": "66.60",
    }

    assert client.post("/split-rules", json=ok, headers=auth_headers).status_code == 200
    assert (
        client.post("/split-rules", json=bad, headers=auth_headers).status_code == 422
    )
    assert len(fake_db.split_rules) == 1


def test_ok_empty_slug_in_metadata_becomes_pending(raw_client, fake_db):
    fake_db.split_rules.append(dict(APPROVED_RULE))
    event = {
        "id": "evt_empty_slug",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "amount_received": 1000,
                "currency": "brl",
                "metadata": {"product_slug": ""},
            }
        },
    }

    post_event(raw_client, event)

    entry = fake_db.ledger[0]
    assert entry["product_slug"] is None
    assert entry["status"] == "pending_classification"
