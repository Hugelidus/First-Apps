"""Cliente para Football-Data.org (backup y clasificaciones)."""

import requests

from src.config import FOOTBALL_DATA_BASE, FOOTBALL_DATA_HEADERS, CACHE_TTL_FIXTURES
from src.data.cache import get_cached, set_cache

CL_CODE = "CL"  # Champions League competition code


def _get(endpoint: str, ttl: int = CACHE_TTL_FIXTURES) -> dict:
    """Petición a Football-Data.org con cache."""
    cache_key = f"fdata:{endpoint}"
    cached = get_cached(cache_key, ttl)
    if cached is not None:
        return cached

    url = f"{FOOTBALL_DATA_BASE}/{endpoint}"
    resp = requests.get(url, headers=FOOTBALL_DATA_HEADERS, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    set_cache(cache_key, data)
    return data


def get_matches(status: str | None = None) -> list[dict]:
    """Partidos de Champions League."""
    endpoint = f"competitions/{CL_CODE}/matches"
    data = _get(endpoint)
    matches = data.get("matches", [])
    if status:
        matches = [m for m in matches if m.get("status") == status]
    return matches


def get_standings() -> list[dict]:
    """Clasificación actual de Champions League."""
    data = _get(f"competitions/{CL_CODE}/standings")
    return data.get("standings", [])


def get_scorers(limit: int = 10) -> list[dict]:
    """Goleadores de Champions League."""
    data = _get(f"competitions/{CL_CODE}/scorers")
    return data.get("scorers", [])[:limit]
