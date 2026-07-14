"""Multi-tenancy: cada cliente ve SO o proprio financeiro.

Regra de ouro: sem X-Account-Id -> 400; nunca devolver dado global.
"""

import json

import pytest

from conftest import (
    OTHER_ACCOUNT_ID,
    TEST_ACCOUNT_ID,
    TEST_CFO_API_KEY,
    stripe_signature,
)

OWNER_ACCOUNT_ID = "00000000-0000-0000-0000-000000000001"

KEY_ONLY = {"X-API-Key": TEST_CFO_API_KEY}

# Todos os endpoints de leitura multi-tenant (metodo, path, body)
TENANT_ENDPOINTS = [
    ("GET", "/reports/summary", None),
    ("GET", "/spending-requests", None),
    ("GET", "/spending-requests/req-1", None),
    ("POST", "/atlas/ask", {"question": "oi"}),
    ("GET", "/atlas/report/weekly", None),
    ("POST", "/atlas/spending/evaluate", {"action": "x", "estimated_cost": 5}),
]


def _request(client, method, path, body, headers):
    if method == "GET":
        return client.get(path, headers=headers)
    return client.post(path, json=body, headers=headers)


@pytest.mark.parametrize("method,path,body", TENANT_ENDPOINTS)
def test_missing_account_id_returns_400(client, method, path, body):
    response = _request(client, method, path, body, KEY_ONLY)

    assert response.status_code == 400, (
        f"{method} {path} sem X-Account-Id deveria ser 400, "
        f"veio {response.status_code} (risco de dado global vazando)"
    )


@pytest.mark.parametrize("method,path,body", TENANT_ENDPOINTS)
def test_invalid_account_id_returns_400(client, method, path, body):
    headers = {**KEY_ONLY, "X-Account-Id": "nao-e-um-uuid"}

    response = _request(client, method, path, body, headers)

    assert response.status_code == 400


def _ledger_entry(event_id, account_id, gross):
    return {
        "stripe_event_id": event_id,
        "account_id": account_id,
        "product_slug": "curso-x",
        "event_type": "payment_succeeded",
        "gross_amount": gross,
        "currency": "brl",
        "company_share": None,
        "pro_labore_share": None,
        "split_rule_applied": None,
        "status": "pending_classification",
        "raw_stripe_payload": {},
        "created_at": "2026-07-01T00:00:00+00:00",
    }


def _spending(id_, account_id):
    return {
        "id": id_,
        "account_id": account_id,
        "agent": "ads-bot",
        "product": "curso-x",
        "action": "buy_domain",
        "estimated_cost": "10.00",
        "currency": "brl",
        "description": None,
        "status": "pending",
        "requested_at": "2026-07-01T12:00:00+00:00",
        "decided_at": None,
        "decided_by": None,
        "decision_note": None,
    }


def test_summary_only_sees_own_account(client, fake_db, auth_headers):
    fake_db.ledger.extend(
        [
            _ledger_entry("evt_mine", TEST_ACCOUNT_ID, "100.00"),
            _ledger_entry("evt_other", OTHER_ACCOUNT_ID, "999.00"),
        ]
    )

    body = client.get("/reports/summary", headers=auth_headers).json()

    assert body["total_gross"] == "100.00"
    assert body["transaction_count"] == 1


def test_spending_requests_only_sees_own_account(client, fake_db, auth_headers):
    fake_db.spending_requests.extend(
        [_spending("req-mine", TEST_ACCOUNT_ID), _spending("req-other", OTHER_ACCOUNT_ID)]
    )

    body = client.get("/spending-requests", headers=auth_headers).json()

    assert [r["id"] for r in body] == ["req-mine"]


def test_spending_request_of_other_account_is_404(client, fake_db, auth_headers):
    """IDOR: conhecer o id do pedido de outro workspace nao pode dar acesso."""
    fake_db.spending_requests.append(_spending("req-other", OTHER_ACCOUNT_ID))

    response = client.get("/spending-requests/req-other", headers=auth_headers)

    assert response.status_code == 404


def test_webhook_tags_owner_workspace(client, fake_db):
    """Fase 1: ingestao do Stripe associa tudo ao workspace do dono."""
    event = {
        "id": "evt_tenant",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "object": "payment_intent",
                "amount_received": 1000,
                "currency": "brl",
                "metadata": {},
            }
        },
    }
    payload = json.dumps(event).encode()

    response = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": stripe_signature(payload)},
    )

    assert response.status_code == 200
    assert fake_db.ledger[0]["account_id"] == OWNER_ACCOUNT_ID


def test_webhook_account_id_overridable_by_env(client, fake_db, monkeypatch):
    monkeypatch.setenv(
        "STRIPE_DEFAULT_ACCOUNT_ID", "33333333-3333-3333-3333-333333333333"
    )
    event = {
        "id": "evt_env",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "object": "payment_intent",
                "amount_received": 1000,
                "currency": "brl",
                "metadata": {},
            }
        },
    }
    payload = json.dumps(event).encode()

    client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": stripe_signature(payload)},
    )

    assert fake_db.ledger[0]["account_id"] == "33333333-3333-3333-3333-333333333333"
