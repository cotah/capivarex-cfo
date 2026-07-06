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

    # S3: nunca somar moedas diferentes num numero so. Os totais de cima
    # continuam existindo (compatibilidade), mas by_currency e a leitura certa
    # quando houver mais de uma moeda.
    by_currency: dict[str, dict] = {}
    for e in entries:
        bucket = by_currency.setdefault(
            e.get("currency") or "(sem moeda)",
            {"gross": Decimal("0"), "company": Decimal("0"),
             "pro_labore": Decimal("0"), "count": 0},
        )
        bucket["gross"] += Decimal(e["gross_amount"])
        bucket["company"] += Decimal(e["company_share"] or "0")
        bucket["pro_labore"] += Decimal(e["pro_labore_share"] or "0")
        bucket["count"] += 1

    return {
        "total_gross": str(total_gross),
        "total_company_share": str(total_company),
        "total_pro_labore_share": str(total_pro_labore),
        "transaction_count": len(entries),
        "by_currency": {
            cur: {
                "total_gross": str(b["gross"]),
                "total_company_share": str(b["company"]),
                "total_pro_labore_share": str(b["pro_labore"]),
                "transaction_count": b["count"],
            }
            for cur, b in sorted(by_currency.items())
        },
        "pending_classification": {
            "count": len(pending),
            "total_gross": str(pending_gross),
            "products": pending_products,
        },
        # Pedidos de gasto aguardando decisao no n8n — receita + gastos
        # pendentes numa visao so. Campo aditivo, nao afeta o resto.
        "pending_spending_requests": len(db.list_spending_requests(status="pending")),
    }
