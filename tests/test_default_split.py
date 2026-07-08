"""Testes do split PADRAO (fallback global 75/25) — configuravel por env."""

from app.services import ledger


def _event(eid, amount=2000, slug=None):
    obj = {"id": "pi_x", "amount_received": amount, "currency": "usd"}
    if slug:
        obj["metadata"] = {"product_slug": slug}
    return {"id": eid, "type": "payment_intent.succeeded", "data": {"object": obj}}


def test_default_split_applied_when_configured(fake_db, monkeypatch):
    monkeypatch.setenv("DEFAULT_SPLIT_COMPANY_PCT", "75")
    monkeypatch.setenv("DEFAULT_SPLIT_PRO_LABORE_PCT", "25")
    entry = ledger.process_event(fake_db, _event("evt_def_1"))
    assert entry["status"] == "classified"
    assert entry["company_share"] == "15.00"      # 75% de 20
    assert entry["pro_labore_share"] == "5.00"    # 25% de 20 (fecha 100%)
    assert entry["split_rule_applied"] == "default:75/25"


def test_pending_when_default_not_configured(fake_db, monkeypatch):
    monkeypatch.delenv("DEFAULT_SPLIT_COMPANY_PCT", raising=False)
    monkeypatch.delenv("DEFAULT_SPLIT_PRO_LABORE_PCT", raising=False)
    entry = ledger.process_event(fake_db, _event("evt_def_2"))
    assert entry["status"] == "pending_classification"
    assert entry["company_share"] is None


def test_invalid_default_sum_falls_back_to_pending(fake_db, monkeypatch):
    monkeypatch.setenv("DEFAULT_SPLIT_COMPANY_PCT", "70")
    monkeypatch.setenv("DEFAULT_SPLIT_PRO_LABORE_PCT", "25")  # soma 95 != 100
    entry = ledger.process_event(fake_db, _event("evt_def_3"))
    assert entry["status"] == "pending_classification"


def test_product_rule_overrides_default(fake_db, monkeypatch):
    monkeypatch.setenv("DEFAULT_SPLIT_COMPANY_PCT", "75")
    monkeypatch.setenv("DEFAULT_SPLIT_PRO_LABORE_PCT", "25")
    fake_db.split_rules.append(
        {"product_slug": "curso-x", "company_pct": 70, "pro_labore_pct": 30, "active": True}
    )
    entry = ledger.process_event(fake_db, _event("evt_def_4", slug="curso-x"))
    assert entry["status"] == "classified"
    assert entry["split_rule_applied"] == "curso-x:70/30"
    assert entry["company_share"] == "14.00"  # 70% de 20
