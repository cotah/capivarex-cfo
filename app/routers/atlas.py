"""Endpoints do ATLAS (CFO de IA). Protegidos por X-API-Key.

Fail-closed: sem chave de LLM configurada, retorna 503.
Multi-tenant: exige X-Account-Id (workspace do cliente logado); sem ele -> 400.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.atlas import llm, service
from app.db import get_db
from app.security import require_account_id, require_api_key

router = APIRouter()


class AtlasAsk(BaseModel):
    question: str = Field(min_length=1, max_length=4000)


class SpendingEval(BaseModel):
    agent: str | None = None
    product: str | None = None
    action: str = Field(min_length=1, max_length=500)
    estimated_cost: float = Field(ge=0)
    currency: str = "EUR"
    description: str | None = Field(default=None, max_length=2000)


def _ensure_llm() -> None:
    if not llm.llm_available():
        raise HTTPException(
            status_code=503,
            detail="ATLAS indisponivel: configure ANTHROPIC_API_KEY ou OPENAI_API_KEY",
        )


@router.post("/atlas/ask", dependencies=[Depends(require_api_key)])
def atlas_ask(
    payload: AtlasAsk,
    account_id: str = Depends(require_account_id),
    db=Depends(get_db),
) -> dict:
    _ensure_llm()
    try:
        return {"answer": service.ask_atlas(db, account_id, payload.question)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Falha ao consultar ATLAS: {e}") from e


@router.get("/atlas/report/weekly", dependencies=[Depends(require_api_key)])
def atlas_weekly(
    account_id: str = Depends(require_account_id), db=Depends(get_db)
) -> dict:
    _ensure_llm()
    try:
        return {"report": service.weekly_report(db, account_id)}
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Falha ao gerar relatorio: {e}") from e


@router.post("/atlas/spending/evaluate", dependencies=[Depends(require_api_key)])
def atlas_spending_evaluate(
    payload: SpendingEval,
    account_id: str = Depends(require_account_id),
    db=Depends(get_db),
) -> dict:
    _ensure_llm()
    try:
        return service.evaluate_spending(db, account_id, payload.model_dump())
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Falha ao avaliar gasto: {e}") from e
