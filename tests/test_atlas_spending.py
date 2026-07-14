"""Testes da avaliacao de gastos do ATLAS (auto ate o limite, escala acima)."""

from conftest import TEST_ACCOUNT_ID

from app.atlas import service


def _seed(fake_db):
    fake_db.ledger.append({
        "account_id": TEST_ACCOUNT_ID,
        "gross_amount": "20.00", "product_slug": None,
        "event_type": "payment_succeeded", "status": "pending_classification",
        "currency": "usd",
    })


def test_under_limit_auto(client, auth_headers, fake_db, monkeypatch):
    _seed(fake_db)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(service, "ask_llm", lambda s, p, max_tokens=2000: "DECISAO: aprovar\nok")
    r = client.post("/atlas/spending/evaluate", headers=auth_headers,
                    json={"action": "ads meta", "estimated_cost": 30, "currency": "EUR"})
    assert r.status_code == 200
    assert r.json()["requires_founder_approval"] is False
    assert "DECISAO" in r.json()["analysis"]


def test_over_limit_escalates(client, auth_headers, fake_db, monkeypatch):
    _seed(fake_db)
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setattr(service, "ask_llm", lambda s, p, max_tokens=2000: "DECISAO: adiar")
    r = client.post("/atlas/spending/evaluate", headers=auth_headers,
                    json={"action": "anuncio grande", "estimated_cost": 200, "currency": "EUR"})
    assert r.status_code == 200
    assert r.json()["requires_founder_approval"] is True


def test_non_eur_escalates(client, auth_headers, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setattr(service, "ask_llm", lambda s, p, max_tokens=2000: "DECISAO: aprovar")
    r = client.post("/atlas/spending/evaluate", headers=auth_headers,
                    json={"action": "ferramenta", "estimated_cost": 10, "currency": "USD"})
    assert r.status_code == 200
    assert r.json()["requires_founder_approval"] is True


def test_requires_auth(client):
    r = client.post("/atlas/spending/evaluate", json={"action": "x", "estimated_cost": 5})
    assert r.status_code == 401


def test_503_without_llm(client, auth_headers, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = client.post("/atlas/spending/evaluate", headers=auth_headers,
                    json={"action": "x", "estimated_cost": 5})
    assert r.status_code == 503
