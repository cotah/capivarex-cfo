"""Classificacao de eventos Stripe e registro no livro-razao.

Regras:
- So le o evento recebido; nunca chama a API do Stripe.
- Produto sem regra aprovada -> status pending_classification, shares nulos.
  NUNCA aplicamos uma porcentagem default por conta propria.
- Reembolso e gravado com gross_amount negativo (soma natural nos reports).
- Aritmetica sempre com Decimal; pro_labore_share = gross - company_share
  para garantir que as partes fecham com o total (sem perder centavo).
"""

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
    gross_amount = _extract_gross_amount(event_type, stripe_object)

    rule = db.get_active_split_rule(product_slug) if product_slug else None
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
    else:
        company_share = None
        pro_labore_share = None
        split_rule_applied = None
        status = "pending_classification"

    entry = {
        "stripe_event_id": event["id"],
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


def _extract_gross_amount(event_type: str, stripe_object: dict) -> Decimal:
    """Stripe manda centavos (int); convertemos para Decimal com 2 casas."""
    if event_type == "payment_succeeded":
        cents = stripe_object.get("amount_received") or stripe_object.get("amount", 0)
    elif event_type == "refund":
        cents = -(stripe_object.get("amount_refunded", 0))
    elif event_type == "invoice_paid":
        cents = stripe_object.get("amount_paid", 0)
    else:
        # subscription_created/cancelled e invoice_failed nao movem dinheiro
        cents = 0
    return (Decimal(cents) / 100).quantize(TWO_PLACES)
