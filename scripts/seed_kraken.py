"""Seed end-to-end: scrape → chunkea → clasifica → embebe → upserta en Qdrant.

Uso:
    uv run python scripts/seed_kraken.py [--skip-scrape] [--recreate]

Requiere:
- ``ANTHROPIC_API_KEY`` en ``.env`` (para el clasificador de spoilers).
- Qdrant corriendo en ``QDRANT_URL`` (por defecto localhost:6333).

``--skip-scrape``: salta la fase de scraping (útil si ya tienes los
JSON crudos en ``data/raw/`` o si vienes de ``bootstrap_canonical.py``).

``--recreate``: borra y recrea la colección antes de upsertar.
"""

from __future__ import annotations

import argparse
import logging
import sys

from src.config import setup_logging
from src.ingest.pipeline import process_documents
from src.ingest.sources import festival_malaga, wikipedia_novela, wikipedia_pelicula
from src.retrieval.embed import get_embedder
from src.retrieval.store import KrakenStore

logger = logging.getLogger(__name__)


def _scrape_all() -> None:
    """Ejecuta los 3 scrapers mínimos."""
    for mod, name in (
        (wikipedia_pelicula, "Wikipedia (película)"),
        (wikipedia_novela, "Wikipedia (novela)"),
        (festival_malaga, "Festival de Málaga"),
    ):
        try:
            mod.fetch()
        except Exception as e:  # noqa: BLE001
            logger.error("Falló %s: %s", name, e)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-scrape", action="store_true", help="No re-scrapear")
    parser.add_argument(
        "--recreate", action="store_true", help="Borrar y recrear la colección"
    )
    args = parser.parse_args()

    setup_logging()

    if not args.skip_scrape:
        logger.info("Fase 1: scraping de fuentes...")
        _scrape_all()
    else:
        logger.info("Fase 1: scraping omitido (--skip-scrape).")

    logger.info("Fase 2: chunkeando y clasificando spoilers...")
    chunks = process_documents()
    if not chunks:
        logger.error("Sin chunks producidos. Aborta.")
        return 1
    logger.info("Producidos %d chunks.", len(chunks))

    logger.info("Fase 3: embeddings con BGE-m3...")
    embedder = get_embedder()
    vectors = embedder.embed([c.text for c in chunks])

    logger.info("Fase 4: upsert en Qdrant...")
    store = KrakenStore(vector_size=embedder.dim)
    store.ensure_collection(recreate=args.recreate)
    n = store.upsert_chunks(chunks, vectors)
    logger.info("Total puntos en colección: %d", store.count())
    logger.info("OK. %d puntos upsertados.", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
