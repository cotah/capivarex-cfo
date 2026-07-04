"""GET /reports/summary: agregacao e destaque de pending_classification."""


def ledger_entry(
    event_id,
    slug,
    gross,
    company,
    pro_labore,
    status,
    created_at="2026-07-01T12:00:00+00:00",
):
    return {
        "stripe_event_id": event_id,
        "product_slug": slug,
        "event_type": "payment_succeeded",
        "gross_amount": gross,
        "currency": "brl",
        "company_share": company,
        "pro_labore_share": pro_labore,
        "split_rule_applied": None if company is None else f"{slug}:70/30",
        "status": status,
        "raw_stripe_payload": {},
        "created_at": created_at,
    }


def seed_ledger(fake_db):
    fake_db.ledger.extend(
        [
            ledger_entry("evt_1", "curso-x", "100.00", "70.00", "30.00", "classified"),
            ledger_entry("evt_2", "curso-x", "-25.00", "-17.50", "-7.50", "classified"),
            ledger_entry(
                "evt_3", "produto-novo", "50.00", None, None, "pending_classification"
            ),
        ]
    )


def test_summary_requires_api_key(client):
    response = client.get("/reports/summary")

    assert response.status_code == 401


def test_summary_aggregates_totals_and_highlights_pending(
    client, fake_db, auth_headers
):
    seed_ledger(fake_db)

    response = client.get("/reports/summary", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total_gross"] == "125.00"  # 100 - 25 + 50
    assert body["total_company_share"] == "52.50"  # 70 - 17.50
    assert body["total_pro_labore_share"] == "22.50"  # 30 - 7.50
    assert body["transaction_count"] == 3
    pending = body["pending_classification"]
    assert pending["count"] == 1
    assert pending["total_gross"] == "50.00"
    assert pending["products"] == ["produto-novo"]


def test_summary_filters_by_product_slug(client, fake_db, auth_headers):
    seed_ledger(fake_db)

    response = client.get(
        "/reports/summary", params={"product_slug": "curso-x"}, headers=auth_headers
    )

    body = response.json()
    assert body["total_gross"] == "75.00"  # 100 - 25
    assert body["transaction_count"] == 2
    assert body["pending_classification"]["count"] == 0


def test_summary_filters_by_since(client, fake_db, auth_headers):
    fake_db.ledger.extend(
        [
            ledger_entry(
                "evt_old",
                "curso-x",
                "10.00",
                "7.00",
                "3.00",
                "classified",
                created_at="2026-01-01T00:00:00+00:00",
            ),
            ledger_entry(
                "evt_new",
                "curso-x",
                "20.00",
                "14.00",
                "6.00",
                "classified",
                created_at="2026-07-02T00:00:00+00:00",
            ),
        ]
    )

    response = client.get(
        "/reports/summary", params={"since": "2026-06-01"}, headers=auth_headers
    )

    body = response.json()
    assert body["transaction_count"] == 1
    assert body["total_gross"] == "20.00"
