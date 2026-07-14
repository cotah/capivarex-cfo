"""Unica porta de acesso ao banco (Supabase — Cerebro Compartilhado).

Adaptador fino: nenhuma logica de negocio aqui, so leitura/escrita.
Nos testes, `get_db` e substituido por um fake em memoria via
`app.dependency_overrides` — nenhum teste toca o Supabase real.

A interface (metodos publicos) precisa ser identica ao FakeDB de
tests/conftest.py.
"""

from functools import lru_cache

from postgrest.exceptions import APIError
from supabase import create_client

from app.config import get_settings

LEDGER = "financial_ledger"
RULES = "product_split_rules"
SPENDING = "spending_requests"
UNIQUE_VIOLATION = "23505"


class SupabaseDB:
    def __init__(self, client):
        self._client = client

    def ping(self) -> bool:
        self._client.table(RULES).select("id").limit(1).execute()
        return True

    def upsert_split_rule(self, rule: dict) -> dict:
        result = (
            self._client.table(RULES)
            .upsert(rule, on_conflict="product_slug")
            .execute()
        )
        return result.data[0]

    def list_split_rules(self) -> list[dict]:
        """Todas as regras de split (para relatorios/ATLAS)."""
        return self._client.table(RULES).select("*").execute().data

    def get_active_split_rule(self, product_slug: str) -> dict | None:
        result = (
            self._client.table(RULES)
            .select("*")
            .eq("product_slug", product_slug)
            .eq("active", True)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def get_ledger_entry(self, stripe_event_id: str) -> dict | None:
        # Uso interno da ingestao (idempotencia). stripe_event_id e unico
        # globalmente no Stripe; nao passa por endpoint de cliente.
        result = (
            self._client.table(LEDGER)
            .select("*")
            .eq("stripe_event_id", stripe_event_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None

    def insert_ledger_entry(self, entry: dict) -> dict:
        try:
            result = self._client.table(LEDGER).insert(entry).execute()
            return result.data[0]
        except APIError as exc:
            # Corrida rara: dois webhooks simultaneos do mesmo evento.
            # O UNIQUE(stripe_event_id) do banco segura; devolvemos o existente.
            if exc.code == UNIQUE_VIOLATION:
                existing = self.get_ledger_entry(entry["stripe_event_id"])
                if existing is not None:
                    return existing
            raise

    def list_refund_entries_for_charge(self, charge_id: str) -> list[dict]:
        """Reembolsos ja registrados para uma charge (S1: amount_refunded do
        Stripe e acumulado; precisamos do que ja contabilizamos)."""
        result = (
            self._client.table(LEDGER)
            .select("gross_amount")
            .eq("event_type", "refund")
            .eq("raw_stripe_payload->data->object->>id", charge_id)
            .execute()
        )
        return result.data

    def list_ledger_entries(
        self,
        account_id: str,
        product_slug: str | None = None,
        since: str | None = None,
    ) -> list[dict]:
        """Multi-tenant: account_id e obrigatorio — nunca ha leitura global."""
        query = self._client.table(LEDGER).select("*").eq("account_id", account_id)
        if product_slug is not None:
            query = query.eq("product_slug", product_slug)
        if since is not None:
            query = query.gte("created_at", since)
        return query.execute().data

    def list_spending_requests(
        self, account_id: str, status: str | None = None
    ) -> list[dict]:
        """Pedidos de gasto criados via n8n. Somente leitura — a decisao
        (aprovar/rejeitar) acontece no n8n, nunca aqui."""
        query = self._client.table(SPENDING).select("*").eq("account_id", account_id)
        if status is not None:
            query = query.eq("status", status)
        return query.order("requested_at", desc=True).execute().data

    def get_spending_request(self, account_id: str, request_id: str) -> dict | None:
        """Filtra por account_id tambem: id de outro workspace -> None (404),
        nunca o dado do vizinho."""
        result = (
            self._client.table(SPENDING)
            .select("*")
            .eq("account_id", account_id)
            .eq("id", request_id)
            .limit(1)
            .execute()
        )
        return result.data[0] if result.data else None


@lru_cache
def _default_db() -> SupabaseDB:
    settings = get_settings()
    return SupabaseDB(
        create_client(settings.supabase_url, settings.supabase_service_key)
    )


def get_db():
    """Dependency do FastAPI — cria o cliente Supabase na primeira chamada."""
    return _default_db()
