"""Cálculo de forma reciente ponderada temporalmente."""

import math

import numpy as np


def weighted_form(results: list[dict], n_matches: int = 6) -> dict[str, float]:
    """Calcula forma reciente con ponderación temporal.

    Args:
        results: Lista de partidos ordenados del más reciente al más antiguo.
                 Cada dict tiene: goals_for, goals_against, is_home, points (0/1/3)
        n_matches: Número de partidos a considerar.

    Returns:
        Dict con métricas de forma ponderadas.
    """
    recent = results[:n_matches]
    if not recent:
        return {
            "points_avg": 0.0,
            "goals_for_avg": 0.0,
            "goals_against_avg": 0.0,
            "goal_diff_avg": 0.0,
            "win_rate": 0.0,
        }

    # Pesos exponenciales: más recientes pesan más
    weights = [math.exp(-0.3 * i) for i in range(len(recent))]
    total_weight = sum(weights)

    points = sum(r["points"] * w for r, w in zip(recent, weights)) / total_weight
    gf = sum(r["goals_for"] * w for r, w in zip(recent, weights)) / total_weight
    ga = sum(r["goals_against"] * w for r, w in zip(recent, weights)) / total_weight
    wins = sum((1 if r["points"] == 3 else 0) * w for r, w in zip(recent, weights)) / total_weight

    return {
        "points_avg": round(points, 3),
        "goals_for_avg": round(gf, 3),
        "goals_against_avg": round(ga, 3),
        "goal_diff_avg": round(gf - ga, 3),
        "win_rate": round(wins, 3),
    }


def home_away_form(results: list[dict], n_matches: int = 6) -> dict[str, dict]:
    """Calcula forma separada para partidos local y visitante."""
    home_results = [r for r in results if r.get("is_home")]
    away_results = [r for r in results if not r.get("is_home")]

    return {
        "overall": weighted_form(results, n_matches),
        "home": weighted_form(home_results, n_matches),
        "away": weighted_form(away_results, n_matches),
    }


def momentum(results: list[dict], n_matches: int = 5) -> float:
    """Calcula momentum: tendencia reciente vs forma general.

    Retorna valor positivo si el equipo está mejorando,
    negativo si está empeorando.
    """
    if len(results) < n_matches * 2:
        return 0.0

    recent = np.mean([r["points"] for r in results[:n_matches]])
    older = np.mean([r["points"] for r in results[n_matches:n_matches * 2]])

    return round(recent - older, 3)
