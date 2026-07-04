"""Fixtures compartilhadas: app de teste com banco fake em memoria."""

import hashlib
import hmac
import time

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import get_db
from app.main import create_app

TEST_CFO_API_KEY = "test-cfo-key"
TEST_WEBHOOK_SECRET = "whsec_test_secret"


def stripe_signature(payload: bytes, timestamp: int | None = None) -> str:
    """Gera um header Stripe-Signature valido para o secret de teste."""
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"{ts}.".encode() + payload
    v1 = hmac.new(
        TEST_WEBHOOK_SECRET.encode(), signed_payload, hashlib.sha256
    ).hexdigest()
    return f"t={ts},v1={v1}"


@pytest.fixture(autouse=True)
def test_env(monkeypatch):
    """Env vars falsas para os testes — nunca valores reais."""
    monkeypatch.setenv("SUPABASE_URL", "http://supabase.test.local")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-service-key")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    monkeypatch.setenv("CFO_API_KEY", TEST_CFO_API_KEY)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class FakeDB:
    """Substituto em memoria do Supabase para os testes.

    Espelha a interface real de app.db — qualquer metodo novo aqui
    precisa existir tambem na implementacao Supabase.
    """

    def __init__(self):
        self.ledger = []
        self.split_rules = []

    def ping(self) -> bool:
        return True

    def upsert_split_rule(self, rule: dict) -> dict:
        for i, existing in enumerate(self.split_rules):
            if existing["product_slug"] == rule["product_slug"]:
                self.split_rules[i] = rule
                return rule
        self.split_rules.append(rule)
        return rule

    def get_active_split_rule(self, product_slug: str) -> dict | None:
        for rule in self.split_rules:
            if rule["product_slug"] == product_slug and rule.get("active"):
                return rule
        return None

    def get_ledger_entry(self, stripe_event_id: str) -> dict | None:
        for entry in self.ledger:
            if entry["stripe_event_id"] == stripe_event_id:
                return entry
        return None

    def insert_ledger_entry(self, entry: dict) -> dict:
        self.ledger.append(entry)
        return entry

    def list_ledger_entries(
        self, product_slug: str | None = None, since: str | None = None
    ) -> list[dict]:
        entries = self.ledger
        if product_slug is not None:
            entries = [e for e in entries if e["product_slug"] == product_slug]
        if since is not None:
            entries = [e for e in entries if e.get("created_at", "") >= since]
        return list(entries)


@pytest.fixture
def fake_db():
    return FakeDB()


@pytest.fixture
def auth_headers():
    return {"X-API-Key": TEST_CFO_API_KEY}


@pytest.fixture
def client(fake_db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: fake_db
    return TestClient(app)
