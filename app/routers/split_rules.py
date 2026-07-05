"""POST /split-rules — upsert de regra de split, autenticado com CFO_API_KEY.

Chamado somente APOS aprovacao humana de uma regra. Nenhum agente chama
este endpoint automaticamente.
"""

import logging

from fastapi import APIRouter, Depends

from app.db import get_db
from app.schemas import SplitRuleIn
from app.security import require_api_key
from app.services import split_rules as service

router = APIRouter(dependencies=[Depends(require_api_key)])
logger = logging.getLogger("cfo.split_rules")


@router.post("/split-rules")
def upsert_split_rule(rule: SplitRuleIn, db=Depends(get_db)):
    saved = service.upsert(db, rule)
    logger.info(
        "split rule upsert: %s -> %s/%s (approved_by=%s)",
        rule.product_slug, rule.company_pct, rule.pro_labore_pct, rule.approved_by,
    )
    return saved
