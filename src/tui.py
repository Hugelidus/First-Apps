"""Interfaz interactiva de terminal para el sistema de pronósticos."""

import os
import sys

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from src.config import BANKROLL, API_FOOTBALL_KEY, ODDS_API_KEY, ANTHROPIC_API_KEY, FOOTBALL_DATA_KEY
from src.data import odds_api, football_data
from src.features.ratings import PiRating
from src.models.goals_model import GoalsModel
from src.betting.value_bets import find_value_bets
from src.utils.display import show_prediction

console = Console()

BANNER = r"""
[bold cyan]
 ____       _   ___    _
| __ )  ___| |_|_ _|  / \
|  _ \ / _ \ __|| |  / _ \
| |_) |  __/ |_ | | / ___ \
|____/ \___|\__|___/_/   \_\
[/bold cyan]
[dim]Sistema de Pronosticos Deportivos - Champions League 2025-26[/dim]
"""


def show_menu():
    """Muestra el menú principal."""
    console.print(BANNER)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Opcion", style="bold cyan", justify="right")
    table.add_column("Descripcion")
    table.add_row("1", "Proximos partidos")
    table.add_row("2", "Analizar un partido")
    table.add_row("3", "Ultimos resultados")
    table.add_row("4", "Clasificacion")
    table.add_row("5", "Goleadores")
    table.add_row("6", "Stats de un equipo")
    table.add_row("7", "Demo (sin APIs)")
    table.add_row("8", "Estado de las APIs")
    table.add_row("0", "Salir")
    console.print(Panel(table, title="[bold]Menu Principal[/bold]", border_style="cyan"))


def menu_status():
    """Muestra el estado de las APIs."""
    console.print("\n[bold]Estado de APIs:[/bold]")
    apis = {
        "Football-Data.org": bool(FOOTBALL_DATA_KEY),
        "The Odds API": bool(ODDS_API_KEY),
        "Anthropic (Claude)": bool(ANTHROPIC_API_KEY),
    }
    for name, ok in apis.items():
        icon = "[green]✔ OK[/green]" if ok else "[red]✘ NO CONFIGURADA[/red]"
        console.print(f"  {name}: {icon}")
    console.print(f"\n  Bankroll: [bold]${BANKROLL:.2f}[/bold]")


def menu_proximos():
    """Muestra los próximos partidos."""
    console.print("\n[bold]Obteniendo proximos partidos...[/bold]\n")
    try:
        matches = football_data.get_upcoming_matches()
        if not matches:
            console.print("[yellow]No hay partidos proximos programados.[/yellow]")
            return

        t = Table(title="Proximos Partidos - Champions League", show_header=True)
        t.add_column("#", justify="right", style="dim")
        t.add_column("Fecha", justify="center")
        t.add_column("Hora", justify="center", style="dim")
        t.add_column("Local", justify="right", style="green")
        t.add_column("vs", justify="center", style="dim")
        t.add_column("Visitante", justify="left", style="red")
        t.add_column("Fase", justify="center")

        # Filtrar partidos sin equipos asignados (cuartos/semis TBD)
        valid = [m for m in matches if m["homeTeam"].get("name") and m["awayTeam"].get("name")]
        for i, m in enumerate(valid[:20], 1):
            date = m.get("utcDate", "")[:10]
            time = m.get("utcDate", "")[11:16]
            home = m["homeTeam"]["name"]
            away = m["awayTeam"]["name"]
            stage = m.get("stage", "").replace("_", " ").title()
            t.add_row(str(i), date, time, home, "vs", away, stage)

        console.print(t)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def menu_analizar():
    """Análisis interactivo de un partido."""
    console.print("\n[bold]Analizar Partido[/bold]")

    # Mostrar próximos partidos para elegir
    try:
        all_matches = football_data.get_upcoming_matches()
        matches = [m for m in all_matches if m["homeTeam"].get("name") and m["awayTeam"].get("name")]
        if matches:
            console.print("\n[dim]Proximos partidos disponibles:[/dim]")
            for i, m in enumerate(matches[:10], 1):
                date = m.get("utcDate", "")[:10]
                home = m["homeTeam"]["name"]
                away = m["awayTeam"]["name"]
                console.print(f"  [cyan]{i}[/cyan]. {home} vs {away} ({date})")
            console.print(f"  [cyan]0[/cyan]. Escribir manualmente\n")

            try:
                choice = input("  Elige partido (numero): ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(matches[:10]):
                    m = matches[int(choice) - 1]
                    home = m["homeTeam"]["name"]
                    away = m["awayTeam"]["name"]
                elif choice == "0":
                    home = input("  Equipo local: ").strip()
                    away = input("  Equipo visitante: ").strip()
                else:
                    home = input("  Equipo local: ").strip()
                    away = input("  Equipo visitante: ").strip()
            except (KeyboardInterrupt, EOFError):
                return
        else:
            try:
                home = input("  Equipo local: ").strip()
                away = input("  Equipo visitante: ").strip()
            except (KeyboardInterrupt, EOFError):
                return
    except Exception:
        try:
            home = input("  Equipo local: ").strip()
            away = input("  Equipo visitante: ").strip()
        except (KeyboardInterrupt, EOFError):
            return

    if not home or not away:
        return

    use_ai = False
    if ANTHROPIC_API_KEY:
        try:
            ai_choice = input("  Incluir analisis IA? (s/N): ").strip().lower()
            use_ai = ai_choice in ("s", "si", "y", "yes")
        except (KeyboardInterrupt, EOFError):
            return

    console.print(f"\n[bold]Analizando: {home} vs {away}...[/bold]\n")

    pi = PiRating()
    goals_model = GoalsModel()

    lambda_home, lambda_away = pi.predict_goals(home, away)
    goals_pred = goals_model.predict(lambda_home, lambda_away)
    probs = goals_pred["result_1x2"]

    llm_result = None
    final_probs = probs
    if use_ai:
        console.print("[dim]Consultando analisis contextual con IA (puede tardar ~30s)...[/dim]")
        try:
            from src.llm.analyzer import analyze_match, apply_adjustments
            llm_result = analyze_match(
                home, away, probs, competition_stage="Champions League - Octavos de Final",
            )
            if llm_result.get("adjustments"):
                adj = llm_result["adjustments"]
                if any(v != 0 for v in adj.values()):
                    final_probs = apply_adjustments(probs, adj)
                    console.print("[green]Probabilidades ajustadas con contexto IA.[/green]")
        except Exception as e:
            console.print(f"[red]Error IA: {e}[/red]")

    # Buscar value bets con cuotas reales
    value_bets = []
    if ODDS_API_KEY:
        try:
            odds_data = odds_api.get_odds_1x2()
            for event in odds_data:
                eh = event.get("home_team", "").lower()
                ea = event.get("away_team", "").lower()
                if home.lower() in eh or away.lower() in ea:
                    for bk in event.get("bookmakers", []):
                        for mkt in bk.get("markets", []):
                            if mkt.get("key") == "h2h":
                                outcomes = mkt.get("outcomes", [])
                                odds_dict = {}
                                for o in outcomes:
                                    name = o.get("name", "").lower()
                                    price = o.get("price", 0)
                                    if "home" in name or home.lower() in name:
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
            pass

    show_prediction(home, away, final_probs, goals_pred, value_bets, llm_result)


def menu_resultados():
    """Muestra los últimos resultados."""
    console.print("\n[bold]Ultimos resultados - Champions League[/bold]\n")
    try:
        matches = football_data.get_finished_matches()

        t = Table(show_header=True)
        t.add_column("Fecha", justify="center", style="dim")
        t.add_column("Local", justify="right")
        t.add_column("", justify="center", style="bold")
        t.add_column("Visitante", justify="left")
        t.add_column("Fase", justify="center", style="dim")

        for m in matches[:15]:
            date = m.get("utcDate", "")[:10]
            home = m["homeTeam"]["name"]
            away = m["awayTeam"]["name"]
            ft = m.get("score", {}).get("fullTime", {})
            gh = ft.get("home", "?")
            ga = ft.get("away", "?")
            score = f"{gh}-{ga}"
            stage = m.get("stage", "").replace("_", " ").title()
            home_style = "bold green" if gh is not None and ga is not None and gh > ga else ""
            away_style = "bold green" if gh is not None and ga is not None and ga > gh else ""
            t.add_row(
                date,
                Text(home, style=home_style),
                score,
                Text(away, style=away_style),
                stage,
            )

        console.print(t)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def menu_clasificacion():
    """Muestra la clasificación."""
    console.print("\n[bold]Obteniendo clasificacion...[/bold]")
    try:
        standings = football_data.get_standings()
        if standings:
            for group in standings:
                table_name = group.get("group", group.get("stage", ""))
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


def menu_goleadores():
    """Muestra los goleadores de la Champions."""
    console.print("\n[bold]Goleadores - Champions League[/bold]\n")
    try:
        scorers = football_data.get_scorers(15)

        t = Table(show_header=True)
        t.add_column("#", justify="right", style="dim")
        t.add_column("Jugador", justify="left")
        t.add_column("Equipo", justify="left", style="dim")
        t.add_column("Goles", justify="center", style="bold green")
        t.add_column("Asist.", justify="center", style="cyan")
        t.add_column("PJ", justify="center")

        for i, s in enumerate(scorers, 1):
            player = s.get("player", {})
            team = s.get("team", {})
            t.add_row(
                str(i),
                player.get("name", "?"),
                team.get("name", "?"),
                str(s.get("goals", 0) or 0),
                str(s.get("assists", 0) or 0),
                str(s.get("playedMatches", 0) or 0),
            )

        console.print(t)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


def menu_stats_equipo():
    """Muestra estadísticas detalladas de un equipo."""
    console.print("\n[bold]Estadisticas de Equipo - Champions League 2025-26[/bold]\n")

    try:
        name = input("  Nombre del equipo: ").strip()
        if not name:
            return
    except (KeyboardInterrupt, EOFError):
        return

    team = football_data.search_team(name)
    if not team:
        console.print(f"[red]No se encontro el equipo '{name}' en la Champions.[/red]")
        return

    team_id = team["id"]
    team_name = team["name"]
    console.print(f"\n[bold]{team_name}[/bold]\n")

    # Stats generales
    stats = football_data.get_team_stats_summary(team_id)
    if stats["played"] == 0:
        console.print("[yellow]No hay partidos jugados todavia.[/yellow]")
        return

    t = Table(title="Resumen General", show_header=True)
    t.add_column("PJ", justify="center")
    t.add_column("G", justify="center", style="green")
    t.add_column("E", justify="center", style="yellow")
    t.add_column("P", justify="center", style="red")
    t.add_column("GF", justify="center")
    t.add_column("GC", justify="center")
    t.add_column("Goles/P", justify="center", style="bold")
    t.add_column("Enc/P", justify="center")
    t.add_column("Valla 0", justify="center", style="cyan")
    t.add_row(
        str(stats["played"]),
        str(stats["wins"]),
        str(stats["draws"]),
        str(stats["losses"]),
        str(stats["goals_for"]),
        str(stats["goals_against"]),
        str(stats["goals_per_match"]),
        str(stats["conceded_per_match"]),
        str(stats["clean_sheets"]),
    )
    console.print(t)

    # Partidos del equipo
    team_matches = football_data.get_team_matches(team_id)
    finished = [m for m in team_matches if m["status"] == "FINISHED"]
    finished.sort(key=lambda x: x.get("utcDate", ""), reverse=True)

    if finished:
        t2 = Table(title="Partidos Jugados", show_header=True)
        t2.add_column("Fecha", justify="center", style="dim")
        t2.add_column("Rival", justify="left")
        t2.add_column("Resultado", justify="center", style="bold")
        t2.add_column("Sede", justify="center")
        t2.add_column("Fase", justify="center", style="dim")

        for m in finished:
            date = m.get("utcDate", "")[:10]
            ft = m.get("score", {}).get("fullTime", {})
            gh = ft.get("home", 0) or 0
            ga = ft.get("away", 0) or 0
            is_home = m["homeTeam"]["id"] == team_id

            if is_home:
                rival = m["awayTeam"]["name"]
                gf, gc = gh, ga
                sede = "Local"
            else:
                rival = m["homeTeam"]["name"]
                gf, gc = ga, gh
                sede = "Visitante"

            if gf > gc:
                result_style = "bold green"
                result_icon = "W"
            elif gf == gc:
                result_style = "yellow"
                result_icon = "D"
            else:
                result_style = "red"
                result_icon = "L"

            score_str = f"{gh}-{ga}"
            stage = m.get("stage", "").replace("_", " ").title()
            t2.add_row(
                date,
                rival,
                Text(f"{score_str} ({result_icon})", style=result_style),
                sede,
                stage,
            )

        console.print(t2)

    # Próximos partidos
    upcoming = [m for m in team_matches if m["status"] in ("SCHEDULED", "TIMED")]
    upcoming.sort(key=lambda x: x.get("utcDate", ""))
    if upcoming:
        t3 = Table(title="Proximos Partidos", show_header=True)
        t3.add_column("Fecha", justify="center")
        t3.add_column("Hora", justify="center", style="dim")
        t3.add_column("Rival", justify="left")
        t3.add_column("Sede", justify="center")
        t3.add_column("Fase", justify="center", style="dim")

        for m in upcoming:
            date = m.get("utcDate", "")[:10]
            time = m.get("utcDate", "")[11:16]
            is_home = m["homeTeam"]["id"] == team_id
            rival = m["awayTeam"]["name"] if is_home else m["homeTeam"]["name"]
            sede = "Local" if is_home else "Visitante"
            stage = m.get("stage", "").replace("_", " ").title()
            t3.add_row(date, time, rival, sede, stage)

        console.print(t3)


def menu_demo():
    """Demo con datos de ejemplo."""
    console.print("\n[bold]DEMO - Datos de ejemplo[/bold]\n")
    goals_model = GoalsModel()

    matches = [
        ("Real Madrid", "Bayern Munich", 1.8, 1.3),
        ("Barcelona", "PSG", 1.6, 1.4),
        ("Man City", "Inter Milan", 2.0, 0.9),
    ]

    for home, away, lh, la in matches:
        pred = goals_model.predict(lh, la)
        odds = {
            "home": round(1 / pred["result_1x2"]["home"] * 0.95, 2),
            "draw": round(1 / pred["result_1x2"]["draw"] * 0.95, 2),
            "away": round(1 / pred["result_1x2"]["away"] * 0.95, 2),
        }
        value_bets = find_value_bets(pred["result_1x2"], odds)
        show_prediction(home, away, pred["result_1x2"], pred, value_bets)


def main():
    """Loop principal de la interfaz."""
    actions = {
        "1": menu_proximos,
        "2": menu_analizar,
        "3": menu_resultados,
        "4": menu_clasificacion,
        "5": menu_goleadores,
        "6": menu_stats_equipo,
        "7": menu_demo,
        "8": menu_status,
    }

    while True:
        show_menu()
        try:
            choice = input("\n  Elige una opcion: ").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold cyan]Hasta luego![/bold cyan]\n")
            break

        if choice == "0":
            console.print("\n[bold cyan]Hasta luego![/bold cyan]\n")
            break

        action = actions.get(choice)
        if action:
            action()
            try:
                input("\n  [Presiona Enter para continuar] ")
            except (KeyboardInterrupt, EOFError):
                pass
        else:
            console.print("[red]Opcion no valida.[/red]")


if __name__ == "__main__":
    main()
