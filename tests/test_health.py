"""GET /health: servico de pe e banco acessivel, sem autenticacao."""


def test_health_returns_ok_and_database_connected(client):
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"
