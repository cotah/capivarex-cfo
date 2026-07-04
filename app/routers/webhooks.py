"""POST /webhooks/stripe — recebe eventos da conta Stripe Factory.

Regra de arquitetura: este servico SO LE eventos. Nunca chama a API do
Stripe (nao ha SDK nem secret key da API no projeto).
"""

import json

from fastapi import APIRouter, Depends, Header, Request

from app.db import get_db
from app.security import verify_stripe_signature
from app.services import ledger

router = APIRouter()


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db=Depends(get_db),
):
    payload = await request.body()
    verify_stripe_signature(payload, stripe_signature)

    event = json.loads(payload)
    entry = ledger.process_event(db, event)
    if entry is None:
        return {"received": True, "ignored": True}
    return {"received": True, "status": entry["status"]}
