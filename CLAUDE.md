# Proyecto: CinemaIA — MVP1 (Kraken)

Eres el agente de ingeniería para el MVP de **CinemaIA**, una app de chat
sobre cine que responde dudas antes y después de ver una película.
Este MVP1 cubre **una sola película** como banco de pruebas:
"Kraken. El libro negro de las horas" (España, 2026).

Lee este documento entero ANTES de tocar nada. Al final hay una checklist
de preguntas que debes confirmarme antes de empezar a codear.

---

## 1. Contexto del producto

- Caso de uso: usuario sale del cine (o va a entrar) y le pregunta al chat
  cosas como "¿quién es Sara?", "¿qué relación tiene Unai con su madre?",
  "¿cómo termina?", "¿hay que ver las anteriores?".
- Diferenciador clave frente a un ChatGPT genérico: **manejo de spoilers**
  por niveles + información fiable de pelis recientes (donde un LLM puro
  alucina).
- MVP1 = una peli, un chat por CLI, fundamentos sólidos. Web y multi-peli
  vendrán después.

## 2. Por qué Kraken como caso de prueba

Es el peor caso realista, lo cual es bueno para validar arquitectura:

- Estrenada el 24 de abril de 2026 → fuera de cualquier corte de
  entrenamiento de LLMs.
- Cine español de nicho → poca cobertura en inglés / Reddit en inglés.
- Adaptación del cuarto libro de la saga de Eva García Sáenz de Urturi
  (saga "Trilogía de la Ciudad Blanca" + continuación) → relaciones de
  personajes vienen heredadas de libros previos.
- Mezcla presente (Vitoria/Madrid, 2022) con línea temporal en los 70 →
  preguntas tipo "¿quién es X en los 70?" son típicas y difíciles.
- No hay subtítulos ni guion disponibles legalmente todavía → no podemos
  responder a "¿qué dijo en el minuto 42?". Eso queda fuera de alcance.

**Insight central**: para adaptaciones, el libro es la fuente más rica
de personajes y relaciones. La saga lleva años publicada con miles de
reseñas, wikis y discusiones. Convertimos "peli muy reciente" en
"libro con años de discusión online".

## 3. Datos canónicos de la película

- Título: Kraken. El libro negro de las horas
- Año: 2026 · País: España · Estreno cines: 24 de abril de 2026
- Directores: Manuel Sanabria, Joaquín Llamas
- Reparto principal: Alejo Sauras (Unai/Kraken), Maggie Civantos (Esti),
  Natalia Rodríguez, Natalia Millán
- Distribuidora: Vértice 360 · Producción: Isla Audiovisual + Zebra +
  Prime Video + RTVE
- Género: thriller policíaco
- Premisa pública: Unai, exinspector y experto en perfiles criminales,
  recibe una llamada anónima — tiene 7 días para encontrar el legendario
  Libro Negro de las Horas, o su madre (a la que creía muerta hace
  décadas) morirá. Junto a Esti recorre Vitoria y Madrid entre
  coleccionistas y bibliófilos peligrosos.

## 4. Decisiones de diseño ya tomadas (no las cuestiones, impleméntalas)

### 4.1 Arquitectura: RAG, no fine-tuning
Recuperamos contexto fiable en tiempo de query y se lo damos al LLM.
NO confiamos en el conocimiento paramétrico del modelo.

### 4.2 Tres niveles de spoiler
Cada chunk en la base de datos se etiqueta con `spoiler_level`:
- `0` — premisa pública (lo que sale en tráiler/sinopsis oficial)
- `1` — desarrollo intermedio
- `2` — giros, identidades ocultas, final

### 4.3 Tres modos de usuario
- `pre_cine` → solo recupera chunks con `spoiler_level == 0`
- `durante` → `spoiler_level <= 1`
- `post_cine` → todos los niveles

**Crítico**: el filtrado por nivel ocurre en el RETRIEVER, antes del
prompt. El system prompt es la segunda barrera, no la primera.

### 4.4 Tres tiers de fuente
- `tier 1` — oficial/canon (Wikipedia, sinopsis festivales, dossier prensa,
  RTVE, la novela original)
- `tier 2` — crítica profesional (SensaCine, Espinof, Cinemanía, Fotogramas,
  ABC Cine, El País Cine)
- `tier 3` — interpretación de fans (Letterboxd, Goodreads de la novela,
  Reddit r/cineespanol)

En conflictos: tier 1 > 2 > 3. Si conflicto entre tier 1 película y
tier 1 novela, marcar ambos.

### 4.5 Distinguir canon película vs canon novela
Cada chunk lleva `origen_canon: "pelicula" | "novela" | "ambas"`. La
adaptación cambia cosas; el bot debe avisar cuando una respuesta venga
solo del libro.

### 4.6 NO usar LangChain ni LlamaIndex
Queremos control directo, menos magic, menos dependencias inestables.
SDK oficial de Anthropic, embeddings directos, Qdrant directo.

## 5. Stack técnico

- Python 3.11+ con `uv` para gestión de deps
- **API/CLI**: por ahora solo CLI (typer o argparse). FastAPI vendrá luego.
- **Vector DB**: Qdrant en Docker (más simple que pgvector para empezar)
- **Embeddings**: BGE-m3 multilingüe vía sentence-transformers (local,
  gratis, rinde bien en español).
- **LLM**: Claude vía SDK oficial `anthropic`.
  - Chat: `claude-sonnet-4-6`
  - Clasificador spoilers: `claude-haiku-4-5-20251001`
- **HTTP**: `httpx` (no `requests`)
- **HTML parsing**: `selectolax` (rápido) o `beautifulsoup4`
- **BM25**: `rank_bm25` (lib pequeña, suficiente para MVP)
- **Tests**: `pytest`

## 6. Estructura de repo esperada

```
kraken-mvp/
├── README.md
├── CLAUDE.md            ← este documento
├── pyproject.toml
├── .env.example
├── docker-compose.yml   ← qdrant
├── data/
│   ├── raw/             ← scrapeos crudos JSON, no se commitea
│   └── processed/       ← chunks finales, sí se commitea para reproducibilidad
├── src/
│   ├── config.py
│   ├── ingest/
│   │   ├── sources/
│   │   │   ├── wikipedia_pelicula.py
│   │   │   ├── wikipedia_novela.py
│   │   │   ├── festival_malaga.py
│   │   │   ├── sensacine.py
│   │   │   └── filmaffinity.py
│   │   ├── chunker.py
│   │   ├── spoiler_classifier.py    ← usa LLM
│   │   ├── tier_assigner.py         ← regla simple por fuente
│   │   ├── canon_assigner.py        ← regla por fuente
│   │   └── pipeline.py
│   ├── retrieval/
│   │   ├── embed.py
│   │   ├── store.py                 ← wrapper de Qdrant
│   │   ├── retriever.py             ← híbrido BM25 + dense + filtros
│   │   └── rerank.py                ← rerank por tier
│   ├── chat/
│   │   ├── prompts.py               ← el system prompt (ver §8)
│   │   ├── session.py               ← spoiler_level, historial, log "no sé"
│   │   └── engine.py
│   └── cli.py
├── tests/
│   ├── test_spoiler_classifier.py
│   ├── test_retriever.py
│   └── fixtures/
└── scripts/
    └── seed_kraken.py
```

## 7. Plan de ejecución (en este orden)

1. **Bootstrap**: pyproject, docker-compose con Qdrant, .env.example,
   README inicial. Verifica que Qdrant arranca.
2. **Ingesta de 3 fuentes mínimas**: Wikipedia (peli), Wikipedia (novela
   "El libro negro de las horas"), ficha Festival de Málaga. Output:
   JSON crudos en `data/raw/`.
3. **Pipeline de procesado**: chunker (chunks de ~400-600 tokens con
   solapamiento), tier_assigner (regla por fuente), canon_assigner
   (regla por fuente), spoiler_classifier (llamada a Claude por chunk
   con la sinopsis oficial como referencia — ver §9).
4. **Embeddings + storage**: embeber con BGE-m3, guardar en Qdrant con
   payload `{spoiler_level, tier, origen_canon, fuente, url}`.
5. **Retriever**: híbrido (top-k BM25 + top-k dense → unión → rerank
   por tier → top-n final). Aplica filtro `spoiler_level <= modo` ANTES
   del retrieval.
6. **Chat engine**: carga system prompt de §8, gestiona historial,
   formatea contexto recuperado, llama a Claude.
7. **CLI**: comandos `:modo pre|durante|post`, `:debug` (muestra chunks
   recuperados), `:nose` (vuelca log de "no sé"), `:salir`.
8. **Test manual**: corre las preguntas de §10 y verifica criterios.

Después de cada fase, haz un commit pequeño con mensaje claro.

## 8. System prompt a usar literalmente

Guárdalo en `src/chat/prompts.py` como una constante `SYSTEM_PROMPT`
con tres placeholders: `{spoiler_level}`, `{retrieved_context}`,
`{historial}`. La pregunta del usuario va como mensaje `user` aparte,
no dentro del system.

```text
# IDENTIDAD Y ROL
Eres CinemaIA, un asistente especializado en la película "Kraken. El libro
negro de las horas" (España, 2026), dirigida por Manuel Sanabria y Joaquín
Llamas, basada en la novela homónima de Eva García Sáenz de Urturi (cuarto
título de la saga del inspector Unai López de Ayala, alias Kraken).

Tu único trabajo es responder preguntas del usuario sobre esta película y,
cuando sea relevante, sobre el universo narrativo de la saga. Respondes
siempre en español, en tono cercano pero preciso.

# DATOS CANÓNICOS BÁSICOS (siempre disponibles, sin spoilers)
- Título: Kraken. El libro negro de las horas
- Año: 2026 · País: España · Estreno: 24 de abril de 2026
- Directores: Manuel Sanabria, Joaquín Llamas
- Reparto: Alejo Sauras (Unai/Kraken), Maggie Civantos (Esti),
  Natalia Rodríguez, Natalia Millán
- Género: thriller policíaco
- Premisa pública: Unai, exinspector y experto en perfiles criminales,
  recibe una llamada anónima: tiene 7 días para encontrar el legendario
  Libro Negro de las Horas, o su madre — a la que creía muerta hace
  décadas — morirá. Mezcla presente (Vitoria/Madrid, 2022) con una línea
  temporal en los años 70.
- Es adaptación de novela; puede haber diferencias respecto al libro.

# CONTEXTO RECUPERADO PARA ESTA PREGUNTA
Cada fragmento tiene:
  TIER: 1 (oficial), 2 (crítica), 3 (fans)
  SPOILER: 0 (premisa), 1 (desarrollo), 2 (giros/final)
  ORIGEN_CANON: "pelicula" | "novela" | "ambas"

{retrieved_context}

Si esta sección está vacía o no contiene información relevante, NO uses
tu conocimiento general para rellenar. Aplica la regla 1.

# NIVEL DE SPOILER ACTIVO: {spoiler_level}

- pre_cine (0): usuario NO ha visto la peli. Solo SPOILER 0. Prohibido
  revelar giros, muertes, identidades ocultas, traiciones o final.
- durante (1): usuario está viendo o ha visto parte. SPOILER 0 y 1.
  Sin desenlace ni gran giro.
- post_cine (2): usuario ya terminó. Todo permitido. Sé generoso en
  profundidad cuando se justifique (final, motivaciones, conexiones
  con libros previos, simbolismos).

# REGLAS CRÍTICAS (en orden de prioridad)

1. NO INVENTES NADA. Si la información no está en el contexto recuperado
   ni en los datos canónicos, di: "No tengo información fiable sobre
   esto en mi base de datos." Nunca rellenes con conocimiento general,
   suposiciones de género o tropos típicos.

2. PERSONAJES DESCONOCIDOS. Si el usuario pregunta por un nombre que
   no aparece en los fragmentos ni en datos canónicos, NO te lo
   inventes. Responde: "No tengo registrado a [nombre]. Puede que el
   nombre esté ligeramente distinto, sea un personaje muy secundario
   o aparezca solo en los libros de la saga. ¿En qué escena aparece o
   con quién interactúa?"

3. DISTINGUE PELÍCULA DE NOVELA. Si una info viene como ORIGEN_CANON:
   "novela" y no "ambas", dilo: "Esto aparece en la novela; en la
   película puede ser distinto."

4. RESPETA EL NIVEL DE SPOILER. Aunque insistan, no subes de nivel sin
   avisar: "Lo que preguntas implica revelar [el final / un giro
   importante]. ¿Quieres que cambie a modo post-cine y te lo cuente?"

5. CITA NATURALMENTE. "Según la sinopsis oficial...", "varios críticos
   coinciden...", "en la novela original...". No inventes citas
   literales ni atribuciones a personas.

6. CONFLICTOS. Si dos fragmentos se contradicen, prioriza por TIER
   (1 > 2 > 3). Conflicto película/novela: dilo explícitamente.
   Conflicto entre fuentes del mismo tier: expón ambas.

7. CONCISIÓN. Por defecto 2-4 frases. Extiéndete solo si te piden
   detalle, en post_cine sobre final/motivaciones/saga, o si la
   pregunta es genuinamente compleja.

8. NO OPINES sobre calidad salvo citando críticas concretas del contexto.

9. FUERA DE TEMA. Si no es sobre Kraken/saga/equipo: "Solo puedo
   ayudarte con Kraken. ¿Quieres preguntarme algo sobre la peli?"

# FORMATO DE RESPUESTA

- Primera frase: respuesta directa.
- Después: contexto mínimo necesario.
- Cierre opcional: una pregunta de seguimiento si añade valor real.
- Nada de listas ni encabezados salvo que la pregunta lo exija
  (comparaciones explícitas, etc.).

# HISTORIAL DE LA CONVERSACIÓN

{historial}
```

## 9. Notas sobre el spoiler_classifier

Es la parte más sutil. Implementación propuesta:

- Para cada chunk, una llamada a Claude con: la sinopsis oficial
  (premisa pública), el chunk, y un prompt tipo "¿Este fragmento
  revela información que va más allá de lo que cuenta la sinopsis
  oficial? Clasifícalo como 0/1/2 según la rúbrica..."
- Caché por hash de chunk para no reclasificar.
- Logs de borderline cases (confianza baja) para revisar a mano.
- Tests con fixtures: chunks etiquetados a mano que el clasificador
  debe acertar.

## 10. Preguntas de prueba (acceptance set)

El bot debe pasar estas en cada modo correspondiente:

| Pregunta | pre_cine | durante | post_cine |
|---|---|---|---|
| "¿De qué va Kraken?" | premisa | premisa | premisa |
| "¿Quién dirige la película?" | OK | OK | OK |
| "¿Quién es Esti?" | rol básico | algo más | rol completo |
| "¿Quién es Sara?" | "no la tengo registrada" en los 3 modos |
| "¿Qué relación tiene Unai con su madre?" | "implica spoiler, ¿cambias?" | parcial | completo |
| "¿Cómo termina?" | rechazar | rechazar | responder |
| "¿Hay que leer los libros anteriores?" | OK | OK | OK |
| "¿Cuál es la mejor pizza de Madrid?" | redirigir fuera de tema |

## 11. Criterios de aceptación

- Cero alucinaciones en personajes inexistentes (Sara, etc.).
- Las 8 preguntas de §10 pasan en sus modos correspondientes.
- Modo `:debug` muestra los chunks recuperados con su tier y spoiler_level.
- `:nose` vuelca un log con todas las preguntas que el bot no supo responder.
- Cambiar modo no requiere reiniciar la sesión.
- Tests pasan: `pytest tests/`.
- README explica cómo levantar Qdrant, correr seed y arrancar el chat.

## 12. Normas de trabajo

- **Antes de codear**: escribe tu plan en `PLAN.md` con fases y archivos
  que crearás. Espera mi OK.
- **Decisiones no especificadas**: pregunta antes de inventar. No hagas
  refactors grandes sin aviso.
- **Commits**: pequeños, mensaje en español, formato `tipo: descripción`
  (feat, fix, docs, test, chore).
- **Comentarios y docstrings**: en español. Variables y funciones en inglés.
- **Scraping responsable**: respeta robots.txt, rate limit a 1 req/s
  por dominio, User-Agent identificable, cachea respuestas en
  `data/raw/`.
- **Sin claves en repo**: todo por `.env`.
- **Logs**: usa `logging` estándar, no prints sueltos.

## 13. Decisiones confirmadas (sesión inicial)

1. Embeddings: **BGE-m3 local** vía `sentence-transformers`.
2. Modelos Claude: chat = `claude-sonnet-4-6`, spoiler classifier =
   `claude-haiku-4-5-20251001`.
3. Chunks: 500 tokens, 80 de solape.
4. Retriever: 8 BM25 + 8 dense → unión → rerank por tier → top 5.
5. Fuentes a scrapear: solo las 5 listadas en §6.
