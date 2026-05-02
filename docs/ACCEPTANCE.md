# Acceptance test — MVP1 Kraken

Procedimiento manual para validar que el sistema cumple los criterios
de §11 de `CLAUDE.md`. Está pensado para que lo corras tú a mano la
primera vez; los resultados los anotamos al final.

## Prerrequisitos

```bash
cp .env.example .env
# Edita .env y rellena ANTHROPIC_API_KEY
uv sync
docker compose up -d
curl -fsS http://localhost:6333/healthz   # → "healthz check passed"
```

## Opción A — Corpus completo (con scraping)

```bash
uv run python scripts/seed_kraken.py --recreate
```

Esto descarga las 3 fuentes mínimas (Wikipedia peli, Wikipedia novela,
Festival Málaga), chunkea, clasifica spoilers con Haiku y upserta en
Qdrant. Cuesta unos pocos céntimos de Anthropic la primera vez (luego
todo va por caché). Tarda unos minutos por la descarga inicial de
BGE-m3 (~1.5 GB) si es la primera vez.

Si la URL del Festival de Málaga no es la que el scraper espera por
defecto, exporta antes:

```bash
export FESTIVAL_MALAGA_URL=https://festivaldemalaga.com/peliculas/<slug-real>
```

## Opción B — Corpus mínimo offline (sin scraping)

Útil si todavía no tienes red lista o quieres probar el chat hoy:

```bash
uv run python scripts/bootstrap_canonical.py
uv run python scripts/seed_kraken.py --skip-scrape --recreate
```

Sigue necesitando `ANTHROPIC_API_KEY` para el spoiler classifier y el
chat.

## Verificación previa al chat

```bash
uv run cinemaia info
```

Debería mostrar al menos 3 chunks (corpus mínimo) o decenas (corpus
completo), repartidos por tier 1 y por niveles de spoiler.

## Las 8 preguntas de aceptación

Ejecuta en este orden, anotando si la respuesta cumple lo esperado.
Para cada modo, corre:

```bash
uv run cinemaia chat --modo pre        # luego :modo durante  ;  :modo post
```

| # | Pregunta | pre_cine | durante | post_cine |
|---|---|---|---|---|
| 1 | ¿De qué va Kraken? | premisa | premisa | premisa |
| 2 | ¿Quién dirige la película? | OK | OK | OK |
| 3 | ¿Quién es Esti? | rol básico | algo más | rol completo |
| 4 | ¿Quién es Sara? | "no la tengo registrada" en los 3 modos |
| 5 | ¿Qué relación tiene Unai con su madre? | "implica spoiler, ¿cambias?" | parcial | completo |
| 6 | ¿Cómo termina? | rechazar | rechazar | responder |
| 7 | ¿Hay que leer los libros anteriores? | OK | OK | OK |
| 8 | ¿Cuál es la mejor pizza de Madrid? | redirigir fuera de tema |

### Criterios de paso

- (1) Respuesta menciona la llamada anónima, los 7 días, el Libro Negro
  y la madre creída muerta. NO debe mencionar el desenlace.
- (2) Sanabria y Llamas, sin alucinar otros nombres.
- (3) En `pre_cine`, solo "compañera de Unai" o similar. En `post_cine`,
  detalles de su rol si están en corpus.
- (4) Las 3 modos: marcador `No tengo registrado a Sara`. **Crítico**:
  cero invención.
- (5) `pre_cine`: avisa de spoiler y propone cambiar de modo.
  `post_cine`: explica con detalle (si el corpus lo cubre).
- (6) `pre_cine` y `durante`: rechaza. `post_cine`: responde si hay
  contexto recuperado de nivel 2.
- (7) Respuesta razonable explicando que es secuela y que ayuda pero no
  es imprescindible.
- (8) Mensaje "solo puedo ayudarte con Kraken".

### Comprobaciones adicionales

1. **Modo debug**:
   ```
   :debug on
   ¿De qué va Kraken?
   ```
   El bot debe mostrar después de la respuesta los chunks recuperados
   con `tier=1 spoiler=0 canon=...`.

2. **Cambio de modo sin reiniciar**:
   ```
   :modo durante
   :modo post
   ```
   El historial debe preservarse (si retomas la conversación, debe
   recordar lo previo).

3. **Log de "no sé"**:
   ```
   :nose
   ```
   Debe listar (al menos) la pregunta sobre Sara.

   ```
   uv run cinemaia export-no-se --out /tmp/no_se.json
   ```
   Vuelca el log en JSON.

4. **Tests automáticos**:
   ```bash
   uv run pytest
   ```
   33 deben pasar; 1 skipped salvo que tengas `ANTHROPIC_API_KEY` en
   el entorno (entonces se ejecuta el test del clasificador real
   contra fixtures).

## Plantilla de reporte

Crea `docs/acceptance-report.md` con esta forma cuando termines:

```markdown
# Acceptance report — fecha YYYY-MM-DD

Corpus usado: completo / mínimo
Total chunks: N

| # | Pregunta | pre | durante | post | Notas |
|---|---|---|---|---|---|
| 1 | ¿De qué va? | ✅ | ✅ | ✅ | |
| 2 | ¿Quién dirige? | ✅ | ✅ | ✅ | |
| 3 | ¿Quién es Esti? |  |  |  | |
| 4 | ¿Quién es Sara? |  |  |  | |
| 5 | Unai y su madre |  |  |  | |
| 6 | ¿Cómo termina? |  |  |  | |
| 7 | Libros previos |  |  |  | |
| 8 | Pizza Madrid |  |  |  | |

Comprobaciones extra:
- :debug muestra chunks: ✅ / ❌
- :modo cambia sin reiniciar: ✅ / ❌
- :nose contiene Sara: ✅ / ❌

Observaciones / fallos detectados:
- ...
```

## Diagnóstico de fallos comunes

- **Bot inventa información sobre Sara**: revisa que el spoiler
  classifier no esté etiquetando todo como nivel 0. Mira
  `data/processed/spoiler_borderline.jsonl`.
- **`pre_cine` revela el final**: comprueba que los chunks tengan
  `spoiler_level=2` correctamente. Si `:debug on` muestra chunks
  con `spoiler=2` filtrándose en modo pre, el filtro Qdrant no se
  está aplicando — revisa `KrakenStore.search`.
- **No recupera nada relevante**: corpus mínimo. Corre `seed_kraken.py`
  sin `--skip-scrape` para tener Wikipedia + Festival.
- **Festival de Málaga falla**: la URL puede haber cambiado. Exporta
  `FESTIVAL_MALAGA_URL`.
- **Wikipedia da 404**: el título canónico de la página puede diferir.
  Edita `TITLE` en `src/ingest/sources/wikipedia_pelicula.py` /
  `wikipedia_novela.py`.
