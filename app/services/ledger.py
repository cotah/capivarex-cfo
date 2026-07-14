"""Classificacao de eventos Stripe e registro no livro-razao.

Regras:
- So le o evento recebido; nunca chama a API do Stripe.
- Produto sem regra aprovada -> status pending_classification, shares nulos.
  NUNCA aplicamos uma porcentagem default por conta propria.
- Reembolso e gravado com gross_amount negativo (soma natural nos reports).
- Aritmetica sempre com Decimal; pro_labore_share = gross - company_share
  para garantir que as partes fecham com o total (sem perder centavo).
"""

import os
from decimal import ROUND_HALF_UP, Decimal

# Evento Stripe -> event_type do ledger. Eventos fora deste mapa sao ignorados.
EVENT_TYPE_MAP = {
    "payment_intent.succeeded": "payment_succeeded",
    "charge.refunded": "refund",
    "customer.subscription.created": "subscription_created",
    "customer.subscription.deleted": "subscription_cancelled",
    "invoice.paid": "invoice_paid",
    "invoice.payment_failed": "invoice_failed",
}

TWO_PLACES = Decimal("0.01")

# Workspace do dono (Henrique). Enquanto so existe o Stripe do dono, TODA
# venda/assinatura ingerida e associada a este workspace — a associacao real
# por cliente entra na Fase 2 (cobranca). Trocavel por env sem deploy.
OWNER_ACCOUNT_ID = "00000000-0000-0000-0000-000000000001"


def _ingestion_account_id() -> str:
    return os.environ.get("STRIPE_DEFAULT_ACCOUNT_ID") or OWNER_ACCOUNT_ID


def _default_split_rule() -> dict | None:
    """Split PADRAO (fallback) aplicado quando nao ha regra especifica do produto.

    Desligado por padrao (respeita 'nunca aplicar default sozinho'): so liga
    quando DEFAULT_SPLIT_COMPANY_PCT e DEFAULT_SPLIT_PRO_LABORE_PCT estao
    setados no ambiente e somam exatamente 100 (ex.: 75 e 25). Config invalida
    => ignora (fail-safe: volta a pending_classification)."""
    company_raw = os.environ.get("DEFAULT_SPLIT_COMPANY_PCT")
    prolabore_raw = os.environ.get("DEFAULT_SPLIT_PRO_LABORE_PCT")
    if not company_raw or not prolabore_raw:
        return None
    try:
        company = Decimal(company_raw)
        prolabore = Decimal(prolabore_raw)
    except Exception:  # noqa: BLE001
        return None
    if company < 0 or prolabore < 0 or company + prolabore != Decimal("100"):
        return None
    return {
        "company_pct": company,
        "pro_labore_pct": prolabore,
        "label": f"default:{company_raw}/{prolabore_raw}",
    }


def process_event(db, event: dict) -> dict | None:
    """Processa um evento Stripe ja autenticado. Retorna a entrada gravada,
    ou None se o tipo de evento nao interessa ao ledger."""
    event_type = EVENT_TYPE_MAP.get(event.get("type", ""))
    if event_type is None:
        return None

    # Idempotencia: Stripe reenvia eventos; o mesmo id nunca gera duas entradas
    existing = db.get_ledger_entry(event["id"])
    if existing is not None:
        return existing

    stripe_object = event["data"]["object"]
    product_slug = _extract_product_slug(stripe_object)
    if event_type == "refund":
        gross_amount = _refund_delta(db, stripe_object)
    else:
        gross_amount = _extract_gross_amount(event_type, stripe_object)

    rule = db.get_active_split_rule(product_slug) if product_slug else None
    default_rule = _default_split_rule() if rule is None else None
    if rule is not None:
        company_pct = Decimal(str(rule["company_pct"]))
        company_share = (gross_amount * company_pct / 100).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        pro_labore_share = gross_amount - company_share
        split_rule_applied = (
            f"{rule['product_slug']}:{rule['company_pct']}/{rule['pro_labore_pct']}"
        )
        status = "classified"
    elif default_rule is not None:
        # Sem regra do produto: aplica o split padrao global (ex.: 75/25).
        company_pct = default_rule["company_pct"]
        company_share = (gross_amount * company_pct / 100).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        pro_labore_share = gross_amount - company_share
        split_rule_applied = default_rule["label"]
        status = "classified"
    else:
        company_share = None
        pro_labore_share = None
        split_rule_applied = None
        status = "pending_classification"

    entry = {
        "stripe_event_id": event["id"],
        # FASE 1: tudo vai para o workspace do dono (ver _ingestion_account_id)
        "account_id": _ingestion_account_id(),
        "product_slug": product_slug,
        "event_type": event_type,
        "gross_amount": str(gross_amount),
        "currency": stripe_object.get("currency"),
        "company_share": None if company_share is None else str(company_share),
        "pro_labore_share": (
            None if pro_labore_share is None else str(pro_labore_share)
        ),
        "split_rule_applied": split_rule_applied,
        "status": status,
        "raw_stripe_payload": event,
    }
    return db.insert_ledger_entry(entry)


def _extract_product_slug(stripe_object: dict) -> str | None:
    """Procura product_slug na metadata do objeto; se nao achar, None
    (vai virar pending_classification — nunca chutamos o produto)."""
    slug = stripe_object.get("metadata", {}).get("product_slug")
    if slug:
        return slug
    # Invoices/subscriptions carregam a metadata nos line items
    lines = stripe_object.get("lines", {}).get("data", [])
    for line in lines:
        slug = line.get("metadata", {}).get("product_slug")
        if slug:
            return slug
    return None


def _refund_delta(db, stripe_object: dict) -> Decimal:
    """charge.refunded traz amount_refunded ACUMULADO da charge (nao o valor
    deste reembolso). O delta real = acumulado - o que ja registramos de
    reembolso para a mesma charge no ledger. Sem isso, 2 reembolsos parciais
    de R$25 registrariam -25 e -50 (total -75, real -50)."""
    cumulative = (Decimal(stripe_object.get("amount_refunded", 0)) / 100).quantize(
        TWO_PLACES
    )
    charge_id = stripe_object.get("id")
    if not charge_id:
        return -cumulative  # sem id da charge nao ha como calcular delta

    already_refunded = sum(
        (-Decimal(e["gross_amount"]) for e in db.list_refund_entries_for_charge(charge_id)),
        Decimal("0"),
    )
    delta = cumulative - already_refunded
    if delta < 0:
        delta = Decimal("0")  # replay fora de ordem: nunca "des-reembolsa"
    return -delta.quantize(TWO_PLACES)


def _extract_gross_amount(event_type: str, stripe_object: dict) -> Decimal:
    """Stripe manda centavos (int); convertemos para Decimal com 2 casas.

    Reembolsos NAO passam por aqui: process_event roteia event_type=="refund"
    para _refund_delta (que calcula o delta acumulado). Por isso esta funcao
    trata apenas os eventos de credito/neutros.
    """
    if event_type == "payment_succeeded":
        # S7: 0 explicito e valor real (nada recebido) — so cai no fallback
        # `amount` quando amount_received esta AUSENTE.
        cents = stripe_object.get("amount_received")
        if cents is None:
            cents = stripe_object.get("amount", 0)
    elif event_type == "invoice_paid":
        cents = stripe_object.get("amount_paid", 0)
    else:
        # subscription_created/cancelled e invoice_failed nao movem dinheiro
        cents = 0
    return (Decimal(cents) / 100).quantize(TWO_PLACES)
