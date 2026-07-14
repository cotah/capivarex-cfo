"""GET /spending-requests: leitura dos pedidos de gasto criados via n8n.

Somente leitura de proposito — aprovar/rejeitar acontece no n8n,
o CFO so expoe a visao.
"""

from conftest import TEST_ACCOUNT_ID


def spending_request(
    id_,
    agent,
    product,
    status,
    estimated_cost="10.00",
    requested_at="2026-07-01T12:00:00+00:00",
):
    return {
        "id": id_,
        "account_id": TEST_ACCOUNT_ID,
        "agent": agent,
        "product": product,
        "action": "buy_domain",
        "estimated_cost": estimated_cost,
        "currency": "brl",
        "description": f"{agent} quer {estimated_cost} para {product}",
        "status": status,
        "requested_at": requested_at,
        "decided_at": None,
        "decided_by": None,
        "decision_note": None,
    }


def seed_requests(fake_db):
    fake_db.spending_requests.extend(
        [
            spending_request("req-1", "marketing-bot", "curso-x", "pending"),
            spending_request(
                "req-2",
                "ads-bot",
                "produto-novo",
                "approved",
                requested_at="2026-07-02T12:00:00+00:00",
            ),
            spending_request(
                "req-3",
                "marketing-bot",
                "curso-x",
                "rejected",
                requested_at="2026-07-03T12:00:00+00:00",
            ),
        ]
    )


def test_list_requires_api_key(client):
    response = client.get("/spending-requests")

    assert response.status_code == 401


def test_detail_requires_api_key(client):
    response = client.get("/spending-requests/req-1")

    assert response.status_code == 401


def test_list_returns_all_newest_first(client, fake_db, auth_headers):
    seed_requests(fake_db)

    response = client.get("/spending-requests", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert [r["id"] for r in body] == ["req-3", "req-2", "req-1"]


def test_list_filters_by_status(client, fake_db, auth_headers):
    seed_requests(fake_db)

    response = client.get(
        "/spending-requests", params={"status": "pending"}, headers=auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert [r["id"] for r in body] == ["req-1"]
    assert body[0]["status"] == "pending"


def test_list_empty_when_no_requests(client, auth_headers):
    response = client.get("/spending-requests", headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == []


def test_detail_returns_request(client, fake_db, auth_headers):
    seed_requests(fake_db)

    response = client.get("/spending-requests/req-2", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "req-2"
    assert body["agent"] == "ads-bot"
    assert body["status"] == "approved"


def test_detail_unknown_id_returns_404(client, fake_db, auth_headers):
    seed_requests(fake_db)

    response = client.get("/spending-requests/req-999", headers=auth_headers)

    assert response.status_code == 404


def test_summary_includes_pending_spending_requests_count(
    client, fake_db, auth_headers
):
    seed_requests(fake_db)
    fake_db.spending_requests.append(
        spending_request("req-4", "ads-bot", "curso-x", "pending")
    )

    response = client.get("/reports/summary", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["pending_spending_requests"] == 2


def test_summary_pending_spending_requests_zero_when_empty(
    client, auth_headers
):
    response = client.get("/reports/summary", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["pending_spending_requests"] == 0
