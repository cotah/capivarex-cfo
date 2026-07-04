"""Configuracao via variaveis de ambiente.

Todos os campos sao obrigatorios (sem default): se faltar env var,
o servico falha na inicializacao — nunca sobe meio configurado.
Nenhum valor e logado ou exposto.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_key: str
    stripe_webhook_secret: str
    cfo_api_key: str

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
