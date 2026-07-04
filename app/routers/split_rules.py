"""POST /split-rules — upsert de regra de split, autenticado com CFO_API_KEY.

Chamado somente APOS aprovacao humana de uma regra. Nenhum agente chama
este endpoint automaticamente.
"""

from fastapi import APIRouter, Depends

from app.db import get_db
from app.schemas import SplitRuleIn
from app.security import require_api_key
from app.services import split_rules as service

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.post("/split-rules")
def upsert_split_rule(rule: SplitRuleIn, db=Depends(get_db)):
    return service.upsert(db, rule)
