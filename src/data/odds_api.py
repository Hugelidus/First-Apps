"""Cliente para The Odds API."""

import requests

from src.config import ODDS_API_BASE, ODDS_API_KEY, CACHE_TTL_ODDS
from src.data.cache import get_cached, set_cache

SPORT_KEY = "soccer_uefa_champs_league"


def _get(endpoint: str, params: dict | None = None) -> list | dict:
    """Petición a The Odds API con cache."""
    params = params or {}
    params["apiKey"] = ODDS_API_KEY
    cache_key = f"odds:{endpoint}:{params}"
    cached = get_cached(cache_key, CACHE_TTL_ODDS)
    if cached is not None:
        return cached

    url = f"{ODDS_API_BASE}/{endpoint}"
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    set_cache(cache_key, data)
    return data


def get_odds_1x2() -> list[dict]:
    """Cuotas 1X2 (head to head) de múltiples casas de apuestas."""
    return _get(f"sports/{SPORT_KEY}/odds", {
        "regions": "eu",
        "markets": "h2h",
        "oddsFormat": "decimal",
    })


def get_odds_totals() -> list[dict]:
    """Cuotas Over/Under de múltiples casas de apuestas."""
    return _get(f"sports/{SPORT_KEY}/odds", {
        "regions": "eu",
        "markets": "totals",
        "oddsFormat": "decimal",
    })


def get_odds_spreads() -> list[dict]:
    """Cuotas handicap de múltiples casas de apuestas."""
    return _get(f"sports/{SPORT_KEY}/odds", {
        "regions": "eu",
        "markets": "spreads",
        "oddsFormat": "decimal",
    })


def get_all_odds() -> list[dict]:
    """Cuotas de todos los mercados combinados."""
    return _get(f"sports/{SPORT_KEY}/odds", {
        "regions": "eu",
        "markets": "h2h,totals,spreads",
        "oddsFormat": "decimal",
    })
