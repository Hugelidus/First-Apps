"""Kelly Criterion fraccional para dimensionamiento de apuestas."""

from src.config import KELLY_FRACTION


def kelly_fraction(prob: float, odds: float, fraction: float = KELLY_FRACTION) -> float:
    """Calcula la fracción Kelly para una apuesta.

    Args:
        prob: Probabilidad estimada de ganar (0-1).
        odds: Cuota decimal (ej: 2.10).
        fraction: Fracción de Kelly a usar (0.25 = quarter Kelly).

    Returns:
        Fracción del bankroll a apostar (0 si no hay valor).
    """
    b = odds - 1  # Ganancia neta por unidad apostada
    q = 1 - prob   # Probabilidad de perder

    if b <= 0 or prob <= 0 or prob >= 1:
        return 0.0

    f = (b * prob - q) / b

    if f <= 0:
        return 0.0

    # Aplicar fracción Kelly y limitar a 5% máximo
    return min(round(f * fraction, 4), 0.05)


def recommended_stake(bankroll: float, prob: float, odds: float,
                      fraction: float = KELLY_FRACTION) -> dict:
    """Calcula stake recomendado en unidades monetarias.

    Returns:
        Dict con fracción Kelly, stake en dinero y análisis.
    """
    frac = kelly_fraction(prob, odds, fraction)
    stake = round(bankroll * frac, 2)
    value = (prob * odds) - 1
    implied_prob = 1 / odds if odds > 0 else 0

    return {
        "kelly_fraction": frac,
        "stake": stake,
        "value": round(value, 4),
        "edge": round(prob - implied_prob, 4),
        "implied_prob": round(implied_prob, 4),
        "our_prob": round(prob, 4),
        "odds": odds,
        "is_value_bet": value > 0,
    }
