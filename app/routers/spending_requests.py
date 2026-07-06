"""GET /spending-requests — leitura dos pedidos de gasto, autenticado com CFO_API_KEY.

Os pedidos sao criados e decididos (aprovar/rejeitar) por workflows no n8n.
Este router e somente leitura de proposito: nenhum endpoint de escrita aqui.
"""

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_db
from app.security import require_api_key

router = APIRouter(dependencies=[Depends(require_api_key)])


@router.get("/spending-requests")
def list_spending_requests(status: str | None = None, db=Depends(get_db)):
    return db.list_spending_requests(status=status)


@router.get("/spending-requests/{request_id}")
def get_spending_request(request_id: str, db=Depends(get_db)):
    request = db.get_spending_request(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Pedido de gasto nao encontrado")
    return request
