"""Análisis contextual de partidos usando Claude API con búsqueda web."""

import json

import anthropic

from src.config import ANTHROPIC_API_KEY

MAX_ADJUSTMENT = 0.10  # Máximo ajuste ±10%


SYSTEM_PROMPT = """Eres un analista experto de fútbol. Tienes acceso a búsqueda web.

PROCESO:
1. Busca en la web: lesiones, forma reciente, stats (tiros a puerta, paradas GK, goles/partido).
2. Analiza y sugiere AJUSTES a las probabilidades ML (entre -0.10 y +0.10).
3. Responde SOLO con este JSON exacto (sin texto adicional):

```json
{"adjustments":{"home":0.0,"draw":0.0,"away":0.0},"confidence":"medium","analysis":"texto","key_factors":["factor1"],"stats":{"home":{"form":"WDLWW","goals_per_match":1.5,"shots_on_target_per_match":4.2,"clean_sheets":"3 en 10","key_absences":["jugador"],"goalkeeper_saves_per_match":3.1},"away":{"form":"WWLWW","goals_per_match":2.0,"shots_on_target_per_match":5.0,"clean_sheets":"4 en 10","key_absences":[],"goalkeeper_saves_per_match":2.8}}}
```

REGLAS: adjustments entre -0.10 y 0.10. Usa null si no encuentras un dato. NO escribas nada fuera del JSON."""


def analyze_match(
    home_team: str,
    away_team: str,
    ml_probabilities: dict[str, float],
    injuries: list[dict] | None = None,
    standings_context: str | None = None,
    competition_stage: str | None = None,
    rich_context: dict | None = None,
    form_data: dict | None = None,
) -> dict:
    """Analiza un partido con Claude + búsqueda web y devuelve ajustes acotados."""
    if not ANTHROPIC_API_KEY:
        return _no_api_response()

    user_message = _build_prompt(
        home_team, away_team, ml_probabilities,
        injuries, standings_context, competition_stage,
        rich_context, form_data,
    )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # Usar web search para que Claude busque info reciente
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}],
        messages=[{"role": "user", "content": user_message}],
    )

    return _extract_result(response)


def apply_adjustments(
    ml_probs: dict[str, float],
    adjustments: dict[str, float],
) -> dict[str, float]:
    """Aplica los ajustes del LLM a las probabilidades ML, con guardrails."""
    adjusted = {}
    for outcome in ["home", "draw", "away"]:
        adj = max(-MAX_ADJUSTMENT, min(MAX_ADJUSTMENT, adjustments.get(outcome, 0)))
        adjusted[outcome] = ml_probs[outcome] + adj

    # Renormalizar para que sumen 1
    total = sum(adjusted.values())
    if total > 0:
        adjusted = {k: round(v / total, 4) for k, v in adjusted.items()}

    return adjusted


def _build_prompt(
    home_team: str,
    away_team: str,
    ml_probs: dict[str, float],
    injuries: list[dict] | None,
    standings: str | None,
    stage: str | None,
    rich_context: dict | None = None,
    form_data: dict | None = None,
) -> str:
    parts = [
        f"PARTIDO: {home_team} (local) vs {away_team} (visitante)",
        f"PROBABILIDADES ML: Local {ml_probs['home']:.1%} | Empate {ml_probs['draw']:.1%} | Visitante {ml_probs['away']:.1%}",
    ]

    if stage:
        parts.append(f"FASE: {stage}")
    if standings:
        parts.append(f"CONTEXTO CLASIFICACIÓN: {standings}")

    if form_data:
        for side, label in [("home", "LOCAL"), ("away", "VISITANTE")]:
            team_form = form_data.get(side, {})
            if team_form.get("last_matches"):
                matches_str = " | ".join(team_form["last_matches"][:5])
                parts.append(f"FORMA {label}: {matches_str}")

    if injuries:
        injury_text = "\n".join(
            f"  - {inj.get('player', {}).get('name', '?')} ({inj.get('team', {}).get('name', '?')}): {inj.get('type', '?')}"
            for inj in injuries[:10]
        )
        parts.append(f"LESIONES/SANCIONES CONOCIDAS:\n{injury_text}")

    if rich_context:
        for side_key, label in [("home_team", "LOCAL"), ("away_team", "VISITANTE")]:
            team_ctx = rich_context.get(side_key, {})
            ctx_parts = []
            if team_ctx.get("form_narrative"):
                ctx_parts.append(f"Estado: {team_ctx['form_narrative']}")
            if team_ctx.get("tactical_notes"):
                ctx_parts.append(f"Táctica: {team_ctx['tactical_notes']}")
            if ctx_parts:
                parts.append(f"CONTEXTO {label}:\n  " + "\n  ".join(ctx_parts))

    parts.append(
        "INSTRUCCIONES:\n"
        "1. Busca en la web información ACTUAL sobre este partido.\n"
        "2. Busca: lesiones/bajas, forma reciente, tiros a puerta/partido, paradas GK, goles/partido.\n"
        "3. Después de buscar, responde EXCLUSIVAMENTE con el JSON especificado. "
        "NO escribas texto antes ni después del JSON. Solo el bloque ```json ... ```."
    )
    return "\n\n".join(parts)


def _extract_result(response) -> dict:
    """Extrae el resultado JSON de la respuesta de Claude (puede incluir web search blocks)."""
    # Combinar todos los bloques de texto en uno solo
    text_parts = []
    for block in response.content:
        if hasattr(block, "text"):
            text_parts.append(block.text)

    if not text_parts:
        return _no_api_response()

    full_text = "".join(text_parts)
    return _parse_response(full_text)


def _parse_response(text: str) -> dict:
    """Parsea la respuesta JSON de Claude."""
    try:
        # Extraer JSON si viene envuelto en markdown
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[-1].split("```")[0]

        result = json.loads(text.strip())

        # Validar estructura mínima
        if "adjustments" not in result:
            result["adjustments"] = {"home": 0, "draw": 0, "away": 0}
        if "confidence" not in result:
            result["confidence"] = "medium"
        if "analysis" not in result:
            result["analysis"] = ""
        if "key_factors" not in result:
            result["key_factors"] = []

        return result
    except (json.JSONDecodeError, IndexError):
        # Intentar encontrar JSON en cualquier parte del texto
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
        return _no_api_response()


def _no_api_response() -> dict:
    return {
        "adjustments": {"home": 0, "draw": 0, "away": 0},
        "confidence": "low",
        "analysis": "Sin análisis contextual disponible.",
        "key_factors": [],
    }
