"""Demo del pipeline completo de predicciones.

Carga datos históricos, entrena ratings, y genera predicciones
para partidos de ejemplo. No requiere API keys.
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.data.historical import load_football_data_csv, get_team_results, get_league_averages
from src.predictions.engine import PredictionEngine
from src.predictions.context import format_context_summary
from src.utils.display import show_prediction

console = Console()


def run_demo():
    """Ejecuta demo completa del pipeline."""
    console.print("\n[bold]DEMO - Pipeline completo de predicciones[/bold]\n")

    # 1. Cargar datos
    console.print("[dim]1. Cargando datos historicos...[/dim]")
    df = load_football_data_csv("data/historical/champions_league.csv")
    console.print(f"   Cargados: {len(df)} partidos")
    console.print(f"   Equipos: {df['home_team'].nunique()}")
    console.print(f"   Rango: {df['date'].min().date()} a {df['date'].max().date()}")

    # 2. Entrenar motor
    console.print("\n[dim]2. Entrenando ratings con datos historicos...[/dim]")
    engine = PredictionEngine()
    info = engine.train_from_dataframe(df)
    console.print(f"   Partidos procesados: {info['matches_processed']}")
    console.print(f"   Equipos con rating: {info['teams']}")
    console.print(f"   Media goles/partido: {info['avg_goals']:.2f}")

    # 3. Rankings de Elo
    console.print("\n[dim]3. Rankings Elo actuales:[/dim]")
    all_teams = sorted(
        set(df["home_team"].tolist() + df["away_team"].tolist()),
        key=lambda t: engine.elo.get_rating(t),
        reverse=True,
    )

    ranking_table = Table(title="Top 15 Elo Rankings", show_header=True)
    ranking_table.add_column("#", justify="right", style="dim")
    ranking_table.add_column("Equipo", justify="left")
    ranking_table.add_column("Elo", justify="center", style="bold")
    ranking_table.add_column("Pi (H/A)", justify="center")

    for i, team in enumerate(all_teams[:15], 1):
        pi = engine.pi.get_ratings(team)
        ranking_table.add_row(
            str(i),
            team,
            f"{engine.elo.get_rating(team):.0f}",
            f"{pi['home']:.2f} / {pi['away']:.2f}",
        )
    console.print(ranking_table)

    # 4. Predicciones de partidos
    fixtures = [
        ("Real Madrid", "Bayern Munich"),
        ("Man City", "Barcelona"),
        ("Liverpool", "PSG"),
        ("Inter Milan", "Borussia Dortmund"),
        ("Arsenal", "Atletico Madrid"),
    ]

    console.print(f"\n[dim]4. Predicciones para {len(fixtures)} partidos:[/dim]\n")

    for home, away in fixtures:
        pred = engine.predict_match(home, away, use_llm=False)

        # Simular cuotas de bookmaker (basadas en nuestras probs + margen)
        probs = pred["probabilities"]
        margin = 1.06
        sim_odds = {
            "home": round(margin / max(probs["home"], 0.01), 2),
            "draw": round(margin / max(probs["draw"], 0.01), 2),
            "away": round(margin / max(probs["away"], 0.01), 2),
        }

        # Recalcular value bets con cuotas simuladas
        from src.betting.value_bets import find_value_bets
        value_bets = find_value_bets(probs, sim_odds, min_value=0.02)

        show_prediction(
            home, away, probs, pred["goals"],
            value_bets=value_bets,
        )

        # Mostrar detalles extra
        detail_table = Table(show_header=True, title="Detalle", width=60)
        detail_table.add_column("Metrica", justify="left")
        detail_table.add_column("Local", justify="center")
        detail_table.add_column("Visitante", justify="center")

        detail_table.add_row(
            "Elo",
            f"{pred['ratings']['elo_home']:.0f}",
            f"{pred['ratings']['elo_away']:.0f}",
        )
        detail_table.add_row(
            "Goles esperados",
            f"{pred['goals']['expected_home']:.2f}",
            f"{pred['goals']['expected_away']:.2f}",
        )
        detail_table.add_row(
            "Fza. ataque",
            f"{pred['strength']['home_attack']:.2f}",
            f"{pred['strength']['away_attack']:.2f}",
        )
        detail_table.add_row(
            "Deb. defensa",
            f"{pred['strength']['home_defense']:.2f}",
            f"{pred['strength']['away_defense']:.2f}",
        )
        detail_table.add_row(
            "Momentum",
            f"{pred['form']['home']['momentum']:+.2f}",
            f"{pred['form']['away']['momentum']:+.2f}",
        )
        console.print(detail_table)

        # Últimos partidos
        if pred["form"]["home"]["last_matches"]:
            console.print(f"  [green]{home}[/green]: " + " | ".join(pred["form"]["home"]["last_matches"][:3]))
        if pred["form"]["away"]["last_matches"]:
            console.print(f"  [red]{away}[/red]: " + " | ".join(pred["form"]["away"]["last_matches"][:3]))
        console.print()

    # 5. Perfil de equipo
    console.print("\n[dim]5. Perfil detallado de un equipo:[/dim]\n")
    profile = engine.get_team_profile("Real Madrid")
    console.print(Panel(
        f"Elo: {profile['elo']}\n"
        f"Pi (H/A): {profile['pi_ratings']['home']:.2f} / {profile['pi_ratings']['away']:.2f}\n"
        f"Ataque: {profile['attack_strength']:.2f} | Defensa: {profile['defense_weakness']:.2f}\n"
        f"Momentum: {profile['momentum']:+.2f}\n"
        f"Partidos: {profile['total_matches']}\n\n"
        f"Ultimos 5:\n" + "\n".join(f"  {m}" for m in profile["last_5"]),
        title="[bold]Real Madrid[/bold]",
        border_style="green",
    ))


if __name__ == "__main__":
    run_demo()
