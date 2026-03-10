"""Sistemas de rating dinámico: Elo y Pi-ratings."""

import math
from collections import defaultdict


class EloRating:
    """Sistema Elo adaptado para fútbol."""

    def __init__(self, k: float = 32, home_advantage: float = 100):
        self.ratings: dict[str, float] = defaultdict(lambda: 1500.0)
        self.k = k
        self.home_advantage = home_advantage

    def expected(self, rating_a: float, rating_b: float) -> float:
        """Probabilidad esperada de victoria de A sobre B."""
        return 1 / (1 + math.pow(10, (rating_b - rating_a) / 400))

    def update(self, home_team: str, away_team: str, home_goals: int, away_goals: int):
        """Actualiza ratings tras un partido."""
        r_home = self.ratings[home_team] + self.home_advantage
        r_away = self.ratings[away_team]

        exp_home = self.expected(r_home, r_away)
        exp_away = 1 - exp_home

        if home_goals > away_goals:
            s_home, s_away = 1.0, 0.0
        elif home_goals < away_goals:
            s_home, s_away = 0.0, 1.0
        else:
            s_home, s_away = 0.5, 0.5

        # Factor de margen de goles
        goal_diff = abs(home_goals - away_goals)
        margin_factor = math.log(1 + goal_diff)

        self.ratings[home_team] += self.k * margin_factor * (s_home - exp_home)
        self.ratings[away_team] += self.k * margin_factor * (s_away - exp_away)

    def predict(self, home_team: str, away_team: str) -> dict[str, float]:
        """Predice probabilidades 1X2."""
        r_home = self.ratings[home_team] + self.home_advantage
        r_away = self.ratings[away_team]
        p_home = self.expected(r_home, r_away)
        p_away = 1 - p_home
        # Aproximación simple para el empate
        draw_factor = 0.26 * (1 - abs(p_home - p_away))
        p_home_adj = p_home * (1 - draw_factor)
        p_away_adj = p_away * (1 - draw_factor)
        p_draw = 1 - p_home_adj - p_away_adj
        return {"home": p_home_adj, "draw": p_draw, "away": p_away_adj}

    def get_rating(self, team: str) -> float:
        return self.ratings[team]


class PiRating:
    """Pi-ratings: ratings separados para local y visitante.

    Superiores a Elo porque mantienen ratings home/away independientes
    y consideran el margen de goles.
    """

    def __init__(self, learning_rate: float = 0.1, home_advantage: float = 0.3):
        # Cada equipo tiene rating_home y rating_away
        self.home_ratings: dict[str, float] = defaultdict(lambda: 0.0)
        self.away_ratings: dict[str, float] = defaultdict(lambda: 0.0)
        self.lr = learning_rate
        self.home_advantage = home_advantage

    def _expected_goals(self, attack: float, defense: float) -> float:
        """Goles esperados basados en diferencia de ratings."""
        return max(0.1, 1.5 + attack - defense)

    def update(self, home_team: str, away_team: str, home_goals: int, away_goals: int):
        """Actualiza ratings tras un partido."""
        # Rating efectivo del equipo local vs visitante
        home_strength = self.home_ratings[home_team] + self.home_advantage
        away_strength = self.away_ratings[away_team]

        expected_home = self._expected_goals(home_strength, away_strength)
        expected_away = self._expected_goals(away_strength, home_strength)

        # Error de predicción
        error_home = home_goals - expected_home
        error_away = away_goals - expected_away

        # Actualizar ratings
        self.home_ratings[home_team] += self.lr * error_home
        self.away_ratings[away_team] += self.lr * error_away

        # Cross-update: el rendimiento defensivo también afecta
        self.home_ratings[home_team] -= self.lr * error_away * 0.5
        self.away_ratings[away_team] -= self.lr * error_home * 0.5

    def predict_goals(self, home_team: str, away_team: str) -> tuple[float, float]:
        """Predice goles esperados para cada equipo."""
        home_strength = self.home_ratings[home_team] + self.home_advantage
        away_strength = self.away_ratings[away_team]
        lambda_home = self._expected_goals(home_strength, away_strength)
        lambda_away = self._expected_goals(away_strength, home_strength)
        return lambda_home, lambda_away

    def get_ratings(self, team: str) -> dict[str, float]:
        return {
            "home": self.home_ratings[team],
            "away": self.away_ratings[team],
        }
