"""Embeddings con BGE-m3 (sentence-transformers).

Carga lazy del modelo: la primera llamada descarga ~1.5 GB y luego
queda cacheado en ~/.cache/huggingface/.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.config import get_settings

if TYPE_CHECKING:  # evitamos importar torch/sentence-transformers al import
    import numpy as np
    from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class Embedder:
    """Encapsula el modelo BGE-m3."""

    def __init__(self, model_name: str | None = None) -> None:
        cfg = get_settings()
        self.model_name = model_name or cfg.embed_model
        self._model: SentenceTransformer | None = None

    def _ensure_model(self) -> "SentenceTransformer":
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            logger.info("Cargando modelo de embeddings %s ...", self.model_name)
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @property
    def dim(self) -> int:
        return int(self._ensure_model().get_sentence_embedding_dimension())

    def embed(self, texts: list[str], *, batch_size: int = 16) -> "np.ndarray":
        """Devuelve un array (n, dim) de embeddings normalizados (cos sim)."""
        model = self._ensure_model()
        emb = model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        return emb

    def embed_one(self, text: str) -> "np.ndarray":
        return self.embed([text])[0]


_singleton: Embedder | None = None


def get_embedder() -> Embedder:
    """Devuelve un Embedder reutilizable proceso-global."""
    global _singleton
    if _singleton is None:
        _singleton = Embedder()
    return _singleton
