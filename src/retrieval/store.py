"""Wrapper de Qdrant para la colección Kraken."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Iterable

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from src.config import get_settings
from src.ingest.pipeline import ProcessedChunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchHit:
    """Resultado de una búsqueda dense."""

    chunk_id: str
    text: str
    fuente: str
    url: str
    tier: int
    origen_canon: str
    spoiler_level: int
    score: float


def _payload_from(chunk: ProcessedChunk) -> dict:
    return {
        "chunk_id": chunk.chunk_id,
        "text": chunk.text,
        "fuente": chunk.fuente,
        "url": chunk.url,
        "tier": chunk.tier,
        "origen_canon": chunk.origen_canon,
        "spoiler_level": chunk.spoiler_level,
    }


def _point_id_for(chunk_id: str) -> str:
    """Convierte chunk_id (16 hex chars) en un UUID determinista para Qdrant."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"chunk:{chunk_id}"))


class KrakenStore:
    """Wrapper sobre QdrantClient con la colección de Kraken."""

    def __init__(
        self,
        client: QdrantClient | None = None,
        collection: str | None = None,
        vector_size: int | None = None,
    ) -> None:
        cfg = get_settings()
        self.client = client or QdrantClient(url=cfg.qdrant_url)
        self.collection = collection or cfg.qdrant_collection
        self.vector_size = vector_size or cfg.embed_dim

    def ensure_collection(self, recreate: bool = False) -> None:
        """Crea la colección si no existe. Si ``recreate``, la borra y recrea."""
        existing = {c.name for c in self.client.get_collections().collections}
        if self.collection in existing:
            if not recreate:
                return
            self.client.delete_collection(self.collection)
        self.client.create_collection(
            collection_name=self.collection,
            vectors_config=qm.VectorParams(
                size=self.vector_size, distance=qm.Distance.COSINE
            ),
        )
        # Índices de payload para filtros eficientes.
        for field, schema in (
            ("spoiler_level", qm.PayloadSchemaType.INTEGER),
            ("tier", qm.PayloadSchemaType.INTEGER),
            ("origen_canon", qm.PayloadSchemaType.KEYWORD),
            ("fuente", qm.PayloadSchemaType.KEYWORD),
        ):
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name=field,
                field_schema=schema,
            )
        logger.info("Colección '%s' creada (dim=%d)", self.collection, self.vector_size)

    def upsert_chunks(self, chunks: Iterable[ProcessedChunk], vectors) -> int:
        """Inserta o actualiza puntos. ``vectors`` es ndarray (n, dim)."""
        points: list[qm.PointStruct] = []
        for chunk, vec in zip(chunks, vectors):
            points.append(
                qm.PointStruct(
                    id=_point_id_for(chunk.chunk_id),
                    vector=vec.tolist(),
                    payload=_payload_from(chunk),
                )
            )
        if not points:
            return 0
        self.client.upsert(collection_name=self.collection, points=points)
        logger.info("Upserted %d puntos en '%s'", len(points), self.collection)
        return len(points)

    def search(
        self,
        vector,
        *,
        top_k: int = 8,
        max_spoiler_level: int = 2,
    ) -> list[SearchHit]:
        """Búsqueda dense con filtro por nivel máximo de spoiler."""
        flt = qm.Filter(
            must=[
                qm.FieldCondition(
                    key="spoiler_level",
                    range=qm.Range(lte=max_spoiler_level),
                )
            ]
        )
        results = self.client.search(
            collection_name=self.collection,
            query_vector=vector.tolist() if hasattr(vector, "tolist") else list(vector),
            query_filter=flt,
            limit=top_k,
            with_payload=True,
        )
        hits: list[SearchHit] = []
        for r in results:
            p = r.payload or {}
            hits.append(
                SearchHit(
                    chunk_id=p.get("chunk_id", ""),
                    text=p.get("text", ""),
                    fuente=p.get("fuente", ""),
                    url=p.get("url", ""),
                    tier=int(p.get("tier", 3)),
                    origen_canon=str(p.get("origen_canon", "pelicula")),
                    spoiler_level=int(p.get("spoiler_level", 0)),
                    score=float(r.score),
                )
            )
        return hits

    def count(self) -> int:
        return self.client.count(collection_name=self.collection, exact=True).count
