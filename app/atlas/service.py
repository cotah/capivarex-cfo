"""Servico do ATLAS: monta o prompt (contexto + persona) e chama a LLM."""

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
