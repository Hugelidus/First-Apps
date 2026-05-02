"""Carga de configuración desde variables de entorno (.env)."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"


class Settings(BaseSettings):
    """Configuración global cargada desde .env."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    chat_model: str = Field(default="claude-sonnet-4-6", alias="CHAT_MODEL")
    spoiler_model: str = Field(
        default="claude-haiku-4-5-20251001", alias="SPOILER_MODEL"
    )

    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    qdrant_collection: str = Field(default="kraken", alias="QDRANT_COLLECTION")

    embed_model: str = Field(default="BAAI/bge-m3", alias="EMBED_MODEL")
    embed_dim: int = Field(default=1024, alias="EMBED_DIM")

    http_user_agent: str = Field(
        default="CinemaIA-MVP/0.1 (+https://github.com/Hugelidus/First-Apps)",
        alias="HTTP_USER_AGENT",
    )
    http_rate_limit_per_host: float = Field(
        default=1.0, alias="HTTP_RATE_LIMIT_PER_HOST"
    )

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la instancia única de Settings."""
    return Settings()


def setup_logging(level: str | None = None) -> None:
    """Inicializa logging con formato consistente."""
    chosen = (level or get_settings().log_level).upper()
    logging.basicConfig(
        level=chosen,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
