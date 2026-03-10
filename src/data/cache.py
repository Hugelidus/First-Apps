"""Cache local para respuestas de APIs."""

import hashlib
import json
import time
from pathlib import Path

from src.config import CACHE_DIR


def _cache_path(key: str) -> Path:
    hashed = hashlib.md5(key.encode()).hexdigest()
    return CACHE_DIR / f"{hashed}.json"


def get_cached(key: str, ttl: int) -> dict | list | None:
    """Obtiene datos del cache si no han expirado."""
    path = _cache_path(key)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if time.time() - data["timestamp"] > ttl:
        path.unlink()
        return None
    return data["payload"]


def set_cache(key: str, payload: dict | list) -> None:
    """Guarda datos en el cache."""
    path = _cache_path(key)
    path.write_text(json.dumps({
        "timestamp": time.time(),
        "payload": payload,
    }, default=str))
