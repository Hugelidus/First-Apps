"""Reranking simple por tier.

Después de unir resultados BM25 + dense, ordenamos primero por tier
(1 oficial > 2 crítica > 3 fans) y dentro de cada tier por score
denso (más alto = más cercano en cosine).
"""

from __future__ import annotations

from dataclasses import dataclass

from src.retrieval.store import SearchHit


@dataclass(frozen=True)
class ScoredHit:
    """Hit con score combinado para retrieval híbrido."""

    hit: SearchHit
    bm25_score: float
    dense_score: float

    @property
    def combined_score(self) -> float:
        # Score combinado solo se usa como tiebreak dentro del mismo tier.
        return 0.5 * self.dense_score + 0.5 * self.bm25_score


def rerank_by_tier(hits: list[ScoredHit], top_n: int = 5) -> list[ScoredHit]:
    """Ordena por (tier asc, combined desc) y devuelve los top_n."""
    return sorted(
        hits,
        key=lambda s: (s.hit.tier, -s.combined_score),
    )[:top_n]
