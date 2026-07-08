"""Criacao do app FastAPI do CFO Agent."""

from fastapi import FastAPI

from app.observability import init_sentry
from app.routers import atlas, health, reports, spending_requests, split_rules, webhooks


def create_app() -> FastAPI:
    init_sentry()
    app = FastAPI(title="Capivarex CFO Agent")
    app.include_router(health.router)
    app.include_router(split_rules.router)
    app.include_router(webhooks.router)
    app.include_router(reports.router)
    app.include_router(spending_requests.router)
    app.include_router(atlas.router)
    return app


# Instancia usada pelo uvicorn em producao (Procfile / Railway)
app = create_app()
