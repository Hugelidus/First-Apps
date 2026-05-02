# PLAN.md — CinemaIA MVP1 (Kraken)

Plan de implementación por fases. Cada fase termina con un commit.
**No avanzo a la siguiente fase sin tu OK explícito.**

Estado:
- [x] Fase 0 — Limpieza del repo y documentación
- [ ] Fase 1 — Bootstrap (deps, Docker, .env)
- [ ] Fase 2 — Ingesta de fuentes
- [ ] Fase 3 — Pipeline de procesado (chunker, tiers, canon, spoilers)
- [ ] Fase 4 — Embeddings + storage en Qdrant
- [ ] Fase 5 — Retriever híbrido con filtros
- [ ] Fase 6 — Chat engine
- [ ] Fase 7 — CLI
- [ ] Fase 8 — Acceptance test manual con las 8 preguntas

---

## Fase 0 — Limpieza y docs (HECHO antes de pedir OK)

Borrado de la base anterior (proyecto sports-forecasting) y guardado de
contexto.

Archivos:
- `CLAUDE.md` — copia íntegra del documento de proyecto.
- `PLAN.md` — este archivo.
- `.gitignore` — añadir `data/raw/`, `*.cache/`, `.uv-cache/`, etc.

Commit: `chore: limpia repo previo y documenta proyecto CinemaIA`.

---

## Fase 1 — Bootstrap

Objetivo: que `uv sync && docker compose up -d` deje un entorno listo,
con Qdrant accesible en `localhost:6333`.

Archivos a crear:
- `pyproject.toml` — Python 3.11+, deps mínimas:
  - runtime: `anthropic`, `qdrant-client`, `sentence-transformers`,
    `httpx`, `selectolax`, `beautifulsoup4`, `rank_bm25`, `typer`,
    `python-dotenv`, `pydantic`, `tiktoken` (para contar tokens en chunker).
  - dev: `pytest`, `pytest-asyncio`, `ruff`.
- `.env.example` — `ANTHROPIC_API_KEY=`, `QDRANT_URL=http://localhost:6333`,
  `QDRANT_COLLECTION=kraken`, `LOG_LEVEL=INFO`.
- `docker-compose.yml` — un servicio `qdrant` con volumen persistente.
- `README.md` — cómo levantar Qdrant, correr el seed, abrir el chat.
- `src/__init__.py` y `src/config.py` — carga de settings con
  `pydantic-settings` o `os.environ` simple.
- `data/raw/.gitkeep`, `data/processed/.gitkeep`.

Verificación: `docker compose up -d`, `curl localhost:6333/healthz` → 200.

Commit: `chore(bootstrap): pyproject, docker-compose qdrant, config base`.

---

## Fase 2 — Ingesta de fuentes

Objetivo: producir JSON crudos y normalizados en `data/raw/` para las
3 fuentes mínimas de §7.

Archivos:
- `src/ingest/sources/base.py` — clase `Source` con `fetch()` y
  cliente `httpx` con rate-limit 1 req/s + User-Agent identificable
  (`CinemaIA-MVP/0.1 (+contacto)`) + caché disco por URL hash.
- `src/ingest/sources/wikipedia_pelicula.py` — Wikipedia ES de la peli
  (vía API REST `/page/summary` + `/page/html` para el cuerpo).
- `src/ingest/sources/wikipedia_novela.py` — Wikipedia ES de la novela
  "El libro negro de las horas".
- `src/ingest/sources/festival_malaga.py` — ficha del Festival de Málaga
  (HTML, parseo con `selectolax`).
- `scripts/seed_kraken.py` (esqueleto, solo ingest aquí).

Salida: un JSON por documento con `{url, title, fetched_at, html, text,
fuente}` en `data/raw/<fuente>__<slug>.json`.

Commit: `feat(ingest): scrapers wiki peli, wiki novela, festival málaga`.

**Nota sobre robots.txt**: implementación incluye chequeo previo con
`urllib.robotparser`. Si una fuente prohíbe el path, se loguea y se
salta — no se scrapea.

---

## Fase 3 — Pipeline de procesado

Objetivo: convertir los JSON crudos en chunks etiquetados listos
para embeber, en `data/processed/chunks.jsonl`.

Archivos:
- `src/ingest/chunker.py` — chunker por tokens (tiktoken), 500/80,
  respeta límites de párrafo cuando puede.
- `src/ingest/tier_assigner.py` — diccionario `dominio → tier`.
- `src/ingest/canon_assigner.py` — diccionario `slug_fuente → origen_canon`.
  Wikipedia peli y festival → `pelicula`. Wikipedia novela → `novela`.
- `src/ingest/spoiler_classifier.py` — llamada a Claude Haiku con
  rúbrica + sinopsis oficial. Caché en disco por hash de chunk.
  Devuelve `(level: 0|1|2, confidence: float, reasoning: str)`.
  Loguea casos con confidence < 0.7.
- `src/ingest/pipeline.py` — orquesta: lee `data/raw/`, chunkea,
  asigna tier/canon, clasifica spoilers, escribe `data/processed/chunks.jsonl`.
- `tests/fixtures/spoilers/` — ~10 chunks de Kraken etiquetados a mano
  (algunos 0, algunos 1, algunos 2).
- `tests/test_spoiler_classifier.py` — verifica que el clasificador
  acierta en los fixtures (acepta 1 fallo de 10 como margen).
- `tests/test_chunker.py` — tamaño y solape correctos.

Commit: `feat(ingest): chunker, tier/canon assigners, spoiler classifier`.

---

## Fase 4 — Embeddings y storage

Objetivo: tener Qdrant con la colección `kraken` poblada.

Archivos:
- `src/retrieval/embed.py` — wrapper de `sentence-transformers` con
  modelo `BAAI/bge-m3`. Carga lazy. Función `embed(texts: list[str]) -> np.ndarray`.
- `src/retrieval/store.py` — wrapper Qdrant: `ensure_collection`,
  `upsert_chunks`, `search(vector, top_k, filters)`. Payload por punto:
  `{spoiler_level, tier, origen_canon, fuente, url, text}`.
  Tamaño vector = 1024 (BGE-m3).
- `scripts/seed_kraken.py` (completo) — carga `chunks.jsonl`, embebe,
  upserta en Qdrant.
- `tests/test_store.py` — colección up/down, upsert, search básica
  con un Qdrant de prueba (skip si no hay docker corriendo).

Verificación: `python scripts/seed_kraken.py` deja N puntos en Qdrant.

Commit: `feat(retrieval): embeddings BGE-m3 y storage Qdrant`.

---

## Fase 5 — Retriever híbrido

Objetivo: dada `query` y `modo`, devolver los 5 chunks más relevantes
con `spoiler_level <= modo`.

Archivos:
- `src/retrieval/retriever.py`:
  - BM25 sobre el texto plano (mantenido en memoria desde
    `chunks.jsonl` o reconstruido al arrancar).
  - Dense via Qdrant `search` con filtro `spoiler_level <= modo`.
  - Unión + dedup por chunk_id.
  - `rerank.py` ordena: tier asc, luego score dense desc.
  - Devuelve top 5 con metadatos completos para el prompt.
- `src/retrieval/rerank.py` — función pura, separada para testabilidad.
- `tests/test_retriever.py`:
  - Filtro de spoiler funciona (modo `pre_cine` nunca devuelve nivel 1 ó 2).
  - Una query "directores" devuelve un chunk tier 1 antes que uno tier 3.

Commit: `feat(retrieval): retriever híbrido BM25+dense con rerank por tier`.

---

## Fase 6 — Chat engine

Objetivo: una función `answer(query, session) -> Answer` que construye
el prompt, llama a Claude Sonnet y devuelve la respuesta + chunks
usados.

Archivos:
- `src/chat/prompts.py` — `SYSTEM_PROMPT` literal de §8 con
  placeholders. Función `format_context(chunks) -> str` que produce
  los bloques `TIER:.. SPOILER:.. ORIGEN_CANON:.. \n texto \n---`.
- `src/chat/session.py`:
  - `Session(modo, history, no_se_log_path)`.
  - `set_modo(modo)`: cambia sin perder historial.
  - `append_turn(user, assistant)`.
  - `log_no_se(query)` cuando la respuesta empieza con la frase
    "No tengo información fiable...".
- `src/chat/engine.py`:
  - `answer(query, session, retriever, llm_client)`.
  - Construye system con `format_context(retrieved)` y
    `historial = session.render_last_n(6)`.
  - Llama a `claude-sonnet-4-6` con `messages=[{role:user, content:query}]`.
  - Detecta "no sé" en la respuesta y loguea.
  - Devuelve `Answer(text, retrieved_chunks)`.

Commit: `feat(chat): engine, session y prompts`.

---

## Fase 7 — CLI

Objetivo: chat interactivo con comandos.

Archivos:
- `src/cli.py` con `typer`:
  - `cinemaia chat --modo pre|durante|post` (default `pre`).
  - Loop de input. Comandos:
    - `:modo pre|durante|post` cambia nivel sin reiniciar.
    - `:debug on|off` togglea mostrar los chunks recuperados con su
      tier/spoiler/fuente cada turno.
    - `:nose` muestra/exporta el log de "no sé" actual.
    - `:salir` o Ctrl-D termina.
  - Salida formateada simple. Sin TUI fancy.

Commit: `feat(cli): chat interactivo con comandos de modo, debug y nose`.

---

## Fase 8 — Acceptance test manual

Objetivo: pasar las 8 preguntas de §10 en sus 3 modos según corresponda.

Pasos:
1. `docker compose up -d`
2. `python scripts/seed_kraken.py` (con las 3 fuentes)
3. `cinemaia chat --modo pre` → preguntas pre_cine
4. `:modo durante` → preguntas durante
5. `:modo post` → preguntas post_cine
6. Anotar fallos en `docs/acceptance-report.md`.

Si todo OK: tag `mvp1-fase8-ok` y reporte final. Si hay fallos:
diagnóstico (¿retriever?, ¿spoiler classifier?, ¿prompt?) y propuesta
de fix.

Commit final: `docs: acceptance report MVP1 Kraken`.

---

## Riesgos identificados y mitigación

1. **Cobertura escasa de la peli en Wikipedia ES recién estrenada**.
   Si la página de la peli es minúscula, lo aviso y propongo añadir
   SensaCine y FilmAffinity en una fase 2.5 antes del retriever.
2. **Spoiler classifier con Haiku puede fallar en chunks borderline**
   (transición libro→peli). Mitigación: confidence + revisión manual
   del log antes de la fase 4.
3. **BGE-m3 tarda en cargar la primera vez (~1.5GB)**. Aviso en README;
   primera ejecución es lenta.
4. **robots.txt de SensaCine/FilmAffinity puede bloquear**. Si ocurre,
   esas fuentes quedan fuera y el MVP usa solo Wikipedia + Festival.
   Sin scraping prohibido bajo ningún concepto.

---

## Preguntas abiertas (decidir antes de fase 2)

- ¿Quieres que añada SensaCine y FilmAffinity ya en fase 2, o las
  reservamos para una fase 2.5 según el resultado del retriever con
  solo las 3 mínimas? Mi recomendación: solo las 3 mínimas en fase 2,
  evaluamos cobertura, decidimos.
- Confirmación: ¿el repo se llamará `kraken-mvp` lógicamente pero
  vivirá en `hugelidus/first-apps` rama `claude/cinemaIA-kraken-mvp-ntjgS`?
  No renombro el repo de GitHub (no tengo permiso para eso).
