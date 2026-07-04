"""Agregacao do relatorio financeiro.

pending_classification sempre aparece em bloco proprio e destacado:
falhar visivel e melhor que numero errado silencioso.
"""

from decimal import Decimal


def summary(db, product_slug: str | None = None, since: str | None = None) -> dict:
    entries = db.list_ledger_entries(product_slug=product_slug, since=since)

    total_gross = sum((Decimal(e["gross_amount"]) for e in entries), Decimal("0"))
    total_company = sum(
        (Decimal(e["company_share"]) for e in entries if e["company_share"]),
        Decimal("0"),
    )
    total_pro_labore = sum(
        (Decimal(e["pro_labore_share"]) for e in entries if e["pro_labore_share"]),
        Decimal("0"),
    )

    pending = [e for e in entries if e["status"] == "pending_classification"]
    pending_gross = sum((Decimal(e["gross_amount"]) for e in pending), Decimal("0"))
    pending_products = sorted(
        {e["product_slug"] or "(sem product_slug)" for e in pending}
    )

    return {
        "total_gross": str(total_gross),
        "total_company_share": str(total_company),
        "total_pro_labore_share": str(total_pro_labore),
        "transaction_count": len(entries),
        "pending_classification": {
            "count": len(pending),
            "total_gross": str(pending_gross),
            "products": pending_products,
        },
    }
