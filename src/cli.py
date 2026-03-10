"""CLI principal del sistema de pronósticos deportivos."""

import click
from rich.console import Console

from src.config import BANKROLL, API_FOOTBALL_KEY, ODDS_API_KEY, ANTHROPIC_API_KEY
from src.data import api_football, odds_api, football_data
from src.features.ratings import EloRating, PiRating
from src.features.form import home_away_form, momentum
from src.features.stats import attack_defense_strength, head_to_head_stats
from src.models.goals_model import GoalsModel
from src.llm.analyzer import analyze_match, apply_adjustments
from src.betting.value_bets import find_value_bets, find_over_under_value, best_odds
from src.betting.kelly import recommended_stake
from src.utils.display import (
    console, show_prediction, show_fixtures_table, show_value_bets_summary,
)

CURRENT_SEASON = 2025


@click.group()
def cli():
    """Sistema de Pronosticos Deportivos - Champions League"""
    pass


@cli.command()
def status():
    """Muestra el estado de las APIs configuradas."""
    console.print("\n[bold]Estado de APIs:[/bold]")
    apis = {
        "API-Football": bool(API_FOOTBALL_KEY),
        "The Odds API": bool(ODDS_API_KEY),
        "Anthropic (Claude)": bool(ANTHROPIC_API_KEY),
    }
    for name, configured in apis.items():
        icon = "[green]OK[/green]" if configured else "[red]NO CONFIGURADA[/red]"
        console.print(f"  {name}: {icon}")
    console.print(f"\n  Bankroll: ${BANKROLL:.2f}")
    console.print()


@cli.command()
def proximos():
    """Muestra los próximos partidos de Champions League."""
    console.print("\n[bold]Obteniendo proximos partidos...[/bold]")
    try:
        fixtures = api_football.get_upcoming_fixtures(CURRENT_SEASON)
        if not fixtures:
            console.print("[yellow]No hay partidos proximos programados.[/yellow]")
            return
        show_fixtures_table(fixtures[:20])
    except Exception as e:
        console.print(f"[red]Error obteniendo partidos: {e}[/red]")
        console.print("[dim]Verifica tu API_FOOTBALL_KEY en el archivo .env[/dim]")


@cli.command()
@click.argument("home_team")
@click.argument("away_team")
@click.option("--con-ia/--sin-ia", default=True, help="Incluir análisis de Claude")
def analizar(home_team: str, away_team: str, con_ia: bool):
    """Análisis completo de un partido específico."""
    console.print(f"\n[bold]Analizando: {home_team} vs {away_team}[/bold]\n")

    # Inicializar modelos
    pi = PiRating()
    elo = EloRating()
    goals_model = GoalsModel()

    # Predicción de goles con Pi-ratings
    lambda_home, lambda_away = pi.predict_goals(home_team, away_team)
    goals_pred = goals_model.predict(lambda_home, lambda_away)

    # Probabilidades 1X2
    probs = goals_pred["result_1x2"]

    # Análisis LLM
    llm_result = None
    final_probs = probs
    if con_ia:
        console.print("[dim]Consultando analisis contextual con IA...[/dim]")
        try:
            llm_result = analyze_match(
                home_team, away_team, probs,
                competition_stage="Champions League",
            )
            if llm_result.get("adjustments"):
                final_probs = apply_adjustments(probs, llm_result["adjustments"])
        except Exception as e:
            console.print(f"[dim]Analisis IA no disponible: {e}[/dim]")

    # Buscar value bets (necesita cuotas reales)
    value_bets = []
    try:
        odds_data = odds_api.get_odds_1x2()
        # Buscar cuotas del partido
        for event in odds_data:
            event_home = event.get("home_team", "").lower()
            event_away = event.get("away_team", "").lower()
            if home_team.lower() in event_home or away_team.lower() in event_away:
                for bookmaker in event.get("bookmakers", []):
                    for market in bookmaker.get("markets", []):
                        if market.get("key") == "h2h":
                            outcomes = market.get("outcomes", [])
                            odds_dict = {}
                            for o in outcomes:
                                name = o.get("name", "").lower()
                                price = o.get("price", 0)
                                if "home" in name or home_team.lower() in name.lower():
                                    odds_dict["home"] = price
                                elif "draw" in name:
                                    odds_dict["draw"] = price
                                else:
                                    odds_dict["away"] = price
                            if odds_dict:
                                value_bets = find_value_bets(final_probs, odds_dict)
                                break
                break
    except Exception:
        pass  # Sin cuotas disponibles, no hay value bets

    show_prediction(home_team, away_team, final_probs, goals_pred, value_bets, llm_result)


@cli.command()
def valuebets():
    """Detecta value bets en los próximos partidos."""
    console.print("\n[bold]Buscando value bets...[/bold]\n")
    console.print("[yellow]Necesitas API keys configuradas para obtener cuotas reales.[/yellow]")
    console.print("[dim]Configura ODDS_API_KEY y API_FOOTBALL_KEY en .env[/dim]\n")


@cli.command()
def clasificacion():
    """Muestra la clasificación actual de Champions League."""
    console.print("\n[bold]Obteniendo clasificacion...[/bold]")
    try:
        standings = football_data.get_standings()
        if standings:
            for group in standings:
                table_name = group.get("group", group.get("stage", ""))
                from rich.table import Table
                t = Table(title=table_name, show_header=True)
                t.add_column("Pos", justify="right", style="dim")
                t.add_column("Equipo", justify="left")
                t.add_column("PJ", justify="center")
                t.add_column("G", justify="center")
                t.add_column("E", justify="center")
                t.add_column("P", justify="center")
                t.add_column("GF", justify="center")
                t.add_column("GC", justify="center")
                t.add_column("Pts", justify="center", style="bold")
                for entry in group.get("table", []):
                    team = entry.get("team", {})
                    t.add_row(
                        str(entry.get("position", "")),
                        team.get("name", "?"),
                        str(entry.get("playedGames", 0)),
                        str(entry.get("won", 0)),
                        str(entry.get("draw", 0)),
                        str(entry.get("lost", 0)),
                        str(entry.get("goalsFor", 0)),
                        str(entry.get("goalsAgainst", 0)),
                        str(entry.get("points", 0)),
                    )
                console.print(t)
        else:
            console.print("[yellow]No se encontro clasificacion.[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@cli.command()
def demo():
    """Demo con datos de ejemplo (no requiere API keys)."""
    console.print("\n[bold]DEMO - Datos de ejemplo[/bold]\n")

    goals_model = GoalsModel()

    # Simular un partido
    matches = [
        ("Real Madrid", "Bayern Munich", 1.8, 1.3),
        ("Barcelona", "PSG", 1.6, 1.4),
        ("Man City", "Inter Milan", 2.0, 0.9),
    ]

    for home, away, lh, la in matches:
        pred = goals_model.predict(lh, la)

        # Simular cuotas
        odds = {
            "home": round(1 / pred["result_1x2"]["home"], 2),
            "draw": round(1 / pred["result_1x2"]["draw"], 2),
            "away": round(1 / pred["result_1x2"]["away"], 2),
        }
        # Añadir margen de bookmaker (5%)
        odds = {k: round(v * 0.95, 2) for k, v in odds.items()}

        value_bets = find_value_bets(pred["result_1x2"], odds)
        show_prediction(home, away, pred["result_1x2"], pred, value_bets)


if __name__ == "__main__":
    cli()
