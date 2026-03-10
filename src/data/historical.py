"""Carga y procesamiento de datos históricos de Champions League.

Fuentes soportadas:
- Football-Data.co.uk (CSVs por temporada)
- CSVs locales con formato estándar
"""

import csv
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.config import DATA_DIR

HISTORICAL_DIR = DATA_DIR / "historical"
HISTORICAL_DIR.mkdir(parents=True, exist_ok=True)

# Columnas estándar que usamos internamente
STANDARD_COLS = [
    "date", "home_team", "away_team",
    "home_goals", "away_goals", "result",
    "home_shots", "away_shots",
    "home_shots_target", "away_shots_target",
    "home_corners", "away_corners",
    "home_fouls", "away_fouls",
    "home_yellow", "away_yellow",
    "home_red", "away_red",
    # Cuotas históricas
    "odd_home", "odd_draw", "odd_away",
    "odd_over_25", "odd_under_25",
    # Metadatos
    "season", "round", "league",
]


def load_football_data_csv(filepath: str | Path) -> pd.DataFrame:
    """Carga CSV de Football-Data.co.uk y normaliza columnas.

    Football-Data.co.uk usa estas columnas:
    Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR,
    HS, AS, HST, AST, HC, AC, HF, AF, HY, AY, HR, AR,
    B365H, B365D, B365A (cuotas Bet365)
    BbOU, BbMx>2.5, BbMx<2.5 (Over/Under)
    """
    df = pd.read_csv(filepath, encoding="utf-8", on_bad_lines="skip")

    # Mapeo de columnas Football-Data -> nuestro estándar
    col_map = {
        "Date": "date",
        "HomeTeam": "home_team", "Home": "home_team", "HT": "home_team",
        "AwayTeam": "away_team", "Away": "away_team", "AT": "away_team",
        "FTHG": "home_goals", "HG": "home_goals",
        "FTAG": "away_goals", "AG": "away_goals",
        "FTR": "result",
        "HS": "home_shots", "AS": "away_shots",
        "HST": "home_shots_target", "AST": "away_shots_target",
        "HC": "home_corners", "AC": "away_corners",
        "HF": "home_fouls", "AF": "away_fouls",
        "HY": "home_yellow", "AY": "away_yellow",
        "HR": "home_red", "AR": "away_red",
        # Cuotas (usamos Bet365 como referencia principal)
        "B365H": "odd_home", "BbAvH": "odd_home",
        "B365D": "odd_draw", "BbAvD": "odd_draw",
        "B365A": "odd_away", "BbAvA": "odd_away",
        "BbMx>2.5": "odd_over_25", "Max>2.5": "odd_over_25",
        "BbMx<2.5": "odd_under_25", "Max<2.5": "odd_under_25",
    }

    renamed = {}
    for old_col, new_col in col_map.items():
        if old_col in df.columns and new_col not in renamed.values():
            renamed[old_col] = new_col

    df = df.rename(columns=renamed)

    # Convertir resultado a numérico: 2=home, 1=draw, 0=away
    if "result" in df.columns:
        result_map = {"H": 2, "D": 1, "A": 0}
        df["result_numeric"] = df["result"].map(result_map)

    # Parsear fechas
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)

    # Convertir goles a int
    for col in ["home_goals", "away_goals"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # Total de goles
    if "home_goals" in df.columns and "away_goals" in df.columns:
        df["total_goals"] = df["home_goals"] + df["away_goals"]
        df["over_25"] = (df["total_goals"] > 2.5).astype(int)

    return df


def load_generic_csv(filepath: str | Path) -> pd.DataFrame:
    """Carga cualquier CSV e intenta mapear columnas automáticamente."""
    df = pd.read_csv(filepath, encoding="utf-8", on_bad_lines="skip")

    # Intentar detectar columnas por nombre similar
    col_lower = {c.lower().strip(): c for c in df.columns}

    auto_map = {}
    patterns = {
        "home_team": ["hometeam", "home_team", "home", "ht", "team1", "equipolocal"],
        "away_team": ["awayteam", "away_team", "away", "at", "team2", "equipovisitante"],
        "home_goals": ["fthg", "home_goals", "hg", "homegoals", "goleslocal"],
        "away_goals": ["ftag", "away_goals", "ag", "awaygoals", "golesvisitante"],
        "date": ["date", "fecha", "matchdate", "datetime"],
    }

    for target, candidates in patterns.items():
        for cand in candidates:
            if cand in col_lower and target not in auto_map.values():
                auto_map[col_lower[cand]] = target
                break

    if auto_map:
        df = df.rename(columns=auto_map)

    # Mismo post-procesamiento
    if "home_goals" in df.columns and "away_goals" in df.columns:
        df["home_goals"] = pd.to_numeric(df["home_goals"], errors="coerce").fillna(0).astype(int)
        df["away_goals"] = pd.to_numeric(df["away_goals"], errors="coerce").fillna(0).astype(int)
        df["total_goals"] = df["home_goals"] + df["away_goals"]

        # Generar resultado
        conditions = [
            df["home_goals"] > df["away_goals"],
            df["home_goals"] == df["away_goals"],
            df["home_goals"] < df["away_goals"],
        ]
        df["result"] = pd.Series(["H", "D", "A"])[
            pd.Categorical(
                sum(i * c for i, c in enumerate(conditions)),
                categories=[0, 1, 2]
            ).codes
        ].values
        df["result_numeric"] = df["result"].map({"H": 2, "D": 1, "A": 0})

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
        df = df.sort_values("date").reset_index(drop=True)

    return df


def load_all_historical(directory: str | Path | None = None) -> pd.DataFrame:
    """Carga todos los CSVs históricos de un directorio y los combina."""
    directory = Path(directory) if directory else HISTORICAL_DIR
    all_dfs = []

    for csv_file in sorted(directory.glob("*.csv")):
        try:
            df = load_football_data_csv(csv_file)
            df["source_file"] = csv_file.name
            all_dfs.append(df)
        except Exception as e:
            print(f"Error cargando {csv_file.name}: {e}")

    if not all_dfs:
        return pd.DataFrame()

    combined = pd.concat(all_dfs, ignore_index=True)
    combined = combined.sort_values("date").reset_index(drop=True)
    return combined


def get_team_results(df: pd.DataFrame, team: str, n_last: int | None = None) -> list[dict]:
    """Extrae resultados de un equipo en formato para el módulo de forma.

    Returns:
        Lista de dicts ordenada del más reciente al más antiguo:
        {points, goals_for, goals_against, is_home}
    """
    home_mask = df["home_team"].str.lower() == team.lower()
    away_mask = df["away_team"].str.lower() == team.lower()

    results = []

    for _, row in df[home_mask].iterrows():
        hg, ag = row["home_goals"], row["away_goals"]
        points = 3 if hg > ag else (1 if hg == ag else 0)
        results.append({
            "date": row.get("date"),
            "points": points,
            "goals_for": hg,
            "goals_against": ag,
            "is_home": True,
            "opponent": row["away_team"],
        })

    for _, row in df[away_mask].iterrows():
        hg, ag = row["home_goals"], row["away_goals"]
        points = 3 if ag > hg else (1 if ag == hg else 0)
        results.append({
            "date": row.get("date"),
            "points": points,
            "goals_for": ag,
            "goals_against": hg,
            "is_home": False,
            "opponent": row["home_team"],
        })

    results.sort(key=lambda x: x.get("date", ""), reverse=True)

    if n_last:
        results = results[:n_last]

    return results


def get_league_averages(df: pd.DataFrame) -> dict[str, float]:
    """Calcula medias de la liga para normalización."""
    if df.empty:
        return {"avg_goals_per_team": 1.3, "avg_total_goals": 2.6}

    avg_home = df["home_goals"].mean()
    avg_away = df["away_goals"].mean()

    return {
        "avg_home_goals": round(avg_home, 4),
        "avg_away_goals": round(avg_away, 4),
        "avg_goals_per_team": round((avg_home + avg_away) / 2, 4),
        "avg_total_goals": round(avg_home + avg_away, 4),
    }
