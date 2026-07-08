"""Inicializacao do Sentry (observabilidade) do CFO Agent.

Le o DSN direto de os.environ (nao do Settings estrito) para nunca acoplar
a observabilidade a validacao das envs obrigatorias — e para funcionar em
tempo de import de create_app(). Sem SENTRY_DSN, e um no-op silencioso.
"""

import logging
import os

import sentry_sdk

logger = logging.getLogger("cfo.observability")

_initialized = False


def init_sentry() -> bool:
    """Inicializa o Sentry se SENTRY_DSN estiver setado. Retorna True se ativou."""
    global _initialized
    if _initialized:
        return True
    dsn = os.environ.get("SENTRY_DSN", "")
    if not dsn:
        return False
    try:
        traces = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0") or 0)
    except ValueError:
        traces = 0.0
    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("ENVIRONMENT", "production"),
        traces_sample_rate=traces,
        send_default_pii=False,  # financeiro: nunca enviar PII por padrao
    )
    _initialized = True
    logger.info("sentry habilitado")
    return True
