"""Siembra un corpus mínimo offline con datos públicos.

Útil para probar el chat sin esperar a tener red para los scrapers.
Crea ``data/raw/canonical_*.json`` con texto canónico (premisa,
ficha técnica, contexto de la saga). NO sustituye al scraping real:
es solo para que el sistema arranque con algo razonable mientras
no haya corpus completo.

Uso:
    uv run python scripts/bootstrap_canonical.py
    uv run python scripts/seed_kraken.py --skip-scrape

Las fuentes ``canonical_*`` están en CANON_BY_FUENTE / TIER_BY_FUENTE
con tier=1, origen_canon adecuado.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.config import RAW_DIR, setup_logging

logger = logging.getLogger(__name__)


CANONICAL_FICHA = (
    "Kraken. El libro negro de las horas es una película española de 2026, "
    "del género thriller policíaco, dirigida por Manuel Sanabria y Joaquín Llamas. "
    "Su estreno en cines españoles fue el 24 de abril de 2026, distribuida por "
    "Vértice 360. La producción corrió a cargo de Isla Audiovisual y Zebra, con "
    "la participación de Prime Video y RTVE.\n\n"
    "El reparto principal está encabezado por Alejo Sauras como Unai López de Ayala, "
    "alias Kraken, junto a Maggie Civantos en el papel de Esti, su compañera. "
    "Completan el reparto Natalia Rodríguez y Natalia Millán, entre otros."
)

CANONICAL_PREMISA = (
    "La premisa pública del filme es la siguiente: Unai, exinspector y experto en "
    "perfiles criminales, recibe una llamada anónima en la que se le anuncia que "
    "tiene siete días para encontrar el legendario Libro Negro de las Horas. Si no "
    "lo consigue, su madre, a la que creía muerta hace décadas, morirá. Junto a su "
    "compañera Esti, Unai recorre Vitoria y Madrid entre coleccionistas y "
    "bibliófilos peligrosos.\n\n"
    "La narración mezcla dos líneas temporales: el presente (Vitoria y Madrid en "
    "2022) y una línea ambientada en los años 70 que aporta contexto al pasado de "
    "los personajes. El tono es de thriller con elementos de novela negra, "
    "característico de la saga literaria en la que se basa."
)

CANONICAL_SAGA = (
    "Kraken. El libro negro de las horas es la adaptación al cine del cuarto título "
    "de la saga del inspector Unai López de Ayala, escrita por Eva García Sáenz de "
    "Urturi. La saga arrancó con la 'Trilogía de la Ciudad Blanca' (compuesta por "
    "'El silencio de la ciudad blanca', 'Los ritos del agua' y 'Los señores del "
    "tiempo') y continúa con esta novela. Los libros previos han sido publicados "
    "durante años y cuentan con amplia comunidad lectora en español.\n\n"
    "Para entender plenamente las relaciones entre Unai y los personajes "
    "secundarios — incluida Esti — ayuda haber leído los libros previos, aunque "
    "la película funciona como historia autocontenida. Las películas previas "
    "anteriores ('El silencio de la ciudad blanca', 2019, y otras adaptaciones) "
    "contextualizan al protagonista pero no son requisito imprescindible."
)


CANONICAL_DOCS = [
    {
        "fuente": "canonical_ficha",
        "title": "Kraken — Ficha técnica",
        "url": "internal://canonical/ficha",
        "text": CANONICAL_FICHA,
    },
    {
        "fuente": "canonical_premisa",
        "title": "Kraken — Premisa pública",
        "url": "internal://canonical/premisa",
        "text": CANONICAL_PREMISA,
    },
    {
        "fuente": "canonical_saga",
        "title": "Kraken — Contexto de la saga",
        "url": "internal://canonical/saga",
        "text": CANONICAL_SAGA,
    },
]


def main() -> int:
    setup_logging()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for doc in CANONICAL_DOCS:
        payload = {
            **doc,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
        path = RAW_DIR / f"{doc['fuente']}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Escrito %s (%d chars)", path, len(doc["text"]))
    logger.info(
        "Hecho. Ahora ejecuta: uv run python scripts/seed_kraken.py --skip-scrape"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
