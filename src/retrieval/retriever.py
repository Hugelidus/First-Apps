"""Retriever híbrido BM25 + dense con filtros de spoiler y rerank por tier.

- BM25 se mantiene en memoria sobre los chunks de ``data/processed/chunks.jsonl``.
- Dense delega en Qdrant aplicando filtro ``spoiler_level <= modo``.
- Unión por chunk_id, normaliza scores, rerankea por tier y devuelve top N.

Modos:
- pre_cine → max_spoiler = 0
- durante  → max_spoiler = 1
- post_cine → max_spoiler = 2
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable, Literal

from rank_bm25 import BM25Okapi

from src.ingest.pipeline import ProcessedChunk, load_processed_chunks
from src.retrieval.embed import Embedder, get_embedder
from src.retrieval.rerank import ScoredHit, rerank_by_tier
from src.retrieval.store import KrakenStore, SearchHit

logger = logging.getLogger(__name__)

Modo = Literal["pre_cine", "durante", "post_cine"]
MAX_SPOILER: dict[str, int] = {"pre_cine": 0, "durante": 1, "post_cine": 2}

_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text)]


@dataclass
class RetrievalConfig:
    bm25_k: int = 8
    dense_k: int = 8
    final_n: int = 5


@dataclass
class RetrievedChunk:
    """Resultado final, plano y listo para el prompt."""

    chunk_id: str
    text: str
    fuente: str
    url: str
    tier: int
    origen_canon: str
    spoiler_level: int
    bm25_score: float
    dense_score: float


class HybridRetriever:
    """Retriever híbrido BM25 + dense + rerank por tier."""

    def __init__(
        self,
        chunks: list[ProcessedChunk] | None = None,
        store: KrakenStore | None = None,
        embedder: Embedder | None = None,
        config: RetrievalConfig | None = None,
    ) -> None:
        self.config = config or RetrievalConfig()
        self.store = store or KrakenStore()
        self.embedder = embedder or get_embedder()
        self._chunks: list[ProcessedChunk] = chunks if chunks is not None else load_processed_chunks()
        if self._chunks:
            self._bm25 = BM25Okapi([_tokenize(c.text) for c in self._chunks])
        else:
            self._bm25 = None
        self._chunk_index = {c.chunk_id: c for c in self._chunks}

    def reload_chunks(self, chunks: list[ProcessedChunk]) -> None:
        self._chunks = chunks
        self._bm25 = BM25Okapi([_tokenize(c.text) for c in chunks]) if chunks else None
        self._chunk_index = {c.chunk_id: c for c in chunks}

    # --- BM25 ---

    def _bm25_search(self, query: str, max_spoiler: int) -> list[tuple[ProcessedChunk, float]]:
        if not self._bm25 or not self._chunks:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        # Filtrar por spoiler antes de elegir top-k.
        scored: list[tuple[ProcessedChunk, float]] = [
            (c, float(s))
            for c, s in zip(self._chunks, scores)
            if c.spoiler_level <= max_spoiler
        ]
        scored.sort(key=lambda x: -x[1])
        return scored[: self.config.bm25_k]

    # --- Dense ---

    def _dense_search(self, query: str, max_spoiler: int) -> list[SearchHit]:
        vec = self.embedder.embed_one(query)
        return self.store.search(vec, top_k=self.config.dense_k, max_spoiler_level=max_spoiler)

    # --- Híbrido ---

    @staticmethod
    def _normalize(values: Iterable[float]) -> list[float]:
        vals = list(values)
        if not vals:
            return []
        lo, hi = min(vals), max(vals)
        if hi - lo < 1e-9:
            return [0.0 for _ in vals]
        return [(v - lo) / (hi - lo) for v in vals]

    def search(self, query: str, modo: Modo) -> list[RetrievedChunk]:
        max_sp = MAX_SPOILER[modo]
        bm25_hits = self._bm25_search(query, max_sp)
        dense_hits = self._dense_search(query, max_sp)

        bm25_norm = self._normalize([s for _, s in bm25_hits])
        dense_norm = self._normalize([h.score for h in dense_hits])

        bm25_by_id = {c.chunk_id: s for (c, _), s in zip(bm25_hits, bm25_norm)}
        dense_by_id = {h.chunk_id: s for h, s in zip(dense_hits, dense_norm)}

        # Unión: usamos los SearchHit del dense como base, y completamos con
        # ProcessedChunk donde solo tengamos BM25.
        union: dict[str, SearchHit] = {h.chunk_id: h for h in dense_hits}
        for chunk, _ in bm25_hits:
            if chunk.chunk_id not in union:
                union[chunk.chunk_id] = SearchHit(
                    chunk_id=chunk.chunk_id,
                    text=chunk.text,
                    fuente=chunk.fuente,
                    url=chunk.url,
                    tier=chunk.tier,
                    origen_canon=chunk.origen_canon,
                    spoiler_level=chunk.spoiler_level,
                    score=0.0,
                )

        scored = [
            ScoredHit(
                hit=h,
                bm25_score=bm25_by_id.get(cid, 0.0),
                dense_score=dense_by_id.get(cid, 0.0),
            )
            for cid, h in union.items()
        ]
        top = rerank_by_tier(scored, top_n=self.config.final_n)

        return [
            RetrievedChunk(
                chunk_id=s.hit.chunk_id,
                text=s.hit.text,
                fuente=s.hit.fuente,
                url=s.hit.url,
                tier=s.hit.tier,
                origen_canon=s.hit.origen_canon,
                spoiler_level=s.hit.spoiler_level,
                bm25_score=s.bm25_score,
                dense_score=s.dense_score,
            )
            for s in top
        ]
