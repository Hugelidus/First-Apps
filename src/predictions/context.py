"""Recopilación de contexto para análisis con LLM.

Reúne información no-estadística que afecta al resultado:
- Lesiones y sanciones
- Estado de forma narrativo
- Importancia del partido (clasificación, eliminación)
- Noticias y rumores recientes del club

Este contexto se envía a Claude para que ajuste las probabilidades ML.
"""

import json

import anthropic

from src.config import ANTHROPIC_API_KEY


CONTEXT_SYSTEM_PROMPT = """Eres un investigador de fútbol. Tu trabajo es recopilar
y estructurar información contextual sobre un partido de Champions League.

Basándote en tu conocimiento, proporciona información sobre:
1. LESIONES: Jugadores clave lesionados o sancionados de cada equipo
2. FORMA: Estado anímico y racha del equipo (más allá de los números)
3. TÁCTICA: Cambios tácticos recientes, nuevo entrenador, cambio de sistema
4. MOTIVACIÓN: Qué se juega cada equipo (clasificación, eliminación, honor)
5. NOTICIAS: Rumores relevantes (traspasos, conflictos internos, problemas financieros)
6. HISTORIAL: Datos curiosos del enfrentamiento directo

IMPORTANTE:
- Sé específico: nombres de jugadores, fechas, datos concretos
- Si no estás seguro de algo, indícalo explícitamente
- No inventes información
- Tu corte de conocimiento puede no incluir los datos más recientes

Responde en JSON con esta estructura:
{
    "home_team": {
        "injuries": [{"player": "nombre", "status": "lesionado/duda/sancionado", "impact": "alto/medio/bajo"}],
        "form_narrative": "descripción del momento del equipo",
        "tactical_notes": "cambios tácticos relevantes",
        "motivation": "qué se juega",
        "news": ["noticia relevante 1", "noticia relevante 2"],
        "key_absences_impact": "cómo afectan las bajas al rendimiento esperado"
    },
    "away_team": {
        "injuries": [...],
        "form_narrative": "...",
        "tactical_notes": "...",
        "motivation": "...",
        "news": ["..."],
        "key_absences_impact": "..."
    },
    "match_context": {
        "competition_stage": "fase de la competición",
        "stakes": "qué hay en juego para cada equipo",
        "historical_notes": "datos relevantes del historial",
        "external_factors": "factores externos (clima, viajes, calendario congestionado)"
    },
    "confidence": "low/medium/high",
    "data_freshness": "indicar hasta cuándo tienes datos fiables"
}"""


def gather_match_context(
    home_team: str,
    away_team: str,
    match_date: str | None = None,
    competition_stage: str | None = None,
    additional_info: str | None = None,
) -> dict:
    """Recopila contexto de un partido usando Claude.

    Claude usa su conocimiento para proporcionar información sobre
    lesiones, forma, tática, motivación y noticias de ambos equipos.

    Args:
        home_team: Nombre del equipo local.
        away_team: Nombre del equipo visitante.
        match_date: Fecha del partido (para que Claude contextualice).
        competition_stage: Fase de la competición.
        additional_info: Información extra que el usuario quiera añadir.

    Returns:
        Dict estructurado con todo el contexto.
    """
    if not ANTHROPIC_API_KEY:
        return _empty_context(home_team, away_team)

    prompt_parts = [
        f"Partido de Champions League: {home_team} (local) vs {away_team} (visitante)",
    ]
    if match_date:
        prompt_parts.append(f"Fecha: {match_date}")
    if competition_stage:
        prompt_parts.append(f"Fase: {competition_stage}")
    if additional_info:
        prompt_parts.append(f"Info adicional: {additional_info}")

    prompt_parts.append(
        "\nProporciona toda la información contextual que tengas sobre "
        "este partido. Sé específico con nombres de jugadores y datos concretos."
    )

    user_message = "\n".join(prompt_parts)

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2048,
            system=CONTEXT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        return _parse_context(response.content[0].text, home_team, away_team)
    except Exception as e:
        ctx = _empty_context(home_team, away_team)
        ctx["error"] = str(e)
        return ctx


def build_analyzer_context(context: dict) -> dict:
    """Transforma el contexto recopilado al formato que espera analyzer.py."""
    injuries = []
    for side in ["home_team", "away_team"]:
        team_data = context.get(side, {})
        for inj in team_data.get("injuries", []):
            injuries.append({
                "player": {"name": inj.get("player", "?")},
                "team": {"name": side.replace("_team", "")},
                "type": inj.get("status", "?"),
                "impact": inj.get("impact", "?"),
            })

    match_ctx = context.get("match_context", {})

    # Construir resumen de clasificación/stakes
    standings_parts = []
    for side in ["home_team", "away_team"]:
        team_data = context.get(side, {})
        if team_data.get("motivation"):
            standings_parts.append(f"{side}: {team_data['motivation']}")

    standings = " | ".join(standings_parts) if standings_parts else None

    return {
        "injuries": injuries,
        "standings": standings,
        "stage": match_ctx.get("competition_stage", "Champions League"),
    }


def format_context_summary(context: dict) -> str:
    """Genera un resumen legible del contexto para mostrar en CLI."""
    lines = []

    for side_key, label in [("home_team", "LOCAL"), ("away_team", "VISITANTE")]:
        team = context.get(side_key, {})
        lines.append(f"\n{'='*40}")
        lines.append(f"  {label}")
        lines.append(f"{'='*40}")

        if team.get("form_narrative"):
            lines.append(f"  Forma: {team['form_narrative']}")

        if team.get("injuries"):
            lines.append("  Bajas:")
            for inj in team["injuries"]:
                impact_icon = {"alto": "!!!", "medio": "!!", "bajo": "!"}.get(
                    inj.get("impact", ""), "?"
                )
                lines.append(
                    f"    [{impact_icon}] {inj.get('player', '?')} - {inj.get('status', '?')}"
                )

        if team.get("tactical_notes"):
            lines.append(f"  Tactica: {team['tactical_notes']}")

        if team.get("motivation"):
            lines.append(f"  Motivacion: {team['motivation']}")

        if team.get("news"):
            lines.append("  Noticias:")
            for news in team["news"][:3]:
                lines.append(f"    > {news}")

        if team.get("key_absences_impact"):
            lines.append(f"  Impacto bajas: {team['key_absences_impact']}")

    match_ctx = context.get("match_context", {})
    if match_ctx:
        lines.append(f"\n{'='*40}")
        lines.append("  CONTEXTO DEL PARTIDO")
        lines.append(f"{'='*40}")
        if match_ctx.get("stakes"):
            lines.append(f"  En juego: {match_ctx['stakes']}")
        if match_ctx.get("historical_notes"):
            lines.append(f"  Historial: {match_ctx['historical_notes']}")
        if match_ctx.get("external_factors"):
            lines.append(f"  Factores externos: {match_ctx['external_factors']}")

    if context.get("confidence"):
        lines.append(f"\n  Confianza datos: {context['confidence']}")
    if context.get("data_freshness"):
        lines.append(f"  Frescura datos: {context['data_freshness']}")

    return "\n".join(lines)


def _parse_context(text: str, home_team: str, away_team: str) -> dict:
    """Parsea respuesta JSON de Claude."""
    try:
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError):
        return _empty_context(home_team, away_team)


def _empty_context(home_team: str, away_team: str) -> dict:
    empty_team = {
        "injuries": [],
        "form_narrative": "Sin datos disponibles",
        "tactical_notes": "",
        "motivation": "",
        "news": [],
        "key_absences_impact": "",
    }
    return {
        "home_team": empty_team.copy(),
        "away_team": empty_team.copy(),
        "match_context": {
            "competition_stage": "Champions League",
            "stakes": "",
            "historical_notes": "",
            "external_factors": "",
        },
        "confidence": "low",
        "data_freshness": "Sin datos",
    }
