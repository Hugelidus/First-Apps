"""Detección de value bets y comparación de cuotas."""

from src.betting.kelly import recommended_stake
from src.config import BANKROLL


def find_value_bets(
    predictions: dict[str, float],
    odds: dict[str, float],
    bankroll: float = BANKROLL,
    min_value: float = 0.05,
) -> list[dict]:
    """Encuentra value bets comparando predicciones con cuotas.

    Args:
        predictions: Dict con probabilidades {home, draw, away}.
        odds: Dict con cuotas decimales {home, draw, away}.
        bankroll: Capital disponible.
        min_value: Valor mínimo para considerar una apuesta (filtrar ruido).

    Returns:
        Lista de value bets ordenadas por valor, de mayor a menor.
    """
    value_bets = []

    for outcome in ["home", "draw", "away"]:
        prob = predictions.get(outcome, 0)
        odd = odds.get(outcome, 0)
        if odd <= 1:
            continue

        value = (prob * odd) - 1
        if value >= min_value:
            stake_info = recommended_stake(bankroll, prob, odd)
            value_bets.append({
                "outcome": outcome,
                **stake_info,
            })

    value_bets.sort(key=lambda x: x["value"], reverse=True)
    return value_bets


def find_over_under_value(
    ou_predictions: dict[str, dict[str, float]],
    ou_odds: dict[str, dict[str, float]],
    bankroll: float = BANKROLL,
    min_value: float = 0.05,
) -> list[dict]:
    """Encuentra value bets en mercados Over/Under.

    Args:
        ou_predictions: Dict con líneas y probabilidades. Ej: {"2.5": {"over": 0.55, "under": 0.45}}
        ou_odds: Dict con líneas y cuotas. Ej: {"2.5": {"over": 1.90, "under": 1.95}}
    """
    value_bets = []

    for line in ou_predictions:
        if line not in ou_odds:
            continue

        for side in ["over", "under"]:
            prob = ou_predictions[line].get(side, 0)
            odd = ou_odds[line].get(side, 0)
            if odd <= 1:
                continue

            value = (prob * odd) - 1
            if value >= min_value:
                stake_info = recommended_stake(bankroll, prob, odd)
                value_bets.append({
                    "market": f"{'Más' if side == 'over' else 'Menos'} de {line} goles",
                    "line": float(line),
                    "side": side,
                    **stake_info,
                })

    value_bets.sort(key=lambda x: x["value"], reverse=True)
    return value_bets


def best_odds(bookmaker_odds: list[dict]) -> dict[str, dict]:
    """Encuentra la mejor cuota para cada mercado entre múltiples casas.

    Args:
        bookmaker_odds: Lista de dicts con {bookmaker, home, draw, away}.

    Returns:
        Dict con la mejor cuota y casa para cada outcome.
    """
    best = {}
    for outcome in ["home", "draw", "away"]:
        top = max(bookmaker_odds, key=lambda x: x.get(outcome, 0))
        best[outcome] = {
            "odds": top.get(outcome, 0),
            "bookmaker": top.get("bookmaker", "?"),
        }
    return best
