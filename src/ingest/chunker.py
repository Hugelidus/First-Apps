"""Chunker basado en tokens.

Usa tiktoken (cl100k_base, neutro al idioma) para tokenizar y cortar
en bloques de ~500 tokens con 80 de solape, respetando límites de
párrafo cuando es posible.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 500
DEFAULT_OVERLAP = 80
_ENCODER_NAME = "cl100k_base"


class _Tokenizer(Protocol):
    def encode(self, text: str) -> list[int]: ...
    def decode(self, tokens: list[int]) -> str: ...


class _WordTokenizer:
    """Tokenizer fallback basado en palabras.

    No produce IDs reales, pero respeta el contrato encode/decode y permite
    chunkear cuando tiktoken no puede descargar su BPE (sandbox sin red).
    Estima 1.3 tokens reales por palabra para textos en español, que es
    cercano a lo que produce cl100k_base.
    """

    _WORD_RE = re.compile(r"\S+|\n+|\s+")

    def __init__(self) -> None:
        self._vocab: dict[str, int] = {}
        self._inv: list[str] = []

    def _intern(self, word: str) -> int:
        if word not in self._vocab:
            self._vocab[word] = len(self._inv)
            self._inv.append(word)
        return self._vocab[word]

    def encode(self, text: str) -> list[int]:
        # Cada "token" representa ~0.77 palabras → multiplicamos para que
        # n_tokens devuelto se aproxime al de un BPE real.
        words = self._WORD_RE.findall(text)
        ids: list[int] = []
        for w in words:
            ids.append(self._intern(w))
            # Repetimos el último id 0.3 veces de media para inflar el conteo.
            if len(ids) % 10 < 3:
                ids.append(self._intern(w))
        return ids

    def decode(self, tokens: list[int]) -> str:
        # Para reconstruir, deduplicamos repeticiones consecutivas del mismo id.
        out: list[str] = []
        prev: int | None = None
        for t in tokens:
            if t == prev:
                continue
            out.append(self._inv[t])
            prev = t
        return "".join(out)


def _get_tokenizer() -> _Tokenizer:
    """Devuelve tiktoken si está disponible, si no el fallback word-based."""
    try:
        import tiktoken

        return tiktoken.get_encoding(_ENCODER_NAME)
    except Exception as e:  # noqa: BLE001 - cualquier error → fallback
        logger.warning("tiktoken no disponible (%s). Usando tokenizer word-based.", e)
        return _WordTokenizer()


@dataclass(frozen=True)
class Chunk:
    """Trozo de texto listo para embeber."""

    chunk_id: str
    text: str
    fuente: str
    url: str
    n_tokens: int

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "fuente": self.fuente,
            "url": self.url,
            "n_tokens": self.n_tokens,
        }


def _hash(text: str, fuente: str, idx: int) -> str:
    h = hashlib.sha1(f"{fuente}::{idx}::{text}".encode("utf-8")).hexdigest()
    return h[:16]


def _split_paragraphs(text: str) -> list[str]:
    """Divide por dobles saltos de línea, descartando vacíos."""
    parts = re.split(r"\n\s*\n", text.strip())
    return [p.strip() for p in parts if p.strip()]


def chunk_text(
    text: str,
    *,
    fuente: str,
    url: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_OVERLAP,
) -> list[Chunk]:
    """Divide ``text`` en chunks de tamaño en tokens con solape.

    Estrategia:
    1. Concatena párrafos hasta acercarse a ``chunk_size`` tokens.
    2. Si un párrafo solo ya excede el tamaño, lo trocea por tokens.
    3. Genera solape arrastrando los últimos ``overlap`` tokens al
       siguiente chunk.
    """
    if chunk_size <= overlap:
        raise ValueError("chunk_size debe ser mayor que overlap")
    enc = _get_tokenizer()
    paragraphs = _split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[Chunk] = []
    current_tokens: list[int] = []

    def flush() -> None:
        if not current_tokens:
            return
        chunk_text_str = enc.decode(current_tokens).strip()
        if not chunk_text_str:
            return
        idx = len(chunks)
        chunk_id = _hash(chunk_text_str, fuente, idx)
        chunks.append(
            Chunk(
                chunk_id=chunk_id,
                text=chunk_text_str,
                fuente=fuente,
                url=url,
                n_tokens=len(current_tokens),
            )
        )

    for para in paragraphs:
        tokens = enc.encode(para)
        # Párrafo grande: trocear directo respetando solape.
        if len(tokens) > chunk_size:
            flush()
            current_tokens = []
            start = 0
            while start < len(tokens):
                window = tokens[start : start + chunk_size]
                current_tokens = window
                flush()
                start += chunk_size - overlap
            current_tokens = []
            continue
        # Cabe en el chunk actual.
        if len(current_tokens) + len(tokens) <= chunk_size:
            current_tokens.extend(tokens)
        else:
            # No cabe → flush y arranca nuevo chunk con solape.
            flush()
            tail = current_tokens[-overlap:] if overlap else []
            current_tokens = [*tail, *tokens]

    flush()
    return chunks
