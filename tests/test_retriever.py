"""Tests del HybridRetriever con store y embedder fakes."""

from __future__ import annotations

import numpy as np

from src.ingest.pipeline import ProcessedChunk
from src.retrieval.retriever import HybridRetriever, RetrievalConfig
from src.retrieval.store import SearchHit


class _FakeEmbedder:
    """Embedder determinista basado en presencia de palabras clave."""

    dim = 8

    def embed_one(self, text: str) -> np.ndarray:
        return self._encode(text)

    def embed(self, texts: list[str], **_) -> np.ndarray:
        return np.vstack([self._encode(t) for t in texts])

    @staticmethod
    def _encode(text: str) -> np.ndarray:
        keywords = ["unai", "esti", "kraken", "madre", "vitoria", "madrid", "libro", "horas"]
        v = np.array([1.0 if k in text.lower() else 0.0 for k in keywords], dtype=np.float32)
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else v


class _FakeStore:
    """Store en memoria que filtra por max_spoiler_level y simula cosine."""

    def __init__(self, chunks: list[ProcessedChunk], embedder: _FakeEmbedder) -> None:
        self.chunks = chunks
        self.embedder = embedder
        self._vecs = embedder.embed([c.text for c in chunks])

    def search(self, vector, *, top_k: int, max_spoiler_level: int) -> list[SearchHit]:
        if isinstance(vector, list):
            vector = np.array(vector, dtype=np.float32)
        scores = self._vecs @ vector
        triples = [
            (chunk, float(score))
            for chunk, score in zip(self.chunks, scores)
            if chunk.spoiler_level <= max_spoiler_level
        ]
        triples.sort(key=lambda t: -t[1])
        return [
            SearchHit(
                chunk_id=c.chunk_id,
                text=c.text,
                fuente=c.fuente,
                url=c.url,
                tier=c.tier,
                origen_canon=c.origen_canon,
                spoiler_level=c.spoiler_level,
                score=s,
            )
            for c, s in triples[:top_k]
        ]


def _chunk(
    chunk_id: str,
    text: str,
    fuente: str,
    tier: int,
    spoiler: int,
    origen: str = "pelicula",
) -> ProcessedChunk:
    return ProcessedChunk(
        chunk_id=chunk_id,
        text=text,
        fuente=fuente,
        url=f"http://x/{chunk_id}",
        n_tokens=len(text.split()),
        tier=tier,
        origen_canon=origen,
        spoiler_level=spoiler,
        spoiler_confidence=1.0,
        spoiler_reasoning="fixture",
    )


def _build_retriever(chunks: list[ProcessedChunk]) -> HybridRetriever:
    emb = _FakeEmbedder()
    store = _FakeStore(chunks, emb)
    return HybridRetriever(
        chunks=chunks,
        store=store,  # type: ignore[arg-type]
        embedder=emb,  # type: ignore[arg-type]
        config=RetrievalConfig(bm25_k=4, dense_k=4, final_n=3),
    )


def test_modo_pre_cine_no_devuelve_spoilers_de_nivel_1_o_2():
    chunks = [
        _chunk("a", "Unai dirige equipo en Vitoria con Esti", "wikipedia_pelicula", 1, 0),
        _chunk("b", "La madre de Unai resulta estar viva al final", "wikipedia_pelicula", 1, 2),
        _chunk("c", "Esti acompaña a Unai a Madrid en pista", "wikipedia_pelicula", 1, 1),
    ]
    r = _build_retriever(chunks)
    hits = r.search("¿quién es Unai?", modo="pre_cine")
    assert hits, "debe devolver al menos un hit"
    for h in hits:
        assert h.spoiler_level == 0, f"filtrado fallido: {h.chunk_id} nivel {h.spoiler_level}"


def test_modo_post_cine_admite_todos_los_niveles():
    chunks = [
        _chunk("a", "Unai en Vitoria", "wikipedia_pelicula", 1, 0),
        _chunk("b", "La madre resulta viva al final", "wikipedia_pelicula", 1, 2),
        _chunk("c", "Esti acompaña a Madrid", "wikipedia_pelicula", 1, 1),
    ]
    r = _build_retriever(chunks)
    hits = r.search("madre", modo="post_cine")
    assert any(h.spoiler_level == 2 for h in hits)


def test_tier_1_antes_que_tier_3_para_misma_query():
    chunks = [
        _chunk("oficial", "Unai dirige el equipo en Vitoria oficial", "wikipedia_pelicula", 1, 0),
        _chunk("fan", "Unai es brutal según los fans en Letterboxd", "letterboxd", 3, 0,
               origen="pelicula"),
    ]
    r = _build_retriever(chunks)
    hits = r.search("Unai", modo="pre_cine")
    assert hits[0].fuente == "wikipedia_pelicula"
    # El de Letterboxd, si aparece, va detrás.
    if len(hits) > 1:
        assert hits[1].tier >= hits[0].tier


def test_modo_durante_admite_nivel_0_y_1_pero_no_2():
    chunks = [
        _chunk("a", "Unai en Vitoria con Esti", "wikipedia_pelicula", 1, 0),
        _chunk("b", "Pista importante en Madrid", "wikipedia_pelicula", 1, 1),
        _chunk("c", "El final revela que la madre vive", "wikipedia_pelicula", 1, 2),
    ]
    r = _build_retriever(chunks)
    hits = r.search("madre", modo="durante")
    for h in hits:
        assert h.spoiler_level <= 1
