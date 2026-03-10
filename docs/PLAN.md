# Plan de Desarrollo: Pronósticos Deportivos con IA

## Visión General
Sistema CLI en Python que predice resultados de Champions League (1X2, Over/Under, handicaps, value bets) combinando Machine Learning + Claude API para análisis contextual.

---

## FASE 1: Configuración del Entorno y Estructura del Proyecto

### 1.1 Setup del proyecto Python
- Crear `pyproject.toml` o `requirements.txt` con dependencias:
  - **Datos**: `pandas`, `numpy`, `requests`, `soccerdata`
  - **ML**: `scikit-learn`, `xgboost`, `catboost`
  - **Estadística**: `scipy` (distribución Poisson)
  - **LLM**: `anthropic` (Claude API)
  - **Utilidades**: `click` (CLI), `rich` (tablas bonitas en terminal), `python-dotenv`
- Crear `.env.example` con las API keys necesarias
- Estructura de carpetas:
  ```
  src/
  ├── cli.py              # Punto de entrada CLI
  ├── config.py           # Configuración y API keys
  ├── data/
  │   ├── api_football.py # Cliente API-Football
  │   ├── odds_api.py     # Cliente The Odds API
  │   ├── football_data.py# Cliente Football-Data.org
  │   └── cache.py        # Cache local de datos
  ├── features/
  │   ├── ratings.py      # Elo / Pi-ratings
  │   ├── form.py         # Forma reciente
  │   ├── stats.py        # Estadísticas de equipo
  │   └── builder.py      # Constructor de features
  ├── models/
  │   ├── match_predictor.py  # Modelo 1X2
  │   ├── goals_model.py      # Over/Under (Poisson + ML)
  │   ├── ensemble.py         # Ensemble voting
  │   └── calibration.py      # Calibración de probabilidades
  ├── betting/
  │   ├── value_bets.py   # Detección de value bets
  │   ├── kelly.py        # Kelly Criterion (fraccional)
  │   └── odds_compare.py # Comparador de cuotas
  ├── llm/
  │   ├── analyzer.py     # Análisis contextual con Claude
  │   └── adjuster.py     # Ajuste de probabilidades ML+LLM
  └── utils/
      ├── display.py      # Formateo de resultados para CLI
      └── validators.py   # Validaciones
  ```

---

## FASE 2: Recolección de Datos (Data Layer)

### 2.1 Cliente API-Football (fuente principal)
- Autenticación con API key
- Endpoints a consumir:
  - `/fixtures` — partidos programados y resultados de Champions League
  - `/fixtures/statistics` — estadísticas por partido (tiros, posesión, corners)
  - `/fixtures/lineups` — alineaciones
  - `/fixtures/headtohead` — historial entre equipos
  - `/teams/statistics` — estadísticas de temporada por equipo
  - `/odds` — cuotas pre-partido
  - `/injuries` — lesiones actuales
- Rate limiting: máximo 100 requests/día (free tier)
- Cache local en JSON/SQLite para no repetir llamadas

### 2.2 Cliente The Odds API (cuotas multi-bookmaker)
- Obtener cuotas de múltiples casas de apuestas
- Mercados: 1X2 (h2h), totals (Over/Under), spreads (handicap)
- Presupuesto: 500 requests/mes

### 2.3 Cliente Football-Data.org (backup/standings)
- Clasificaciones actualizadas
- Calendario de partidos
- 10 requests/min (generoso)

### 2.4 Sistema de Cache
- Almacenar respuestas de API localmente (SQLite o JSON)
- TTL configurable (ej: fixtures = 1h, estadísticas históricas = 24h)
- Evitar gastar requests innecesarios en los free tiers

---

## FASE 3: Feature Engineering

### 3.1 Sistema de Ratings Dinámicos
- Implementar **Elo ratings** como baseline (más simple)
- Implementar **Pi-ratings** (superior: ratings separados local/visitante + margen de goles)
- Actualizar ratings tras cada jornada

### 3.2 Features de Forma Reciente
- Últimos 5-6 partidos con ponderación temporal (recientes pesan más)
- Separar forma local vs visitante
- Métricas: puntos, goles a favor/contra, xG si disponible

### 3.3 Features Estadísticas por Equipo
- Fuerza atacante y debilidad defensiva (relativo a media de la liga)
- Tiros a puerta, corners, posesión (como features secundarias)
- Head-to-head histórico entre los dos equipos

### 3.4 Constructor de Features (Feature Builder)
- Pipeline que combina todas las features en un DataFrame listo para ML
- Normalización y encoding donde sea necesario
- Split temporal (walk-forward), NUNCA split aleatorio

---

## FASE 4: Modelos de Predicción

### 4.1 Modelo 1X2 (Resultado del Partido)
- **XGBoost** como modelo principal
- **CatBoost** como modelo secundario
- Features: ratings, forma, stats, head-to-head
- Output: probabilidades calibradas (Home%, Draw%, Away%)
- Validación: walk-forward por temporada

### 4.2 Modelo de Goles (Over/Under + Handicap)
- **Dixon-Coles** (Poisson corregido) para score matrix
  - Calcula lambda_home y lambda_away (goles esperados)
  - Matriz de probabilidades de cada marcador (0-0 a 6-6)
  - Deriva Over/Under 2.5 sumando celdas relevantes
  - Deriva handicaps sumando celdas donde el margen cumple
- **XGBoost clasificador** para Over/Under 2.5 como alternativa ML
- Combinar ambos enfoques

### 4.3 Ensemble (Combinación)
- Voting ensemble: XGBoost + CatBoost para 1X2
- Promedio ponderado de Dixon-Coles + ML para goles
- Calibración de probabilidades con Platt scaling o isotonic regression

---

## FASE 5: Integración con LLM (Claude)

### 5.1 Análisis Contextual con Claude
- Enviar a Claude:
  - Predicciones base del modelo ML
  - Datos de lesiones/sanciones actuales
  - Información de la fase de la competición (fase de grupos, eliminatorias, final)
  - Contexto motivacional (equipo ya clasificado, necesita ganar, etc.)
- Claude devuelve:
  - Factor de ajuste con justificación
  - Análisis narrativo del partido

### 5.2 Sistema de Ajuste Acotado
- Claude puede ajustar probabilidades máximo ±10%
- Guardrails para que el LLM no sobreescriba al modelo estadístico
- Log de ajustes para evaluar si el LLM mejora o empeora las predicciones

---

## FASE 6: Sistema de Apuestas (Betting Logic)

### 6.1 Detección de Value Bets
- Fórmula: `value = (probabilidad_predicha × cuota_decimal) - 1`
- Si value > 0, hay valor
- Umbral mínimo configurable (ej: value > 0.05 para filtrar ruido)

### 6.2 Kelly Criterion Fraccional
- `f = (B×P - Q) / B` donde B=cuota-1, P=prob, Q=1-P
- Usar Kelly fraccional (1/4 a 1/2) para reducir varianza
- Límite máximo: nunca apostar más del 5% del bankroll
- Solo apostar cuando Kelly > 0

### 6.3 Comparador de Cuotas
- Mostrar cuotas de múltiples casas de apuestas
- Destacar la mejor cuota disponible para cada mercado
- Calcular probabilidad implícita de cada cuota

---

## FASE 7: Interfaz CLI

### 7.1 Comandos principales
- `pronostico proximos` — Muestra próximos partidos de Champions con predicciones
- `pronostico analizar <equipo1> vs <equipo2>` — Análisis detallado de un partido
- `pronostico valuebets` — Lista las value bets detectadas
- `pronostico historial` — Historial de predicciones y aciertos
- `pronostico actualizar` — Actualizar datos y ratings

### 7.2 Formato de salida
- Tablas con `rich` mostrando:
  - Partido, fecha, predicción 1X2, Over/Under
  - Cuotas, value bets detectadas, stake recomendado (Kelly)
  - Análisis de Claude (resumen breve)

---

## FASE 8: Evaluación y Backtesting

### 8.1 Backtesting histórico
- Correr el modelo sobre temporadas pasadas de Champions
- Medir: accuracy, ROI simulado, calibración de probabilidades
- Ranked Probability Score (RPS) como métrica principal

### 8.2 Tracking en vivo
- Registrar cada predicción y resultado real
- Dashboard CLI de rendimiento: aciertos, ROI, racha

---

## Orden de Implementación Recomendado

| Paso | Fase | Prioridad | Dependencias |
|------|------|-----------|--------------|
| 1    | F1: Setup proyecto y dependencias | Alta | Ninguna |
| 2    | F2.1: Cliente API-Football + cache | Alta | F1 |
| 3    | F2.2: Cliente The Odds API | Alta | F1 |
| 4    | F2.3: Cliente Football-Data.org | Media | F1 |
| 5    | F3.1: Elo/Pi-ratings | Alta | F2 |
| 6    | F3.2-3.4: Resto de features | Alta | F2, F3.1 |
| 7    | F4.1: Modelo 1X2 (XGBoost) | Alta | F3 |
| 8    | F4.2: Modelo de goles (Dixon-Coles) | Alta | F3 |
| 9    | F4.3: Ensemble + calibración | Media | F4.1, F4.2 |
| 10   | F5: Integración Claude | Media | F4 |
| 11   | F6: Value bets + Kelly | Alta | F4, F2.2 |
| 12   | F7: CLI completa | Media | Todo lo anterior |
| 13   | F8: Backtesting | Media | F4, F6 |

---

## Notas Técnicas Importantes

1. **Validación temporal**: SIEMPRE walk-forward, nunca splits aleatorios
2. **Pi-ratings > Elo**: Mantener ratings separados local/visitante
3. **xG > goles raw**: Usar expected goals cuando estén disponibles
4. **Kelly fraccional**: Nunca Kelly completo, usar 1/4 a 1/2
5. **LLM acotado**: Claude ajusta máx ±10%, no reemplaza al modelo ML
6. **Cache agresivo**: Los free tiers son limitados, cachear todo
7. **Asian Handicap**: Mercado poco investigado, posible ventaja competitiva
