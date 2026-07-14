"""Autenticacao dos endpoints administrativos via CFO_API_KEY.

A chave nunca e logada. Comparacao em tempo constante (secrets.compare_digest)
para evitar timing attacks.
"""

import hashlib
import hmac
import secrets
import time
import uuid

from fastapi import Header, HTTPException

from app.config import get_settings

# Tolerancia maxima entre o timestamp assinado e agora (protege contra replay)
STRIPE_TIMESTAMP_TOLERANCE_SECONDS = 300


def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().cfo_api_key
    if x_api_key is None or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(status_code=401, detail="API key ausente ou invalida")


def require_account_id(x_account_id: str | None = Header(default=None)) -> str:
    """Multi-tenant: todo dado e lido/escrito no escopo de um workspace.

    Regra de ouro: sem X-Account-Id -> 400. NUNCA devolver dado global
    (fail-closed evita vazamento entre clientes). Valida o formato UUID
    aqui para falhar com 400 claro, nao com 500 do banco.
    """
    if x_account_id is None or not x_account_id.strip():
        raise HTTPException(status_code=400, detail="Header X-Account-Id obrigatorio")
    try:
        return str(uuid.UUID(x_account_id.strip()))
    except ValueError:
        raise HTTPException(
            status_code=400, detail="X-Account-Id invalido (esperado UUID)"
        ) from None


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

    # Durante rotacao de secret o Stripe manda VARIOS v1 no mesmo header;
    # a assinatura vale se QUALQUER um bater (spec oficial do Stripe).
    timestamp = None
    received_v1s = []
    for item in signature_header.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        if key == "t":
            timestamp = value
        elif key == "v1":
            received_v1s.append(value)

    if not timestamp or not received_v1s or not timestamp.isdigit():
        raise rejection

    if abs(time.time() - int(timestamp)) > STRIPE_TIMESTAMP_TOLERANCE_SECONDS:
        raise rejection

    secret = get_settings().stripe_webhook_secret
    signed_payload = f"{timestamp}.".encode() + payload
    expected_v1 = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    if not any(secrets.compare_digest(expected_v1, v1) for v1 in received_v1s):
        raise rejection
