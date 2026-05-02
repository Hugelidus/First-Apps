"""Tests de tier_assigner y canon_assigner."""

import pytest

from src.ingest.canon_assigner import canon_for
from src.ingest.tier_assigner import tier_for


def test_tier_oficial():
    assert tier_for("wikipedia_pelicula") == 1
    assert tier_for("wikipedia_novela") == 1
    assert tier_for("festival_malaga") == 1


def test_tier_critica_y_fans():
    assert tier_for("sensacine") == 2
    assert tier_for("letterboxd") == 3


def test_tier_fuente_desconocida():
    with pytest.raises(KeyError):
        tier_for("fuente_inventada")


def test_canon_pelicula_vs_novela():
    assert canon_for("wikipedia_pelicula") == "pelicula"
    assert canon_for("wikipedia_novela") == "novela"
    assert canon_for("reddit_cineespanol") == "ambas"
