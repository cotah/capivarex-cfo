"""GET /reports/summary — totais e pendencias, autenticado com CFO_API_KEY."""

from datetime import datetime

from fastapi import APIRouter, Depends

from app.db import get_db
from app.security import require_api_key
from app.services import reports as service

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/reports/summary")
def summary(
    product_slug: str | None = None,
    since: datetime | None = None,  # S5: data invalida -> 422 aqui, nao 500 no banco
    db=Depends(get_db),
):
    return service.summary(
        db,
        product_slug=product_slug,
        since=since.isoformat() if since else None,
    )
