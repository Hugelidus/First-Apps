"""Pipeline de procesado: lee data/raw/, chunkea, etiqueta y escribe chunks.jsonl."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from src.config import PROCESSED_DIR, RAW_DIR
from src.ingest.canon_assigner import OrigenCanon, canon_for
from src.ingest.chunker import Chunk, chunk_text
from src.ingest.spoiler_classifier import SpoilerClassifier
from src.ingest.tier_assigner import tier_for

logger = logging.getLogger(__name__)

CHUNKS_PATH = PROCESSED_DIR / "chunks.jsonl"


@dataclass(frozen=True)
class ProcessedChunk:
    """Chunk listo para embeber, con todos los metadatos."""

    chunk_id: str
    text: str
    fuente: str
    url: str
    n_tokens: int
    tier: int
    origen_canon: OrigenCanon
    spoiler_level: int
    spoiler_confidence: float
    spoiler_reasoning: str

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "text": self.text,
            "fuente": self.fuente,
            "url": self.url,
            "n_tokens": self.n_tokens,
            "tier": self.tier,
            "origen_canon": self.origen_canon,
            "spoiler_level": self.spoiler_level,
            "spoiler_confidence": self.spoiler_confidence,
            "spoiler_reasoning": self.spoiler_reasoning,
        }


def _iter_raw_documents(raw_dir: Path) -> Iterable[dict]:
    for p in sorted(raw_dir.glob("*.json")):
        if p.name.startswith("_") or p.name == ".gitkeep":
            continue
        try:
            yield json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            logger.error("JSON inválido en %s: %s", p, e)


def process_documents(
    raw_dir: Path = RAW_DIR,
    out_path: Path = CHUNKS_PATH,
    classifier: SpoilerClassifier | None = None,
) -> list[ProcessedChunk]:
    """Procesa todos los JSON crudos en ``raw_dir`` y escribe ``out_path``.

    Si ``classifier`` es None, instancia uno con la API key del entorno.
    """
    classifier = classifier or SpoilerClassifier()

    processed: list[ProcessedChunk] = []
    for doc in _iter_raw_documents(raw_dir):
        fuente = doc["fuente"]
        text = doc["text"]
        url = doc.get("url", "")
        try:
            tier = tier_for(fuente)
            origen = canon_for(fuente)
        except KeyError as e:
            logger.error("Documento descartado: %s", e)
            continue

        chunks: list[Chunk] = chunk_text(text, fuente=fuente, url=url)
        logger.info("%s → %d chunks", fuente, len(chunks))
        for c in chunks:
            label = classifier.classify(c.text)
            processed.append(
                ProcessedChunk(
                    chunk_id=c.chunk_id,
                    text=c.text,
                    fuente=c.fuente,
                    url=c.url,
                    n_tokens=c.n_tokens,
                    tier=tier,
                    origen_canon=origen,
                    spoiler_level=label.level,
                    spoiler_confidence=label.confidence,
                    spoiler_reasoning=label.reasoning,
                )
            )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for pc in processed:
            f.write(json.dumps(pc.to_dict(), ensure_ascii=False) + "\n")
    logger.info("Escritos %d chunks en %s", len(processed), out_path)
    return processed


def load_processed_chunks(path: Path = CHUNKS_PATH) -> list[ProcessedChunk]:
    """Lee ``chunks.jsonl`` y devuelve los ProcessedChunk."""
    chunks: list[ProcessedChunk] = []
    if not path.exists():
        return chunks
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            chunks.append(ProcessedChunk(**d))
    return chunks
