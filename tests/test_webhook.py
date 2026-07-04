"""POST /webhooks/stripe: verificacao de assinatura e processamento de eventos."""

import json
import time

from conftest import stripe_signature

APPROVED_RULE = {
    "product_slug": "curso-x",
    "company_pct": "70",
    "pro_labore_pct": "30",
    "approved_by": "Henrique",
    "rationale": None,
    "active": True,
}


def make_payment_event(event_id="evt_1", amount_cents=10000, slug="curso-x"):
    metadata = {"product_slug": slug} if slug else {}
    return {
        "id": event_id,
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "object": "payment_intent",
                "amount_received": amount_cents,
                "currency": "brl",
                "metadata": metadata,
            }
        },
    }


def post_event(client, event: dict):
    payload = json.dumps(event).encode()
    return client.post(
        "/webhooks/stripe",
        content=payload,
        headers={
            "Stripe-Signature": stripe_signature(payload),
            "Content-Type": "application/json",
        },
    )


def test_webhook_rejects_missing_signature(client, fake_db):
    response = client.post("/webhooks/stripe", content=b"{}")

    assert response.status_code == 401
    assert fake_db.ledger == []


def test_webhook_rejects_invalid_signature(client, fake_db):
    response = client.post(
        "/webhooks/stripe",
        content=b"{}",
        headers={"Stripe-Signature": "t=1234567890,v1=assinatura-falsa"},
    )

    assert response.status_code == 401
    assert fake_db.ledger == []


def test_payment_with_approved_rule_is_classified(client, fake_db):
    fake_db.split_rules.append(dict(APPROVED_RULE))

    response = post_event(client, make_payment_event(amount_cents=10000))

    assert response.status_code == 200
    assert len(fake_db.ledger) == 1
    entry = fake_db.ledger[0]
    assert entry["stripe_event_id"] == "evt_1"
    assert entry["event_type"] == "payment_succeeded"
    assert entry["product_slug"] == "curso-x"
    assert entry["gross_amount"] == "100.00"
    assert entry["currency"] == "brl"
    assert entry["company_share"] == "70.00"
    assert entry["pro_labore_share"] == "30.00"
    assert entry["split_rule_applied"] == "curso-x:70/30"
    assert entry["status"] == "classified"
    assert entry["raw_stripe_payload"]["id"] == "evt_1"


def test_refund_is_recorded_with_negative_amounts(client, fake_db):
    fake_db.split_rules.append(dict(APPROVED_RULE))
    refund_event = {
        "id": "evt_refund_1",
        "type": "charge.refunded",
        "data": {
            "object": {
                "object": "charge",
                "amount_refunded": 2500,
                "currency": "brl",
                "metadata": {"product_slug": "curso-x"},
            }
        },
    }

    response = post_event(client, refund_event)

    assert response.status_code == 200
    entry = fake_db.ledger[0]
    assert entry["event_type"] == "refund"
    assert entry["gross_amount"] == "-25.00"
    assert entry["company_share"] == "-17.50"
    assert entry["pro_labore_share"] == "-7.50"
    assert entry["status"] == "classified"


def test_product_without_rule_becomes_pending_classification(client, fake_db):
    # Nenhuma regra cadastrada para "produto-novo"
    event = make_payment_event(slug="produto-novo")

    response = post_event(client, event)

    assert response.status_code == 200  # nao quebra: falha visivel, nao erro
    entry = fake_db.ledger[0]
    assert entry["status"] == "pending_classification"
    assert entry["product_slug"] == "produto-novo"
    assert entry["company_share"] is None
    assert entry["pro_labore_share"] is None
    assert entry["split_rule_applied"] is None
    assert entry["gross_amount"] == "100.00"  # o valor bruto e registrado


def test_event_without_product_metadata_becomes_pending(client, fake_db):
    fake_db.split_rules.append(dict(APPROVED_RULE))
    event = make_payment_event(slug=None)  # sem metadata product_slug

    response = post_event(client, event)

    assert response.status_code == 200
    entry = fake_db.ledger[0]
    assert entry["product_slug"] is None
    assert entry["status"] == "pending_classification"


def test_unknown_event_type_is_ignored(client, fake_db):
    event = {
        "id": "evt_x",
        "type": "product.created",
        "data": {"object": {"object": "product"}},
    }

    response = post_event(client, event)

    assert response.status_code == 200
    assert response.json()["ignored"] is True
    assert fake_db.ledger == []


def test_same_event_twice_does_not_duplicate(client, fake_db):
    fake_db.split_rules.append(dict(APPROVED_RULE))
    event = make_payment_event(event_id="evt_dup")

    first = post_event(client, event)
    second = post_event(client, event)

    assert first.status_code == 200
    assert second.status_code == 200  # retorna 200 sem reprocessar
    assert len(fake_db.ledger) == 1


def test_webhook_rejects_expired_timestamp(client, fake_db):
    payload = b"{}"
    old_timestamp = int(time.time()) - 3600  # 1 hora atras
    signature = stripe_signature(payload, timestamp=old_timestamp)

    response = client.post(
        "/webhooks/stripe",
        content=payload,
        headers={"Stripe-Signature": signature},
    )

    assert response.status_code == 401
    assert fake_db.ledger == []
