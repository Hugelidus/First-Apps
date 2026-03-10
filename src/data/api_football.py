"""Cliente para API-Football (api-sports.io)."""

import requests

from src.config import (
    API_FOOTBALL_BASE,
    API_FOOTBALL_HEADERS,
    CACHE_TTL_FIXTURES,
    CACHE_TTL_STATS,
    CHAMPIONS_LEAGUE_ID,
)
from src.data.cache import get_cached, set_cache


def _get(endpoint: str, params: dict | None = None, ttl: int = CACHE_TTL_STATS) -> dict:
    """Hace una petición a API-Football con cache."""
    cache_key = f"apifb:{endpoint}:{params}"
    cached = get_cached(cache_key, ttl)
    if cached is not None:
        return cached

    url = f"{API_FOOTBALL_BASE}/{endpoint}"
    resp = requests.get(url, headers=API_FOOTBALL_HEADERS, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    set_cache(cache_key, data)
    return data


def get_fixtures(season: int, status: str | None = None) -> list[dict]:
    """Obtiene partidos de Champions League para una temporada."""
    params = {"league": CHAMPIONS_LEAGUE_ID, "season": season}
    if status:
        params["status"] = status
    data = _get("fixtures", params, ttl=CACHE_TTL_FIXTURES)
    return data.get("response", [])


def get_upcoming_fixtures(season: int) -> list[dict]:
    """Partidos próximos no jugados (NS = Not Started)."""
    return get_fixtures(season, status="NS")


def get_finished_fixtures(season: int) -> list[dict]:
    """Partidos ya jugados (FT = Full Time)."""
    return get_fixtures(season, status="FT")


def get_fixture_stats(fixture_id: int) -> list[dict]:
    """Estadísticas de un partido específico."""
    data = _get("fixtures/statistics", {"fixture": fixture_id})
    return data.get("response", [])


def get_head_to_head(team1_id: int, team2_id: int, last: int = 10) -> list[dict]:
    """Historial de enfrentamientos entre dos equipos."""
    h2h = f"{team1_id}-{team2_id}"
    data = _get("fixtures/headtohead", {"h2h": h2h, "last": last})
    return data.get("response", [])


def get_team_stats(team_id: int, season: int) -> dict:
    """Estadísticas de temporada de un equipo."""
    data = _get("teams/statistics", {
        "team": team_id,
        "season": season,
        "league": CHAMPIONS_LEAGUE_ID,
    })
    return data.get("response", {})


def get_injuries(fixture_id: int) -> list[dict]:
    """Lesiones/sanciones para un partido."""
    data = _get("injuries", {"fixture": fixture_id}, ttl=CACHE_TTL_FIXTURES)
    return data.get("response", [])


def get_odds(fixture_id: int) -> list[dict]:
    """Cuotas pre-partido."""
    data = _get("odds", {"fixture": fixture_id}, ttl=CACHE_TTL_FIXTURES)
    return data.get("response", [])


def get_standings(season: int) -> list[dict]:
    """Clasificación de Champions League."""
    data = _get("standings", {"league": CHAMPIONS_LEAGUE_ID, "season": season})
    return data.get("response", [])
