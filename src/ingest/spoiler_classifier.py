"""Clasificador de nivel de spoiler con Claude Haiku.

Para cada chunk:
- Carga la rúbrica + sinopsis oficial como bloque cacheable (prompt
  caching de Anthropic) para no pagar el contexto fijo en cada llamada.
- Devuelve ``(level, confidence, reasoning)``.
- Cachea el resultado por hash del chunk en disco para no reclasificar.
- Loguea casos con ``confidence < 0.7`` para revisión manual.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from anthropic import Anthropic

from src.config import DATA_DIR, get_settings

logger = logging.getLogger(__name__)

CACHE_PATH = DATA_DIR / "processed" / "spoiler_cache.json"
BORDERLINE_PATH = DATA_DIR / "processed" / "spoiler_borderline.jsonl"

SINOPSIS_OFICIAL = (
    "Unai, exinspector y experto en perfiles criminales, recibe una llamada "
    "anónima: tiene 7 días para encontrar el legendario Libro Negro de las "
    "Horas, o su madre — a la que creía muerta hace décadas — morirá. Junto "
    "a Esti recorre Vitoria y Madrid entre coleccionistas y bibliófilos "
    "peligrosos. Mezcla presente (Vitoria/Madrid, 2022) con una línea "
    "temporal en los años 70."
)

RUBRICA = f"""Eres un clasificador de nivel de spoiler para una película. Trabajas
en español. Te paso la sinopsis oficial pública (lo que cualquiera puede
leer en tráiler/cartelera) y un fragmento de información sobre la
película o su novela original. Devuelves cuánto revela el fragmento
respecto a esa sinopsis.

# RÚBRICA (3 niveles)

- 0 = PREMISA PÚBLICA. El fragmento solo contiene información que ya está
  en la sinopsis oficial, en la ficha técnica (reparto, equipo, año,
  género, premios) o son datos ampliamente difundidos antes del estreno.
  No revela giros, identidades ocultas, muertes, traiciones, móvil del
  villano ni final.

- 1 = DESARROLLO INTERMEDIO. El fragmento añade detalles del primer/segundo
  acto que la sinopsis no cuenta: nuevos personajes secundarios, escenas
  concretas no mostradas en el tráiler, contexto histórico relevante,
  pistas. NO revela el desenlace ni el gran giro central.

- 2 = GIROS / FINAL. El fragmento revela:
  - el final, el desenlace, quién muere o sobrevive,
  - la identidad real del villano o de un personaje oculto,
  - la traición o el gran giro,
  - revelaciones sobre la madre de Unai o sobre conexiones con libros
    previos de la saga que dependan del clímax,
  - el destino del Libro Negro de las Horas.

# SINOPSIS OFICIAL

{SINOPSIS_OFICIAL}

# CÓMO DECIDIR

- Si dudas entre 1 y 2, elige 2 (somos conservadores: mejor pasarse).
- Si el fragmento solo da reparto/equipo/premios/festivales → 0.
- Si describe escenas del tercer acto, identidades secretas o el final → 2.
- Si describe contexto, primer acto o subtramas sin desvelar el final → 1.

# FORMATO DE SALIDA

Devuelve EXCLUSIVAMENTE un JSON con esta forma, sin texto adicional:

{{"level": 0|1|2, "confidence": 0.0-1.0, "reasoning": "una frase breve"}}
"""


@dataclass(frozen=True)
class SpoilerLabel:
    level: int
    confidence: float
    reasoning: str

    def to_dict(self) -> dict:
        return {
            "level": self.level,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }


def _chunk_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_cache() -> dict[str, dict]:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            logger.warning("Caché de spoilers corrupta, se reinicia.")
    return {}


def _save_cache(cache: dict[str, dict]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _log_borderline(chunk_text: str, label: SpoilerLabel) -> None:
    BORDERLINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BORDERLINE_PATH.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "level": label.level,
                    "confidence": label.confidence,
                    "reasoning": label.reasoning,
                    "text": chunk_text[:500],
                },
                ensure_ascii=False,
            )
            + "\n"
        )


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_response(text: str) -> SpoilerLabel:
    """Extrae el JSON de la respuesta del modelo. Si falla, devuelve nivel 2 conservador."""
    m = _JSON_RE.search(text)
    if not m:
        logger.error("Respuesta sin JSON detectable: %r", text[:200])
        return SpoilerLabel(level=2, confidence=0.0, reasoning="parse_error")
    try:
        data = json.loads(m.group(0))
        level = int(data["level"])
        if level not in (0, 1, 2):
            raise ValueError(f"level inválido: {level}")
        return SpoilerLabel(
            level=level,
            confidence=float(data.get("confidence", 0.5)),
            reasoning=str(data.get("reasoning", ""))[:300],
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
        logger.error("JSON inválido del clasificador (%s): %r", e, text[:200])
        return SpoilerLabel(level=2, confidence=0.0, reasoning="parse_error")


class SpoilerClassifier:
    """Clasificador con caché en disco y prompt caching del bloque fijo."""

    def __init__(
        self,
        client: Anthropic | None = None,
        model: str | None = None,
        cache_path: Path = CACHE_PATH,
    ) -> None:
        cfg = get_settings()
        self.client = client or Anthropic(api_key=cfg.anthropic_api_key)
        self.model = model or cfg.spoiler_model
        self.cache_path = cache_path
        self._cache = _load_cache() if cache_path == CACHE_PATH else {}

    def classify(self, chunk_text: str) -> SpoilerLabel:
        """Devuelve el nivel de spoiler del chunk, con caché por hash."""
        h = _chunk_hash(chunk_text)
        if h in self._cache:
            return SpoilerLabel(**self._cache[h])

        resp = self.client.messages.create(
            model=self.model,
            max_tokens=300,
            system=[
                {
                    "type": "text",
                    "text": RUBRICA,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
                {
                    "role": "user",
                    "content": (
                        "FRAGMENTO A CLASIFICAR:\n\n"
                        f"{chunk_text}\n\n"
                        "Responde SOLO con el JSON descrito."
                    ),
                }
            ],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )
        label = _parse_response(text)

        self._cache[h] = label.to_dict()
        _save_cache(self._cache)
        if label.confidence < 0.7:
            _log_borderline(chunk_text, label)
        return label
