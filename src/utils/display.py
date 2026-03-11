"""Formateo de resultados para la CLI usando Rich."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


def show_prediction(
    home_team: str,
    away_team: str,
    probs: dict[str, float],
    goals: dict | None = None,
    value_bets: list[dict] | None = None,
    llm_analysis: dict | None = None,
):
    """Muestra predicción completa de un partido."""
    # Header
    console.print()
    console.rule(f"[bold]{home_team} vs {away_team}[/bold]")

    # Tabla 1X2
    table = Table(title="Prediccion 1X2", show_header=True)
    table.add_column("Local", justify="center", style="green")
    table.add_column("Empate", justify="center", style="yellow")
    table.add_column("Visitante", justify="center", style="red")
    table.add_row(
        f"{probs['home']:.1%}",
        f"{probs['draw']:.1%}",
        f"{probs['away']:.1%}",
    )
    console.print(table)

    # Over/Under
    if goals and "over_under" in goals:
        ou_table = Table(title="Over/Under", show_header=True)
        ou_table.add_column("Linea", justify="center")
        ou_table.add_column("Over", justify="center", style="green")
        ou_table.add_column("Under", justify="center", style="red")
        for line, probs_ou in goals["over_under"].items():
            ou_table.add_row(line, f"{probs_ou['over']:.1%}", f"{probs_ou['under']:.1%}")
        console.print(ou_table)

    # Marcadores más probables
    if goals and "most_likely_scores" in goals:
        score_table = Table(title="Marcadores mas probables", show_header=True)
        score_table.add_column("Marcador", justify="center")
        score_table.add_column("Probabilidad", justify="center")
        for s in goals["most_likely_scores"][:5]:
            score_table.add_row(f"{s['home']}-{s['away']}", f"{s['prob']:.1%}")
        console.print(score_table)

    # Value bets
    if value_bets:
        vb_table = Table(title="[bold]VALUE BETS[/bold]", show_header=True)
        vb_table.add_column("Mercado", justify="left")
        vb_table.add_column("Valor", justify="center", style="bold green")
        vb_table.add_column("Cuota", justify="center")
        vb_table.add_column("Edge", justify="center")
        vb_table.add_column("Stake", justify="center", style="bold")
        for vb in value_bets:
            market = vb.get("market", vb.get("outcome", "?"))
            vb_table.add_row(
                market,
                f"{vb['value']:.1%}",
                f"{vb['odds']:.2f}",
                f"{vb['edge']:.1%}",
                f"${vb['stake']:.2f}",
            )
        console.print(vb_table)
    else:
        console.print("[dim]No se detectaron value bets para este partido.[/dim]")

    # Análisis LLM
    if llm_analysis and llm_analysis.get("analysis"):
        # Stats detalladas si las hay
        stats = llm_analysis.get("stats")
        if stats:
            st = Table(title="Estadisticas Recientes (via IA)", show_header=True)
            st.add_column("", justify="left", style="dim")
            st.add_column(home_team, justify="center", style="green")
            st.add_column(away_team, justify="center", style="red")

            home_st = stats.get("home", {})
            away_st = stats.get("away", {})

            rows = [
                ("Forma", home_st.get("form", "-"), away_st.get("form", "-")),
                ("Goles/partido", _fmt_num(home_st.get("goals_per_match")), _fmt_num(away_st.get("goals_per_match"))),
                ("Tiros a puerta/p", _fmt_num(home_st.get("shots_on_target_per_match")), _fmt_num(away_st.get("shots_on_target_per_match"))),
                ("Paradas GK/p", _fmt_num(home_st.get("goalkeeper_saves_per_match")), _fmt_num(away_st.get("goalkeeper_saves_per_match"))),
                ("Valla invicta", str(home_st.get("clean_sheets", "-")), str(away_st.get("clean_sheets", "-"))),
            ]

            for label, hv, av in rows:
                st.add_row(label, hv, av)

            # Bajas
            h_abs = home_st.get("key_absences", [])
            a_abs = away_st.get("key_absences", [])
            if h_abs or a_abs:
                st.add_row(
                    "Bajas clave",
                    ", ".join(h_abs) if h_abs else "-",
                    ", ".join(a_abs) if a_abs else "-",
                )

            console.print(st)

        console.print(Panel(
            llm_analysis["analysis"],
            title=f"Analisis IA [confianza: {llm_analysis.get('confidence', '?')}]",
            border_style="blue",
        ))
        if llm_analysis.get("key_factors"):
            for factor in llm_analysis["key_factors"]:
                console.print(f"  [blue]>[/blue] {factor}")

    console.print()


def _fmt_num(val) -> str:
    """Formatea un número o devuelve '-'."""
    if val is None:
        return "-"
    if isinstance(val, (int, float)):
        return f"{val:.1f}"
    return str(val)


def show_fixtures_table(fixtures: list[dict]):
    """Muestra tabla de próximos partidos."""
    table = Table(title="Proximos Partidos - Champions League", show_header=True)
    table.add_column("#", justify="right", style="dim")
    table.add_column("Fecha", justify="center")
    table.add_column("Local", justify="right", style="green")
    table.add_column("vs", justify="center", style="dim")
    table.add_column("Visitante", justify="left", style="red")
    table.add_column("Fase", justify="center")

    for i, f in enumerate(fixtures, 1):
        fixture = f.get("fixture", {})
        teams = f.get("teams", {})
        league = f.get("league", {})

        table.add_row(
            str(i),
            fixture.get("date", "?")[:10],
            teams.get("home", {}).get("name", "?"),
            "vs",
            teams.get("away", {}).get("name", "?"),
            league.get("round", "?"),
        )

    console.print(table)


def show_value_bets_summary(all_value_bets: list[dict]):
    """Muestra resumen de todas las value bets detectadas."""
    if not all_value_bets:
        console.print("[yellow]No se detectaron value bets en los proximos partidos.[/yellow]")
        return

    table = Table(title="[bold]RESUMEN VALUE BETS[/bold]", show_header=True)
    table.add_column("Partido", justify="left")
    table.add_column("Mercado", justify="left")
    table.add_column("Valor", justify="center", style="bold green")
    table.add_column("Cuota", justify="center")
    table.add_column("Prob", justify="center")
    table.add_column("Stake", justify="center", style="bold")

    for vb in all_value_bets:
        table.add_row(
            vb.get("match", "?"),
            vb.get("market", vb.get("outcome", "?")),
            f"{vb['value']:.1%}",
            f"{vb['odds']:.2f}",
            f"{vb['our_prob']:.1%}",
            f"${vb['stake']:.2f}",
        )

    console.print(table)
