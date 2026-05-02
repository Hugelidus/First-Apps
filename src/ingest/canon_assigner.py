"""Asignación de origen_canon (pelicula | novela | ambas) por fuente."""

from __future__ import annotations

from typing import Literal

OrigenCanon = Literal["pelicula", "novela", "ambas"]

CANON_BY_FUENTE: dict[str, OrigenCanon] = {
    "wikipedia_pelicula": "pelicula",
    "festival_malaga": "pelicula",
    "rtve": "pelicula",
    "sensacine": "pelicula",
    "espinof": "pelicula",
    "cinemania": "pelicula",
    "fotogramas": "pelicula",
    "abc_cine": "pelicula",
    "elpais_cine": "pelicula",
    "letterboxd": "pelicula",
    "filmaffinity_usuarios": "pelicula",
    "filmaffinity_critica": "pelicula",
    "wikipedia_novela": "novela",
    "goodreads_novela": "novela",
    "reddit_cineespanol": "ambas",
}


def canon_for(fuente: str) -> OrigenCanon:
    """Devuelve el origen_canon para una fuente; lanza si no la conoce."""
    if fuente not in CANON_BY_FUENTE:
        raise KeyError(
            f"Fuente desconocida '{fuente}'. Añádela a CANON_BY_FUENTE."
        )
    return CANON_BY_FUENTE[fuente]
