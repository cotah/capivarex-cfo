"""GET /reports/summary — totais e pendencias, autenticado com CFO_API_KEY.

Multi-tenant: exige X-Account-Id (workspace do cliente logado); sem ele -> 400.
"""

from datetime import datetime

from fastapi import APIRouter, Depends

from app.db import get_db
from app.security import require_account_id, require_api_key
from app.services import reports as service

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/reports/summary")
def summary(
    product_slug: str | None = None,
    since: datetime | None = None,  # S5: data invalida -> 422 aqui, nao 500 no banco
    account_id: str = Depends(require_account_id),
    db=Depends(get_db),
):
    return service.summary(
        db,
        account_id,
        product_slug=product_slug,
        since=since.isoformat() if since else None,
    )
