"""Autenticacao dos endpoints administrativos via CFO_API_KEY.

A chave nunca e logada. Comparacao em tempo constante (secrets.compare_digest)
para evitar timing attacks.
"""

import hashlib
import hmac
import secrets
import time

from fastapi import Header, HTTPException

from app.config import get_settings

# Tolerancia maxima entre o timestamp assinado e agora (protege contra replay)
STRIPE_TIMESTAMP_TOLERANCE_SECONDS = 300


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().cfo_api_key
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="API key ausente ou invalida")


def verify_stripe_signature(payload: bytes, signature_header: str | None) -> None:
    """Valida o header Stripe-Signature (formato: t=<ts>,v1=<hmac>).

    Implementado manualmente de proposito: o servico nao usa o SDK do Stripe,
    entao nao existe caminho no codigo capaz de chamar a API do Stripe.
    Levanta 401 se a assinatura estiver ausente, invalida ou expirada.
    """
    rejection = HTTPException(
        status_code=401, detail="Assinatura Stripe ausente ou invalida"
    )
    if not signature_header:
        raise rejection

    parts = dict(
        item.split("=", 1) for item in signature_header.split(",") if "=" in item
    )
    timestamp, received_v1 = parts.get("t"), parts.get("v1")
    if not timestamp or not received_v1 or not timestamp.isdigit():
        raise rejection

    if abs(time.time() - int(timestamp)) > STRIPE_TIMESTAMP_TOLERANCE_SECONDS:
        raise rejection

    secret = get_settings().stripe_webhook_secret
    signed_payload = f"{timestamp}.".encode() + payload
    expected_v1 = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    if not secrets.compare_digest(expected_v1, received_v1):
        raise rejection
