"""Tests del rerank por tier."""

from __future__ import annotations

from src.retrieval.rerank import ScoredHit, rerank_by_tier
from src.retrieval.store import SearchHit


def _hit(chunk_id: str, tier: int, score: float = 0.5) -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id,
        text="x",
        fuente="wikipedia_pelicula" if tier == 1 else "letterboxd",
        url="",
        tier=tier,
        origen_canon="pelicula",
        spoiler_level=0,
        score=score,
    )


def test_rerank_tier_1_antes_que_tier_3_aunque_score_dense_menor():
    a = ScoredHit(_hit("A", tier=3), bm25_score=0.9, dense_score=0.9)
    b = ScoredHit(_hit("B", tier=1), bm25_score=0.1, dense_score=0.1)
    out = rerank_by_tier([a, b], top_n=2)
    assert [s.hit.chunk_id for s in out] == ["B", "A"]


def test_rerank_dentro_del_mismo_tier_ordena_por_score_combinado():
    a = ScoredHit(_hit("A", tier=2), bm25_score=0.2, dense_score=0.2)
    b = ScoredHit(_hit("B", tier=2), bm25_score=0.9, dense_score=0.9)
    out = rerank_by_tier([a, b], top_n=2)
    assert [s.hit.chunk_id for s in out] == ["B", "A"]


def test_rerank_top_n_limita_resultados():
    hits = [
        ScoredHit(_hit(str(i), tier=1, score=1.0 / (i + 1)), bm25_score=0.0, dense_score=1.0 / (i + 1))
        for i in range(10)
    ]
    out = rerank_by_tier(hits, top_n=3)
    assert len(out) == 3
