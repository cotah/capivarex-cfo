"""Criacao do app FastAPI do CFO Agent."""

from fastapi import FastAPI

from app.routers import health, reports, split_rules, webhooks


def create_app() -> FastAPI:
    app = FastAPI(title="Capivarex CFO Agent")
    app.include_router(health.router)
    app.include_router(split_rules.router)
    app.include_router(webhooks.router)
    app.include_router(reports.router)
    return app


# Instancia usada pelo uvicorn em producao (Procfile / Railway)
app = create_app()
