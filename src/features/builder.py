"""Constructor de features: combina ratings, forma y stats en un DataFrame."""

import pandas as pd

from src.features.ratings import EloRating, PiRating
from src.features.form import home_away_form, momentum
from src.features.stats import attack_defense_strength


def build_match_features(
    home_team: str,
    away_team: str,
    elo: EloRating,
    pi: PiRating,
    home_results: list[dict],
    away_results: list[dict],
    home_stats: dict,
    away_stats: dict,
    h2h_stats: dict,
    league_avg_goals: float,
) -> dict:
    """Construye el vector de features para un partido.

    Returns:
        Dict con todas las features listas para el modelo ML.
    """
    # Ratings
    elo_pred = elo.predict(home_team, away_team)
    pi_home_goals, pi_away_goals = pi.predict_goals(home_team, away_team)
    home_pi = pi.get_ratings(home_team)
    away_pi = pi.get_ratings(away_team)

    # Forma
    home_form = home_away_form(home_results)
    away_form = home_away_form(away_results)
    home_momentum = momentum(home_results)
    away_momentum = momentum(away_results)

    # Fuerza atacante/defensiva
    home_ad = attack_defense_strength(
        home_stats.get("goals_for_avg", 1.0),
        home_stats.get("goals_against_avg", 1.0),
        league_avg_goals,
    )
    away_ad = attack_defense_strength(
        away_stats.get("goals_for_avg", 1.0),
        away_stats.get("goals_against_avg", 1.0),
        league_avg_goals,
    )

    return {
        # Elo
        "elo_home": elo.get_rating(home_team),
        "elo_away": elo.get_rating(away_team),
        "elo_diff": elo.get_rating(home_team) - elo.get_rating(away_team),
        "elo_prob_home": elo_pred["home"],
        "elo_prob_draw": elo_pred["draw"],
        "elo_prob_away": elo_pred["away"],
        # Pi-ratings
        "pi_home_rating": home_pi["home"],
        "pi_away_rating": away_pi["away"],
        "pi_expected_home_goals": pi_home_goals,
        "pi_expected_away_goals": pi_away_goals,
        # Forma local (como local)
        "home_form_points": home_form["home"]["points_avg"],
        "home_form_gf": home_form["home"]["goals_for_avg"],
        "home_form_ga": home_form["home"]["goals_against_avg"],
        "home_form_gd": home_form["home"]["goal_diff_avg"],
        "home_form_wr": home_form["home"]["win_rate"],
        # Forma visitante (como visitante)
        "away_form_points": away_form["away"]["points_avg"],
        "away_form_gf": away_form["away"]["goals_for_avg"],
        "away_form_ga": away_form["away"]["goals_against_avg"],
        "away_form_gd": away_form["away"]["goal_diff_avg"],
        "away_form_wr": away_form["away"]["win_rate"],
        # Momentum
        "home_momentum": home_momentum,
        "away_momentum": away_momentum,
        # Fuerza atacante/defensiva
        "home_attack": home_ad["attack_strength"],
        "home_defense": home_ad["defense_weakness"],
        "away_attack": away_ad["attack_strength"],
        "away_defense": away_ad["defense_weakness"],
        # Head-to-head
        "h2h_home_wr": h2h_stats.get("win_rate", 0.0),
        "h2h_draw_rate": h2h_stats.get("draw_rate", 0.0),
        "h2h_home_gf": h2h_stats.get("avg_goals_for", 0.0),
        "h2h_home_ga": h2h_stats.get("avg_goals_against", 0.0),
    }


def build_features_dataframe(matches_features: list[dict]) -> pd.DataFrame:
    """Convierte lista de features en DataFrame."""
    return pd.DataFrame(matches_features)
