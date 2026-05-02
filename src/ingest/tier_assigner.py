"""Asignación de tier (1 oficial, 2 crítica, 3 fans) por fuente."""

from __future__ import annotations

# Mapeo declarativo: fuente_slug → tier.
TIER_BY_FUENTE: dict[str, int] = {
    "wikipedia_pelicula": 1,
    "wikipedia_novela": 1,
    "festival_malaga": 1,
    "rtve": 1,
    "sensacine": 2,
    "espinof": 2,
    "cinemania": 2,
    "fotogramas": 2,
    "abc_cine": 2,
    "elpais_cine": 2,
    "filmaffinity_critica": 2,
    "letterboxd": 3,
    "goodreads_novela": 3,
    "reddit_cineespanol": 3,
    "filmaffinity_usuarios": 3,
}


def tier_for(fuente: str) -> int:
    """Devuelve el tier para una fuente conocida; lanza si no la conoce."""
    if fuente not in TIER_BY_FUENTE:
        raise KeyError(
            f"Fuente desconocida '{fuente}'. Añádela a TIER_BY_FUENTE."
        )
    return TIER_BY_FUENTE[fuente]
