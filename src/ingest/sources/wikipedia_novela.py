"""Scraper de la Wikipedia ES para la novela 'El libro negro de las horas'."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.config import RAW_DIR
from src.ingest.sources.base import HttpClient
from src.ingest.sources.wikipedia_pelicula import ENDPOINT

logger = logging.getLogger(__name__)

TITLE = "El libro negro de las horas"
FUENTE = "wikipedia_novela"


def fetch(title: str = TITLE) -> dict:
    """Descarga el extracto plano y guarda JSON crudo."""
    url = ENDPOINT.format(title=title.replace(" ", "_"))
    with HttpClient() as http:
        result = http.get(url)
    payload = json.loads(result.text)
    pages = payload.get("query", {}).get("pages", {})
    if not pages:
        raise RuntimeError(f"Wikipedia no devolvió páginas para '{title}'")
    page = next(iter(pages.values()))
    if "missing" in page:
        raise RuntimeError(
            f"Página '{title}' no existe en es.wikipedia. Revisa el título exacto."
        )
    text = page.get("extract", "").strip()
    if not text:
        raise RuntimeError(f"Wikipedia devolvió extracto vacío para '{title}'")

    doc = {
        "fuente": FUENTE,
        "url": page.get("fullurl", url),
        "title": page.get("title", title),
        "text": text,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }
    out = RAW_DIR / f"{FUENTE}.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Guardado %s (%d chars)", out, len(text))
    return doc


if __name__ == "__main__":
    from src.config import setup_logging

    setup_logging()
    fetch()
