"""POST /webhooks/stripe — recebe eventos da conta Stripe Factory.

Regra de arquitetura: este servico SO LE eventos. Nunca chama a API do
Stripe (nao ha SDK nem secret key da API no projeto).
"""

import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.db import get_db
from app.security import verify_stripe_signature
from app.services import ledger

router = APIRouter()
logger = logging.getLogger("cfo.webhooks")


def _parse_event(payload: bytes) -> dict:
    """Valida o envelope minimo de um evento Stripe. Corpo invalido -> 400
    (definitivo); 500 faria o Stripe reenviar para sempre um evento que
    sempre vai quebrar. Erros de banco continuam 500 (retry do Stripe ajuda)."""
    bad_request = HTTPException(status_code=400, detail="Evento Stripe malformado")
    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise bad_request
    if (
        not isinstance(event, dict)
        or not isinstance(event.get("id"), str)
        or not event["id"]
        or not isinstance(event.get("type"), str)
        or not isinstance(event.get("data"), dict)
        or not isinstance(event["data"].get("object"), dict)
    ):
        raise bad_request
    return event


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db=Depends(get_db),
):
    payload = await request.body()
    verify_stripe_signature(payload, stripe_signature)

    event = _parse_event(payload)
    entry = ledger.process_event(db, event)
    if entry is None:
        logger.info("evento %s (%s): tipo ignorado", event["id"], event["type"])
        return {"received": True, "ignored": True}
    if entry["status"] == "pending_classification":
        logger.warning(
            "evento %s (%s): pending_classification — produto %r sem regra",
            event["id"], event["type"], entry["product_slug"],
        )
    else:
        logger.info(
            "evento %s (%s): %s", event["id"], event["type"], entry["status"]
        )
    return {"received": True, "status": entry["status"]}
