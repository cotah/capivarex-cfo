"""Testes da inicializacao do Sentry (observabilidade) do CFO."""

from app import observability


def test_sentry_noop_without_dsn(monkeypatch):
    monkeypatch.delenv("SENTRY_DSN", raising=False)
    monkeypatch.setattr(observability, "_initialized", False)
    assert observability.init_sentry() is False


def test_sentry_enabled_with_dsn(monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        observability.sentry_sdk, "init", lambda **k: captured.update(k)
    )
    monkeypatch.setenv(
        "SENTRY_DSN", "https://examplePublicKey@o0.ingest.sentry.io/0"
    )
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setattr(observability, "_initialized", False)

    assert observability.init_sentry() is True
    assert captured["dsn"].startswith("https://")
    assert captured["environment"] == "test"
    assert captured["send_default_pii"] is False
