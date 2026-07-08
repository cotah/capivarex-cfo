"""Testes do ATLAS (CFO de IA) — LLM sempre mockada (sem custo/rede)."""

from app.atlas import context, service


def _seed(fake_db):
    fake_db.ledger.append({
        "gross_amount": "20.00", "product_slug": None,
        "event_type": "payment_succeeded", "status": "pending_classification",
        "currency": "usd",
    })
    fake_db.split_rules.append({
        "product_slug": "curso-x", "company_pct": 70,
        "pro_labore_pct": 30, "active": True,
    })
    fake_db.spending_requests.append({
        "id": "1", "agent": "ads", "product": "curso-x", "action": "meta ads",
        "estimated_cost": "300", "currency": "EUR", "status": "pending",
        "requested_at": "2026-07-01T00:00:00Z",
    })


def test_context_builder_has_sections(fake_db):
    _seed(fake_db)
    ctx = context.build_financial_context(fake_db)
    assert "Receita" in ctx
    assert "pending_classification" in ctx
    assert "curso-x" in ctx
    assert "NAO disponiveis" in ctx  # declara o que falta (nao inventa)


def test_atlas_ask_requires_auth(client):
    resp = client.post("/atlas/ask", json={"question": "oi"})  # sem X-API-Key
    assert resp.status_code == 401


def test_atlas_ask_503_without_llm(client, auth_headers, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    resp = client.post("/atlas/ask", json={"question": "invisto em ads?"}, headers=auth_headers)
    assert resp.status_code == 503


def test_atlas_ask_200_with_mocked_llm(client, auth_headers, fake_db, monkeypatch):
    _seed(fake_db)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(
        service, "ask_llm",
        lambda system, prompt, max_tokens=2000: "RESPOSTA DO ATLAS",
    )
    resp = client.post(
        "/atlas/ask", json={"question": "invisto 300 em ads?"}, headers=auth_headers
    )
    assert resp.status_code == 200
    assert resp.json()["answer"] == "RESPOSTA DO ATLAS"


def test_atlas_weekly_200_with_mocked_llm(client, auth_headers, fake_db, monkeypatch):
    _seed(fake_db)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(
        service, "ask_llm",
        lambda system, prompt, max_tokens=2000: "RELATORIO SEMANAL",
    )
    resp = client.get("/atlas/report/weekly", headers=auth_headers)
    assert resp.status_code == 200
    assert "RELATORIO" in resp.json()["report"]
