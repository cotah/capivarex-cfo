"""Monta o CONTEXTO FINANCEIRO real (a partir do banco) para o ATLAS ler.

So agrega o que existe no sistema hoje: receita (financial_ledger), regras de
split (product_split_rules) e pedidos de gasto (spending_requests). Declara
explicitamente o que NAO esta disponivel, para o ATLAS nunca inventar.
"""

from decimal import Decimal


def _d(value) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception:  # noqa: BLE001
        return Decimal("0")


def build_financial_context(db) -> str:
    entries = db.list_ledger_entries()
    rules = db.list_split_rules()
    spending = db.list_spending_requests()

    total = Decimal("0")
    refunds = Decimal("0")
    pending_class = 0
    by_product: dict[str, Decimal] = {}
    currencies: set[str] = set()
    for e in entries:
        amt = _d(e.get("gross_amount"))
        total += amt
        slug = e.get("product_slug") or "(sem produto)"
        by_product[slug] = by_product.get(slug, Decimal("0")) + amt
        if e.get("status") == "pending_classification":
            pending_class += 1
        if e.get("event_type") == "refund":
            refunds += amt
        if e.get("currency"):
            currencies.add(str(e["currency"]).upper())

    cur = "/".join(sorted(currencies)) or "?"
    lines: list[str] = []
    lines.append("## Receita (livro-razao / Stripe)")
    lines.append(f"- Eventos registrados: {len(entries)}")
    lines.append(f"- Receita liquida acumulada: {total} {cur} (reembolsos ja incluidos: {refunds})")
    lines.append(f"- Eventos SEM classificacao de split (pending_classification): {pending_class}")
    if by_product:
        lines.append("- Por produto:")
        for slug, amt in sorted(by_product.items(), key=lambda kv: kv[1], reverse=True):
            lines.append(f"  - {slug}: {amt} {cur}")

    lines.append("")
    lines.append("## Regras de split aprovadas (product_split_rules)")
    if rules:
        for r in rules:
            active = "ativa" if r.get("active", True) else "inativa"
            lines.append(
                f"- {r.get('product_slug')}: empresa {r.get('company_pct')}% / "
                f"pro-labore {r.get('pro_labore_pct')}% ({active})"
            )
    else:
        lines.append("- Nenhuma regra cadastrada. Toda receita fica pendente de classificacao.")

    lines.append("")
    lines.append("## Pedidos de gasto (spending_requests / CFO Gatekeeper)")
    pend = [s for s in spending if s.get("status") == "pending"]
    pend_total = sum((_d(s.get("estimated_cost")) for s in pend), Decimal("0"))
    lines.append(f"- Total de pedidos: {len(spending)} | pendentes: {len(pend)}")
    lines.append(f"- Custo estimado dos pendentes: {pend_total}")
    for s in pend[:15]:
        lines.append(
            f"  - [{s.get('status')}] {s.get('agent')} / {s.get('product')}: "
            f"{s.get('action')} — {s.get('estimated_cost')} {s.get('currency', '')}"
        )

    lines.append("")
    lines.append("## Dados NAO disponiveis neste sistema (trate como premissa/faltante)")
    lines.append(
        "- Saldo de caixa/banco, despesas operacionais, folha de pagamento, impostos "
        "provisionados, CAC, LTV, churn, runway e burn rate NAO sao rastreados aqui. "
        "Se precisar deles, declare que estao ausentes."
    )
    return "\n".join(lines)
