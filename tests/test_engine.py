"""Tests del ChatEngine con un cliente Anthropic mockeado."""

from __future__ import annotations

from typing import Any

import numpy as np

from src.chat.engine import ChatEngine
from src.chat.prompts import SYSTEM_PROMPT
from src.chat.session import Session
from src.ingest.pipeline import ProcessedChunk
from src.retrieval.retriever import HybridRetriever, RetrievalConfig


class _FakeEmbedder:
    dim = 4

    def embed_one(self, text: str) -> np.ndarray:
        return self._encode(text)

    def embed(self, texts: list[str], **_) -> np.ndarray:
        return np.vstack([self._encode(t) for t in texts])

    @staticmethod
    def _encode(text: str) -> np.ndarray:
        kws = ["unai", "esti", "madre", "kraken"]
        v = np.array([1.0 if k in text.lower() else 0.0 for k in kws], dtype=np.float32)
        n = np.linalg.norm(v)
        return v / n if n > 0 else v


class _FakeStore:
    def __init__(self, chunks):
        self.chunks = chunks
        self.emb = _FakeEmbedder()
        self._vecs = self.emb.embed([c.text for c in chunks])

    def search(self, vector, *, top_k, max_spoiler_level):
        from src.retrieval.store import SearchHit

        if isinstance(vector, list):
            vector = np.array(vector, dtype=np.float32)
        scores = self._vecs @ vector
        triples = sorted(
            (
                (c, float(s))
                for c, s in zip(self.chunks, scores)
                if c.spoiler_level <= max_spoiler_level
            ),
            key=lambda t: -t[1],
        )
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


class _StubBlock:
    def __init__(self, text: str) -> None:
        self.type = "text"
        self.text = text


class _StubResponse:
    def __init__(self, text: str) -> None:
        self.content = [_StubBlock(text)]


class _StubClient:
    def __init__(self, response_text: str) -> None:
        self._text = response_text
        self.calls: list[dict[str, Any]] = []

        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.calls.append(kwargs)
                return _StubResponse(outer._text)

        self.messages = _Messages()


def _chunk(cid, text, fuente="wikipedia_pelicula", tier=1, sp=0, oc="pelicula"):
    return ProcessedChunk(
        chunk_id=cid,
        text=text,
        fuente=fuente,
        url="http://x",
        n_tokens=len(text.split()),
        tier=tier,
        origen_canon=oc,
        spoiler_level=sp,
        spoiler_confidence=1.0,
        spoiler_reasoning="fixture",
    )


def _retriever(chunks):
    emb = _FakeEmbedder()
    store = _FakeStore(chunks)
    return HybridRetriever(
        chunks=chunks,
        store=store,  # type: ignore[arg-type]
        embedder=emb,  # type: ignore[arg-type]
        config=RetrievalConfig(bm25_k=4, dense_k=4, final_n=3),
    )


def test_engine_inyecta_modo_y_contexto_en_system(tmp_path):
    chunks = [_chunk("a", "Unai dirige a Esti en Vitoria")]
    r = _retriever(chunks)
    client = _StubClient("Es un thriller policíaco español de 2026.")
    eng = ChatEngine(retriever=r, client=client, model="claude-sonnet-4-6")
    sess = Session(no_se_log_path=tmp_path / "ns.jsonl")
    ans = eng.answer("¿De qué va?", sess)
    assert "thriller" in ans.text
    assert len(ans.retrieved) == 1

    assert client.calls, "el modelo debió ser llamado"
    sys_prompt = client.calls[0]["system"]
    assert "NIVEL DE SPOILER ACTIVO: pre_cine" in sys_prompt
    assert "Unai dirige a Esti en Vitoria" in sys_prompt
    # La pregunta del usuario va en messages, no en el system.
    assert client.calls[0]["messages"][0]["content"] == "¿De qué va?"


def test_engine_actualiza_historial(tmp_path):
    r = _retriever([_chunk("a", "Unai dirige a Esti en Vitoria")])
    client = _StubClient("Respuesta válida sobre Unai.")
    eng = ChatEngine(retriever=r, client=client, model="claude-sonnet-4-6")
    sess = Session(no_se_log_path=tmp_path / "ns.jsonl")
    eng.answer("¿quién es Unai?", sess)
    assert len(sess.history) == 2
    assert sess.history[0].role == "user"
    assert sess.history[1].role == "assistant"


def test_system_prompt_contiene_placeholders_correctos():
    assert "{spoiler_level}" in SYSTEM_PROMPT
    assert "{retrieved_context}" in SYSTEM_PROMPT
    assert "{historial}" in SYSTEM_PROMPT
