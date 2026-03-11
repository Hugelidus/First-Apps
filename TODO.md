# TODO - Próxima sesión

## 1. Chat Conversacional con IA (`src/chat.py`)

Crear interfaz de chat donde el usuario habla con Claude y Claude puede consultar todos los datos del app + investigar en la web.

### Arquitectura
- Clase `ChatEngine` con historial de conversación
- Claude Sonnet 4 con `tools` (function calling) + `web_search`
- Loop: usuario escribe → Claude decide qué tools llamar → ejecuta → responde
- Display con Rich (panels, markdown, spinners)

### Tools a definir (wrapping funciones existentes)

| Tool | Función existente | Para qué |
|------|-------------------|----------|
| `get_upcoming_matches` | `football_data.get_upcoming_matches()` | Próximos partidos |
| `get_finished_matches` | `football_data.get_finished_matches()` | Resultados recientes |
| `get_standings` | `football_data.get_standings()` | Clasificación |
| `get_scorers` | `football_data.get_scorers()` | Goleadores |
| `search_team` | `football_data.search_team()` | Buscar equipo por nombre |
| `get_team_stats` | `football_data.get_team_stats_summary()` | Stats de equipo |
| `get_team_matches` | `football_data.get_team_matches()` | Partidos de un equipo |
| `get_odds` | `odds_api.get_odds_1x2()` | Cuotas 1X2 |
| `get_odds_totals` | `odds_api.get_odds_totals()` | Cuotas Over/Under |
| `predict_match` | PiRating + GoalsModel | Predicción completa |
| `find_value_bets` | Predicción + Cuotas + value_bets | Value bets de un partido |
| `calculate_stake` | `kelly.recommended_stake()` | Cuánto apostar |
| `analyze_longshots` | **NUEVO** | Cuotas altas con valor |
| `backtest_strategy` | **NUEVO** | Backtest con datos históricos |
| `web_search` | Built-in Anthropic | Investigar en la web |

### Integración
- Agregar opción "9. Chat con IA" en `src/tui.py`

---

## 2. Estrategia Cuotas Altas (Longshots)

El objetivo es encontrar apuestas de cuota alta (+3.0, +5.0, etc.) que sean rentables a largo plazo, aunque acierten pocas veces.

### Tool `analyze_longshots`
- Obtener próximos partidos + cuotas del mercado
- Generar predicciones con nuestros modelos (PiRating + GoalsModel)
- Filtrar: cuota >= umbral (default 3.0) AND valor esperado positivo (prob × cuota > 1)
- Kelly stake ajustado para longshots
- Parámetros: min_odds, max_odds, min_value

### Tool `backtest_strategy`
- Usar `data/historical/champions_league.csv` (333 partidos con cuotas reales B365)
- Simular estrategia walk-forward:
  1. Entrenar Pi-ratings hasta partido N
  2. Predecir partido N+1
  3. Comparar predicción vs cuotas B365
  4. Si hay value bet en cuota alta → apuesta simulada con Kelly
  5. Registrar acierto/fallo
- Reportar: ROI, hit rate, profit/loss, drawdown, racha máxima
- Filtros: por equipo ("solo Madrid"), por rango de cuotas (3.0-8.0)

### Datos disponibles en CSV
Columnas clave: `B365H`, `B365D`, `B365A` (cuotas), `FTR` (resultado real H/D/A), `HST`/`AST` (tiros a puerta), `Date`, `HomeTeam`, `AwayTeam`, `FTHG`/`FTAG` (goles)
