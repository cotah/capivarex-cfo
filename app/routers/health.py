"""GET /health — sem autenticacao, confirma servico de pe e banco acessivel."""

from fastapi import APIRouter, Depends

from app.db import get_db

router = APIRouter()


@router.get("/health")
def health(db=Depends(get_db)):
    db.ping()
    return {"status": "ok", "database": "connected"}
