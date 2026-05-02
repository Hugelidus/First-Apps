"""Scraper de la ficha del Festival de Málaga.

NOTA: la URL exacta de la ficha de Kraken en festivaldemalaga.com debe
verificarse manualmente la primera vez. Si no es la que está aquí por
defecto, exporta ``FESTIVAL_MALAGA_URL`` antes de ejecutar.

Estrategia: parseamos el HTML con selectolax y extraemos el bloque
principal (sinopsis + ficha técnica) por selectores típicos del sitio.
Si la estructura cambia, este scraper falla con un error claro.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from selectolax.parser import HTMLParser

from src.config import RAW_DIR
from src.ingest.sources.base import HttpClient

logger = logging.getLogger(__name__)

DEFAULT_URL = "https://festivaldemalaga.com/peliculas/kraken-el-libro-negro-de-las-horas"
FUENTE = "festival_malaga"


def _extract_text(html: str) -> str:
    """Extrae el texto principal de la ficha."""
    tree = HTMLParser(html)
    candidates = [
        "main",
        "article",
        ".pelicula-detalle",
        ".sinopsis",
        ".ficha-tecnica",
        "#content",
    ]
    parts: list[str] = []
    for sel in candidates:
        for node in tree.css(sel):
            txt = node.text(separator="\n", strip=True)
            if txt and txt not in parts:
                parts.append(txt)
    if not parts:
        # Fallback: texto del body completo, limpio.
        body = tree.css_first("body")
        if body is not None:
            parts.append(body.text(separator="\n", strip=True))
    return "\n\n".join(parts).strip()


def fetch(url: str | None = None) -> dict:
    """Descarga la ficha y guarda JSON crudo con texto extraído."""
    target = url or os.environ.get("FESTIVAL_MALAGA_URL", DEFAULT_URL)
    with HttpClient() as http:
        result = http.get(target)
    text = _extract_text(result.text)
    if len(text) < 200:
        raise RuntimeError(
            f"Texto extraído sospechosamente corto ({len(text)} chars). "
            "¿Cambió la estructura del sitio o la URL es incorrecta?"
        )
    doc = {
        "fuente": FUENTE,
        "url": target,
        "title": "Ficha Festival de Málaga — Kraken. El libro negro de las horas",
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
