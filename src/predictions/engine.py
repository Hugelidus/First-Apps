"""Motor de predicciones: combina datos históricos + modelos + contexto LLM.

Pipeline:
1. Cargar datos históricos
2. Entrenar ratings (Elo + Pi) con TODOS los partidos pasados
3. Calcular forma reciente de cada equipo
4. Calcular fuerza atacante/defensiva
5. Generar predicción base (Dixon-Coles + ratings)
6. Buscar contexto (lesiones, estado de forma, noticias)
7. Ajustar con LLM (Claude)
8. Calcular value bets si hay cuotas
"""

import pandas as pd

from src.data.historical import get_team_results, get_league_averages
from src.features.ratings import EloRating, PiRating
from src.features.form import home_away_form, momentum
from src.features.stats import attack_defense_strength
from src.models.goals_model import GoalsModel
from src.llm.analyzer import analyze_match, apply_adjustments
from src.predictions.context import gather_match_context, build_analyzer_context
from src.betting.value_bets import find_value_bets, find_over_under_value


class PredictionEngine:
    """Motor principal de predicciones."""

    def __init__(self):
        self.elo = EloRating()
        self.pi = PiRating()
        self.goals_model = GoalsModel()
        self.df: pd.DataFrame = pd.DataFrame()
        self.league_avg: dict = {}
        self.is_trained = False

    def train_from_dataframe(self, df: pd.DataFrame):
        """Entrena los ratings con datos históricos.

        Procesa cada partido cronológicamente para que los ratings
        evolucionen de forma realista (walk-forward).
        """
        self.df = df.sort_values("date").reset_index(drop=True)
        self.league_avg = get_league_averages(df)

        # Entrenar ratings partido a partido (orden cronológico)
        for _, row in self.df.iterrows():
            home = row["home_team"]
            away = row["away_team"]
            hg = int(row["home_goals"])
            ag = int(row["away_goals"])

            self.elo.update(home, away, hg, ag)
            self.pi.update(home, away, hg, ag)

        self.is_trained = True
        n_teams = len(set(df["home_team"].tolist() + df["away_team"].tolist()))
        return {
            "matches_processed": len(df),
            "teams": n_teams,
            "avg_goals": self.league_avg.get("avg_total_goals", 0),
        }

    def predict_match(
        self,
        home_team: str,
        away_team: str,
        use_llm: bool = False,
        context: dict | None = None,
        odds: dict | None = None,
    ) -> dict:
        """Genera predicción completa para un partido.

        Args:
            home_team: Nombre del equipo local.
            away_team: Nombre del equipo visitante.
            use_llm: Si True, consulta a Claude para ajuste contextual.
            context: Dict con info contextual (lesiones, noticias, etc.).
            odds: Dict con cuotas {home, draw, away} para calcular value bets.

        Returns:
            Dict con predicción completa.
        """
        if not self.is_trained:
            raise RuntimeError("Entrena el motor primero con train_from_dataframe()")

        # --- 1. Ratings actuales ---
        elo_pred = self.elo.predict(home_team, away_team)
        pi_goals = self.pi.predict_goals(home_team, away_team)

        # --- 2. Forma reciente ---
        home_results = get_team_results(self.df, home_team, n_last=10)
        away_results = get_team_results(self.df, away_team, n_last=10)

        home_form = home_away_form(home_results)
        away_form = home_away_form(away_results)

        home_mom = momentum(home_results)
        away_mom = momentum(away_results)

        # --- 3. Fuerza atacante/defensiva ---
        avg = self.league_avg.get("avg_goals_per_team", 1.3)
        home_gf = home_form["home"]["goals_for_avg"] or avg
        home_ga = home_form["home"]["goals_against_avg"] or avg
        away_gf = away_form["away"]["goals_for_avg"] or avg
        away_ga = away_form["away"]["goals_against_avg"] or avg

        home_ad = attack_defense_strength(home_gf, home_ga, avg)
        away_ad = attack_defense_strength(away_gf, away_ga, avg)

        # --- 4. Predicción de goles (Dixon-Coles) ---
        # Combinar Pi-ratings con fuerza atacante/defensiva
        lambda_home = (pi_goals[0] + home_ad["attack_strength"] * away_ad["defense_weakness"] * avg) / 2
        lambda_away = (pi_goals[1] + away_ad["attack_strength"] * home_ad["defense_weakness"] * avg) / 2

        goals_pred = self.goals_model.predict(lambda_home, lambda_away)

        # --- 5. Probabilidades 1X2 combinadas ---
        # Promedio ponderado: Dixon-Coles (60%) + Elo (40%)
        dc_1x2 = goals_pred["result_1x2"]
        base_probs = {
            "home": round(dc_1x2["home"] * 0.6 + elo_pred["home"] * 0.4, 4),
            "draw": round(dc_1x2["draw"] * 0.6 + elo_pred["draw"] * 0.4, 4),
            "away": round(dc_1x2["away"] * 0.6 + elo_pred["away"] * 0.4, 4),
        }

        # --- 6. Contexto + Ajuste LLM ---
        llm_analysis = None
        rich_context = None
        final_probs = base_probs

        if use_llm:
            try:
                # Recopilar contexto: lesiones, noticias, rumores, táctica
                rich_context = gather_match_context(
                    home_team, away_team,
                    competition_stage=context.get("stage") if context else "Champions League",
                    additional_info=context.get("additional_info") if context else None,
                )

                # Construir datos para el analyzer
                analyzer_ctx = build_analyzer_context(rich_context)

                # Form data para el prompt
                form_for_llm = {
                    "home": {
                        "last_matches": [
                            f"{'W' if r['points']==3 else 'D' if r['points']==1 else 'L'} "
                            f"{r['goals_for']}-{r['goals_against']} vs {r['opponent']}"
                            for r in home_results[:5]
                        ],
                        "momentum": home_mom,
                    },
                    "away": {
                        "last_matches": [
                            f"{'W' if r['points']==3 else 'D' if r['points']==1 else 'L'} "
                            f"{r['goals_for']}-{r['goals_against']} vs {r['opponent']}"
                            for r in away_results[:5]
                        ],
                        "momentum": away_mom,
                    },
                }

                # Análisis con toda la info
                llm_analysis = analyze_match(
                    home_team, away_team, base_probs,
                    injuries=analyzer_ctx.get("injuries"),
                    standings_context=analyzer_ctx.get("standings"),
                    competition_stage=analyzer_ctx.get("stage"),
                    rich_context=rich_context,
                    form_data=form_for_llm,
                )
                if llm_analysis.get("adjustments"):
                    final_probs = apply_adjustments(base_probs, llm_analysis["adjustments"])
            except Exception as e:
                llm_analysis = {"error": str(e), "analysis": f"Error en análisis LLM: {e}"}

        # --- 7. Value bets ---
        value_bets_1x2 = []
        value_bets_ou = []
        if odds:
            value_bets_1x2 = find_value_bets(final_probs, odds)
            if "over_25" in odds and "under_25" in odds:
                ou_odds = {"2.5": {"over": odds["over_25"], "under": odds["under_25"]}}
                value_bets_ou = find_over_under_value(
                    goals_pred["over_under"], ou_odds,
                )

        # --- 8. Compilar resultado ---
        return {
            "match": f"{home_team} vs {away_team}",
            "probabilities": final_probs,
            "base_probabilities": base_probs,
            "goals": {
                "expected_home": round(lambda_home, 2),
                "expected_away": round(lambda_away, 2),
                "expected_total": round(lambda_home + lambda_away, 2),
                "over_under": goals_pred["over_under"],
                "most_likely_scores": goals_pred["most_likely_scores"],
            },
            "ratings": {
                "elo_home": round(self.elo.get_rating(home_team), 1),
                "elo_away": round(self.elo.get_rating(away_team), 1),
                "pi_home": self.pi.get_ratings(home_team),
                "pi_away": self.pi.get_ratings(away_team),
            },
            "form": {
                "home": {
                    "overall": home_form["overall"],
                    "at_home": home_form["home"],
                    "momentum": home_mom,
                    "last_matches": [
                        f"{'W' if r['points']==3 else 'D' if r['points']==1 else 'L'} "
                        f"{r['goals_for']}-{r['goals_against']} vs {r['opponent']}"
                        for r in home_results[:5]
                    ],
                },
                "away": {
                    "overall": away_form["overall"],
                    "at_away": away_form["away"],
                    "momentum": away_mom,
                    "last_matches": [
                        f"{'W' if r['points']==3 else 'D' if r['points']==1 else 'L'} "
                        f"{r['goals_for']}-{r['goals_against']} vs {r['opponent']}"
                        for r in away_results[:5]
                    ],
                },
            },
            "strength": {
                "home_attack": home_ad["attack_strength"],
                "home_defense": home_ad["defense_weakness"],
                "away_attack": away_ad["attack_strength"],
                "away_defense": away_ad["defense_weakness"],
            },
            "llm_analysis": llm_analysis,
            "value_bets": value_bets_1x2 + value_bets_ou,
        }

    def get_team_profile(self, team: str) -> dict:
        """Perfil completo de un equipo: rating, forma, stats."""
        results = get_team_results(self.df, team, n_last=10)
        form = home_away_form(results)
        mom = momentum(results)
        avg = self.league_avg.get("avg_goals_per_team", 1.3)

        gf = form["overall"]["goals_for_avg"] or avg
        ga = form["overall"]["goals_against_avg"] or avg
        ad = attack_defense_strength(gf, ga, avg)

        return {
            "team": team,
            "elo": round(self.elo.get_rating(team), 1),
            "pi_ratings": self.pi.get_ratings(team),
            "form": form,
            "momentum": mom,
            "attack_strength": ad["attack_strength"],
            "defense_weakness": ad["defense_weakness"],
            "last_5": [
                f"{'W' if r['points']==3 else 'D' if r['points']==1 else 'L'} "
                f"{r['goals_for']}-{r['goals_against']} "
                f"{'(H)' if r['is_home'] else '(A)'} vs {r['opponent']}"
                for r in results[:5]
            ],
            "total_matches": len(results),
        }

    def predict_multiple(
        self,
        fixtures: list[tuple[str, str]],
        use_llm: bool = False,
    ) -> list[dict]:
        """Predice múltiples partidos."""
        return [
            self.predict_match(home, away, use_llm=use_llm)
            for home, away in fixtures
        ]
