"""Cliente para Football-Data.org (fuente principal gratuita)."""

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


def get_upcoming_matches() -> list[dict]:
    """Próximos partidos programados."""
    matches = get_matches()
    upcoming = [m for m in matches if m.get("status") in ("SCHEDULED", "TIMED")]
    upcoming.sort(key=lambda x: x.get("utcDate", ""))
    return upcoming


def get_finished_matches() -> list[dict]:
    """Partidos ya jugados."""
    matches = get_matches()
    finished = [m for m in matches if m.get("status") == "FINISHED"]
    finished.sort(key=lambda x: x.get("utcDate", ""), reverse=True)
    return finished


def get_standings() -> list[dict]:
    """Clasificación actual de Champions League."""
    data = _get(f"competitions/{CL_CODE}/standings")
    return data.get("standings", [])


def get_scorers(limit: int = 10) -> list[dict]:
    """Goleadores de Champions League."""
    data = _get(f"competitions/{CL_CODE}/scorers")
    return data.get("scorers", [])[:limit]


def get_team_matches(team_id: int) -> list[dict]:
    """Partidos de un equipo específico en Champions."""
    matches = get_matches()
    return [
        m for m in matches
        if m["homeTeam"]["id"] == team_id or m["awayTeam"]["id"] == team_id
    ]


def get_team_stats_summary(team_id: int) -> dict:
    """Resumen de estadísticas de un equipo en la Champions actual."""
    matches = get_matches()
    team_matches = [
        m for m in matches
        if (m["homeTeam"]["id"] == team_id or m["awayTeam"]["id"] == team_id)
        and m["status"] == "FINISHED"
    ]

    goals_for = 0
    goals_against = 0
    wins = draws = losses = 0
    clean_sheets = 0

    for m in team_matches:
        ft = m.get("score", {}).get("fullTime", {})
        gh = ft.get("home", 0) or 0
        ga = ft.get("away", 0) or 0
        is_home = m["homeTeam"]["id"] == team_id

        gf = gh if is_home else ga
        gc = ga if is_home else gh
        goals_for += gf
        goals_against += gc

        if gc == 0:
            clean_sheets += 1
        if gf > gc:
            wins += 1
        elif gf == gc:
            draws += 1
        else:
            losses += 1

    played = len(team_matches)
    return {
        "played": played,
        "wins": wins,
        "draws": draws,
        "losses": losses,
        "goals_for": goals_for,
        "goals_against": goals_against,
        "goals_per_match": round(goals_for / played, 2) if played else 0,
        "conceded_per_match": round(goals_against / played, 2) if played else 0,
        "clean_sheets": clean_sheets,
    }


def search_team(name: str) -> dict | None:
    """Busca un equipo por nombre parcial en los partidos de CL."""
    matches = get_matches()
    name_lower = name.lower()
    for m in matches:
        for side in ("homeTeam", "awayTeam"):
            team = m[side]
            if name_lower in team["name"].lower() or name_lower in team.get("shortName", "").lower():
                return team
    return None
