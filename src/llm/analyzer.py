"""Análisis contextual de partidos usando Claude API."""

import json

import anthropic

from src.config import ANTHROPIC_API_KEY

MAX_ADJUSTMENT = 0.10  # Máximo ajuste ±10%


SYSTEM_PROMPT = """Eres un analista experto de fútbol especializado en Champions League.
Tu rol es analizar el CONTEXTO de un partido que un modelo ML no puede capturar:
lesiones, sanciones, motivación, fase de la competición, cambios tácticos, etc.

REGLAS:
1. Recibiras las probabilidades del modelo ML y datos contextuales.
2. Debes sugerir AJUSTES a las probabilidades, NO nuevas probabilidades.
3. Los ajustes deben estar entre -0.10 y +0.10 (máximo ±10%).
4. Debes justificar cada ajuste con datos concretos.
5. Si no hay contexto relevante, sugiere ajustes de 0.

Responde SIEMPRE en formato JSON con esta estructura:
{
    "adjustments": {
        "home": <float entre -0.10 y 0.10>,
        "draw": <float entre -0.10 y 0.10>,
        "away": <float entre -0.10 y 0.10>
    },
    "confidence": <"low"|"medium"|"high">,
    "analysis": "<análisis breve del partido>",
    "key_factors": ["<factor 1>", "<factor 2>", ...]
}"""


def analyze_match(
    home_team: str,
    away_team: str,
    ml_probabilities: dict[str, float],
    injuries: list[dict] | None = None,
    standings_context: str | None = None,
    competition_stage: str | None = None,
) -> dict:
    """Analiza un partido con Claude y devuelve ajustes acotados.

    Args:
        home_team: Nombre del equipo local.
        away_team: Nombre del equipo visitante.
        ml_probabilities: Dict con home, draw, away del modelo ML.
        injuries: Lista de lesiones/sanciones.
        standings_context: Posición en la tabla y contexto competitivo.
        competition_stage: Fase de la competición (grupos, octavos, etc.).

    Returns:
        Dict con ajustes y análisis.
    """
    if not ANTHROPIC_API_KEY:
        return _no_api_response()

    user_message = _build_prompt(
        home_team, away_team, ml_probabilities,
        injuries, standings_context, competition_stage,
    )

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    return _parse_response(response.content[0].text)


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
) -> str:
    parts = [
        f"PARTIDO: {home_team} (local) vs {away_team} (visitante)",
        f"PROBABILIDADES ML: Local {ml_probs['home']:.1%} | Empate {ml_probs['draw']:.1%} | Visitante {ml_probs['away']:.1%}",
    ]

    if stage:
        parts.append(f"FASE: {stage}")
    if standings:
        parts.append(f"CONTEXTO CLASIFICACIÓN: {standings}")
    if injuries:
        injury_text = "\n".join(
            f"  - {inj.get('player', {}).get('name', '?')} ({inj.get('team', {}).get('name', '?')}): {inj.get('type', '?')}"
            for inj in injuries[:10]
        )
        parts.append(f"LESIONES/SANCIONES:\n{injury_text}")

    parts.append(
        "Analiza el contexto y sugiere ajustes a las probabilidades ML. "
        "Responde en JSON."
    )
    return "\n\n".join(parts)


def _parse_response(text: str) -> dict:
    """Parsea la respuesta JSON de Claude."""
    try:
        # Extraer JSON si viene envuelto en markdown
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        return _no_api_response()


def _no_api_response() -> dict:
    return {
        "adjustments": {"home": 0, "draw": 0, "away": 0},
        "confidence": "low",
        "analysis": "Sin análisis contextual disponible.",
        "key_factors": [],
    }
