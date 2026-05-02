# CinemaIA — MVP1 (Kraken)

Chat por CLI con manejo de spoilers por niveles sobre la película
**"Kraken. El libro negro de las horas"** (España, 2026, dirigida por
Manuel Sanabria y Joaquín Llamas, basada en la novela homónima de Eva
García Sáenz de Urturi).

Arquitectura: RAG con Qdrant + embeddings BGE-m3 + Claude. Sin
LangChain, sin LlamaIndex.

> ⚠️ Estado: **fase 1 — bootstrap**. Aún no hay datos cargados ni chat
> funcional. Ver `PLAN.md` para el plan completo.

---

## Requisitos

- Python **3.11+**
- [`uv`](https://docs.astral.sh/uv/) para gestión de dependencias
- Docker + Docker Compose (para Qdrant)
- Una `ANTHROPIC_API_KEY` válida

## Bootstrap

```bash
# 1. Clonar y entrar
git clone https://github.com/Hugelidus/First-Apps.git cinemaia
cd cinemaia
git checkout claude/cinemaIA-kraken-mvp-ntjgS

# 2. Configurar .env
cp .env.example .env
# Edita .env y rellena ANTHROPIC_API_KEY

# 3. Instalar dependencias
uv sync

# 4. Levantar Qdrant
docker compose up -d
curl -fsS http://localhost:6333/healthz   # → "healthz check passed"
```

La primera vez que se use el embedder, `sentence-transformers`
descargará BGE-m3 (~1.5 GB) en `~/.cache/huggingface/`.

## Uso (cuando esté disponible — fases 6+)

```bash
# Poblar la base con las 3 fuentes mínimas
uv run python scripts/seed_kraken.py

# Abrir el chat
uv run cinemaia chat --modo pre
```

Comandos del chat:

| Comando | Acción |
|---|---|
| `:modo pre\|durante\|post` | Cambia el nivel de spoiler sin reiniciar |
| `:debug on\|off` | Muestra los chunks recuperados con tier/spoiler |
| `:nose` | Vuelca el log de preguntas sin respuesta |
| `:salir` | Termina la sesión |

## Estructura del repo

```
.
├── CLAUDE.md           # Contexto y reglas del proyecto
├── PLAN.md             # Plan de implementación por fases
├── pyproject.toml
├── docker-compose.yml  # Qdrant
├── .env.example
├── data/
│   ├── raw/            # JSON crudos de scraping (no commiteado)
│   └── processed/      # chunks.jsonl etiquetados
├── src/
│   ├── config.py
│   ├── ingest/         # scrapers + chunker + spoiler classifier
│   ├── retrieval/      # embed + qdrant + retriever híbrido
│   ├── chat/           # prompts, sesión, engine
│   └── cli.py
├── scripts/
│   └── seed_kraken.py  # ingesta + embeddings end-to-end
└── tests/
```

## Decisiones de diseño

Documentadas íntegramente en [`CLAUDE.md`](./CLAUDE.md). En resumen:

- **3 niveles de spoiler** (`0` premisa, `1` desarrollo, `2` final).
  El filtrado ocurre en el retriever, no en el prompt.
- **3 tiers de fuente** (oficial > crítica > fans).
- **Cada chunk distingue** `origen_canon: "pelicula" | "novela" | "ambas"`.
- **Sin frameworks RAG** (LangChain/LlamaIndex). SDKs directos.

## Tests

```bash
uv run pytest
```

## Licencia

Privado. No publicar contenidos scrapeados sin permiso de los sitios
originales.
