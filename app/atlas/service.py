"""Servico do ATLAS: monta o prompt (contexto + persona) e chama a LLM."""

import os
from decimal import Decimal

from app.atlas.context import build_financial_context
from app.atlas.llm import ask_llm
from app.atlas.persona import ATLAS_SYSTEM


def ask_atlas(db, question: str) -> str:
    context = build_financial_context(db)
    prompt = (
        "CONTEXTO FINANCEIRO ATUAL (dados reais do sistema Capivarex CFO):\n"
        f"{context}\n\n"
        "PERGUNTA DO FUNDADOR:\n" + question.strip()
    )
    return ask_llm(ATLAS_SYSTEM, prompt)


def weekly_report(db) -> str:
    context = build_financial_context(db)
    prompt = (
        "CONTEXTO FINANCEIRO ATUAL (dados reais do sistema Capivarex CFO):\n"
        f"{context}\n\n"
        "Gere o RELATORIO FINANCEIRO SEMANAL executivo no formato ATLAS: "
        "diagnostico, numeros principais, riscos, plano de acao priorizado e "
        "as prioridades da proxima semana. Objetivo e acionavel."
    )
    return ask_llm(ATLAS_SYSTEM, prompt, max_tokens=3000)


def _auto_approve_limit() -> Decimal:
    try:
        return Decimal(os.environ.get("ATLAS_AUTO_APPROVE_LIMIT_EUR", "50"))
    except Exception:  # noqa: BLE001
        return Decimal("50")


def _to_decimal(value) -> Decimal:
    try:
        return Decimal(str(value if value is not None else "0"))
    except Exception:  # noqa: BLE001
        return Decimal("0")


def _format_request(req: dict) -> str:
    return (
        f"- Agente/solicitante: {req.get('agent') or '(fundador)'}\n"
        f"- Produto: {req.get('product') or '(nao informado)'}\n"
        f"- Acao/gasto: {req.get('action')}\n"
        f"- Custo estimado: {req.get('estimated_cost')} {req.get('currency') or 'EUR'}\n"
        f"- Descricao: {req.get('description') or '(sem descricao)'}"
    )


def evaluate_spending(db, req: dict) -> dict:
    """ATLAS avalia um pedido de gasto. Decide sozinho ate o limite (EUR);
    acima disso, ou em outra moeda, marca requires_founder_approval=True."""
    limit = _auto_approve_limit()
    cost = _to_decimal(req.get("estimated_cost"))
    currency = (req.get("currency") or "EUR").upper()
    over_limit = currency != "EUR" or cost > limit

    context = build_financial_context(db)
    instruction = (
        "Avalie o PEDIDO DE GASTO abaixo como CFO, usando seu sistema de aprovacao. "
        "Comece a resposta com uma linha exatamente assim: "
        "'DECISAO: <aprovar|aprovar com condicoes|experimento|adiar|rejeitar>'. "
        "Depois entregue: justificativa objetiva, condicoes e limite de perda, "
        "criterio de sucesso e criterio de parada."
    )
    if over_limit:
        instruction += (
            f" IMPORTANTE: este gasto ({cost} {currency}) esta ACIMA do limite de "
            f"aprovacao automatica (EUR {limit}) ou em outra moeda. De seu parecer, "
            "mas deixe explicito que a decisao final e do fundador (escalar)."
        )
    prompt = (
        "CONTEXTO FINANCEIRO ATUAL (dados reais do sistema Capivarex CFO):\n"
        f"{context}\n\nPEDIDO DE GASTO:\n{_format_request(req)}\n\n{instruction}"
    )
    analysis = ask_llm(ATLAS_SYSTEM, prompt)
    return {
        "estimated_cost": str(cost),
        "currency": currency,
        "auto_approve_limit_eur": str(limit),
        "requires_founder_approval": over_limit,
        "analysis": analysis,
    }
