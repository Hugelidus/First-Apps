"""Modelo de goles: Dixon-Coles (Poisson corregido) para Over/Under y Handicap."""

import numpy as np
from scipy.stats import poisson


def poisson_score_matrix(lambda_home: float, lambda_away: float, max_goals: int = 7) -> np.ndarray:
    """Genera matriz de probabilidades de marcadores usando Poisson.

    Args:
        lambda_home: Goles esperados del equipo local.
        lambda_away: Goles esperados del equipo visitante.
        max_goals: Máximo de goles por equipo a considerar.

    Returns:
        Matriz (max_goals x max_goals) con probabilidad de cada marcador.
    """
    matrix = np.zeros((max_goals, max_goals))
    for i in range(max_goals):
        for j in range(max_goals):
            matrix[i][j] = poisson.pmf(i, lambda_home) * poisson.pmf(j, lambda_away)
    return matrix


def dixon_coles_correction(matrix: np.ndarray, lambda_home: float, lambda_away: float,
                           rho: float = -0.13) -> np.ndarray:
    """Aplica corrección Dixon-Coles para marcadores bajos.

    Corrige la subestimación de empates y resultados 0-0, 1-0, 0-1, 1-1
    que tiene el modelo Poisson básico.
    """
    corrected = matrix.copy()

    # Corrección para marcadores bajos (0-0, 1-0, 0-1, 1-1)
    corrected[0][0] *= 1 - lambda_home * lambda_away * rho
    corrected[1][0] *= 1 + lambda_away * rho
    corrected[0][1] *= 1 + lambda_home * rho
    corrected[1][1] *= 1 - rho

    # Renormalizar para que sume 1
    corrected /= corrected.sum()
    return corrected


class GoalsModel:
    """Modelo de predicción de goles basado en Dixon-Coles."""

    def __init__(self, rho: float = -0.13):
        self.rho = rho

    def predict(self, lambda_home: float, lambda_away: float) -> dict:
        """Genera predicciones completas de goles.

        Returns:
            Dict con probabilidades de Over/Under, handicaps y marcador más probable.
        """
        # Generar matriz de marcadores
        raw_matrix = poisson_score_matrix(lambda_home, lambda_away)
        matrix = dixon_coles_correction(raw_matrix, lambda_home, lambda_away, self.rho)

        # Over/Under
        over_under = self._calc_over_under(matrix)

        # Resultado 1X2 desde la matriz
        result_1x2 = self._calc_1x2(matrix)

        # Handicaps asiáticos
        handicaps = self._calc_handicaps(matrix)

        # Marcador más probable
        most_likely = self._most_likely_scores(matrix, top_n=5)

        return {
            "lambda_home": round(lambda_home, 3),
            "lambda_away": round(lambda_away, 3),
            "over_under": over_under,
            "result_1x2": result_1x2,
            "handicaps": handicaps,
            "most_likely_scores": most_likely,
        }

    def _calc_over_under(self, matrix: np.ndarray) -> dict[str, dict[str, float]]:
        """Calcula probabilidades Over/Under para varias líneas."""
        lines = [1.5, 2.5, 3.5, 4.5]
        result = {}
        for line in lines:
            over = 0.0
            for i in range(matrix.shape[0]):
                for j in range(matrix.shape[1]):
                    if i + j > line:
                        over += matrix[i][j]
            result[f"{line}"] = {
                "over": round(over, 4),
                "under": round(1 - over, 4),
            }
        return result

    def _calc_1x2(self, matrix: np.ndarray) -> dict[str, float]:
        """Calcula 1X2 desde la matriz de marcadores."""
        home_win = draw = away_win = 0.0
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                if i > j:
                    home_win += matrix[i][j]
                elif i == j:
                    draw += matrix[i][j]
                else:
                    away_win += matrix[i][j]
        return {
            "home": round(home_win, 4),
            "draw": round(draw, 4),
            "away": round(away_win, 4),
        }

    def _calc_handicaps(self, matrix: np.ndarray) -> dict[str, dict[str, float]]:
        """Calcula probabilidades de handicap asiático."""
        handicap_lines = [-2.5, -1.5, -0.5, 0.5, 1.5, 2.5]
        result = {}
        for hc in handicap_lines:
            covers = 0.0
            for i in range(matrix.shape[0]):
                for j in range(matrix.shape[1]):
                    # Home team handicap: home_goals + handicap > away_goals
                    if (i + hc) > j:
                        covers += matrix[i][j]
            result[f"home {hc:+.1f}"] = {
                "covers": round(covers, 4),
                "not_covers": round(1 - covers, 4),
            }
        return result

    def _most_likely_scores(self, matrix: np.ndarray, top_n: int = 5) -> list[dict]:
        """Devuelve los marcadores más probables."""
        scores = []
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                scores.append({"home": i, "away": j, "prob": round(float(matrix[i][j]), 4)})
        scores.sort(key=lambda x: x["prob"], reverse=True)
        return scores[:top_n]
