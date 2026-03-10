"""Cálculo de estadísticas de equipo y fuerza atacante/defensiva."""


def attack_defense_strength(
    team_goals_for: float,
    team_goals_against: float,
    league_avg_goals: float,
) -> dict[str, float]:
    """Calcula fuerza atacante y debilidad defensiva relativa a la media.

    Args:
        team_goals_for: Media de goles a favor del equipo por partido.
        team_goals_against: Media de goles en contra del equipo por partido.
        league_avg_goals: Media de goles por equipo por partido en la liga.

    Returns:
        Dict con attack_strength y defense_weakness.
    """
    if league_avg_goals == 0:
        return {"attack_strength": 1.0, "defense_weakness": 1.0}

    return {
        "attack_strength": round(team_goals_for / league_avg_goals, 4),
        "defense_weakness": round(team_goals_against / league_avg_goals, 4),
    }


def expected_goals_poisson(
    home_attack: float,
    home_defense: float,
    away_attack: float,
    away_defense: float,
    league_avg: float,
) -> tuple[float, float]:
    """Calcula goles esperados para modelo Poisson.

    lambda_home = home_attack * away_defense * league_avg
    lambda_away = away_attack * home_defense * league_avg
    """
    lambda_home = home_attack * away_defense * league_avg
    lambda_away = away_attack * home_defense * league_avg
    return round(lambda_home, 4), round(lambda_away, 4)


def head_to_head_stats(matches: list[dict], team_id: int) -> dict[str, float]:
    """Extrae estadísticas head-to-head para un equipo.

    Args:
        matches: Lista de partidos históricos del H2H.
        team_id: ID del equipo de interés.

    Returns:
        Dict con win_rate, draw_rate, loss_rate, avg_goals_for, avg_goals_against.
    """
    if not matches:
        return {
            "win_rate": 0.0,
            "draw_rate": 0.0,
            "loss_rate": 0.0,
            "avg_goals_for": 0.0,
            "avg_goals_against": 0.0,
        }

    wins = draws = losses = 0
    goals_for = goals_against = 0

    for match in matches:
        home = match.get("teams", {}).get("home", {})
        away = match.get("teams", {}).get("away", {})
        score = match.get("score", {}).get("fulltime", {})

        h_goals = score.get("home", 0) or 0
        a_goals = score.get("away", 0) or 0

        if home.get("id") == team_id:
            goals_for += h_goals
            goals_against += a_goals
            if h_goals > a_goals:
                wins += 1
            elif h_goals == a_goals:
                draws += 1
            else:
                losses += 1
        elif away.get("id") == team_id:
            goals_for += a_goals
            goals_against += h_goals
            if a_goals > h_goals:
                wins += 1
            elif a_goals == h_goals:
                draws += 1
            else:
                losses += 1

    total = len(matches)
    return {
        "win_rate": round(wins / total, 3),
        "draw_rate": round(draws / total, 3),
        "loss_rate": round(losses / total, 3),
        "avg_goals_for": round(goals_for / total, 3),
        "avg_goals_against": round(goals_against / total, 3),
    }
