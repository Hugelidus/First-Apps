"""Tests mínimos de configuración: aseguran que Settings carga con defaults."""

from src.config import get_settings


def test_settings_carga_con_defaults(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    s = get_settings()
    assert s.chat_model == "claude-sonnet-4-6"
    assert s.spoiler_model == "claude-haiku-4-5-20251001"
    assert s.embed_model == "BAAI/bge-m3"
    assert s.embed_dim == 1024
    assert s.qdrant_collection == "kraken"
