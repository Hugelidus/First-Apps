"""Descarga de datos históricos de Champions League.

Fuente principal: Football-Data.co.uk
Alternativa: Datos generados localmente para desarrollo sin conexión.
"""

from pathlib import Path

import requests

from src.config import DATA_DIR

HISTORICAL_DIR = DATA_DIR / "historical"
HISTORICAL_DIR.mkdir(parents=True, exist_ok=True)

# Football-Data.co.uk URLs para principales ligas europeas
# (UCL no está disponible directamente, usamos ligas top para entrenar ratings)
FOOTBALL_DATA_URLS = {
    # Premier League
    "england_2324": "https://www.football-data.co.uk/mmz4281/2324/E0.csv",
    "england_2223": "https://www.football-data.co.uk/mmz4281/2223/E0.csv",
    "england_2122": "https://www.football-data.co.uk/mmz4281/2122/E0.csv",
    # La Liga
    "spain_2324": "https://www.football-data.co.uk/mmz4281/2324/SP1.csv",
    "spain_2223": "https://www.football-data.co.uk/mmz4281/2223/SP1.csv",
    "spain_2122": "https://www.football-data.co.uk/mmz4281/2122/SP1.csv",
    # Serie A
    "italy_2324": "https://www.football-data.co.uk/mmz4281/2324/I1.csv",
    "italy_2223": "https://www.football-data.co.uk/mmz4281/2223/I1.csv",
    # Bundesliga
    "germany_2324": "https://www.football-data.co.uk/mmz4281/2324/D1.csv",
    "germany_2223": "https://www.football-data.co.uk/mmz4281/2223/D1.csv",
    # Ligue 1
    "france_2324": "https://www.football-data.co.uk/mmz4281/2324/F1.csv",
    "france_2223": "https://www.football-data.co.uk/mmz4281/2223/F1.csv",
}


def download_csv(url: str, filename: str) -> Path:
    """Descarga un CSV y lo guarda en data/historical/."""
    filepath = HISTORICAL_DIR / filename
    if filepath.exists():
        print(f"  Ya existe: {filename}")
        return filepath

    print(f"  Descargando: {filename}...")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    filepath.write_bytes(resp.content)
    print(f"  OK: {filename} ({len(resp.content)} bytes)")
    return filepath


def download_all():
    """Descarga todos los CSVs disponibles."""
    print("Descargando datos historicos de Football-Data.co.uk...\n")
    downloaded = []
    for name, url in FOOTBALL_DATA_URLS.items():
        try:
            path = download_csv(url, f"{name}.csv")
            downloaded.append(path)
        except Exception as e:
            print(f"  Error descargando {name}: {e}")
    print(f"\nDescargados: {len(downloaded)} archivos")
    return downloaded


def generate_champions_league_data() -> Path:
    """Genera dataset de Champions League con datos realistas.

    Incluye partidos de las últimas temporadas con equipos reales,
    resultados plausibles y estadísticas generadas.
    """
    import csv
    import random
    from datetime import datetime, timedelta

    filepath = HISTORICAL_DIR / "champions_league.csv"

    # Equipos que han participado regularmente en UCL
    teams = {
        "Real Madrid": {"attack": 1.4, "defense": 0.8},
        "Barcelona": {"attack": 1.3, "defense": 0.9},
        "Bayern Munich": {"attack": 1.5, "defense": 0.7},
        "Man City": {"attack": 1.5, "defense": 0.7},
        "Liverpool": {"attack": 1.3, "defense": 0.8},
        "PSG": {"attack": 1.3, "defense": 0.9},
        "Juventus": {"attack": 1.1, "defense": 0.8},
        "Chelsea": {"attack": 1.1, "defense": 0.8},
        "Atletico Madrid": {"attack": 0.9, "defense": 0.7},
        "Inter Milan": {"attack": 1.1, "defense": 0.8},
        "AC Milan": {"attack": 1.0, "defense": 0.9},
        "Borussia Dortmund": {"attack": 1.2, "defense": 0.9},
        "Napoli": {"attack": 1.2, "defense": 0.8},
        "Arsenal": {"attack": 1.2, "defense": 0.8},
        "Benfica": {"attack": 1.0, "defense": 0.9},
        "Porto": {"attack": 1.0, "defense": 0.9},
        "Ajax": {"attack": 1.1, "defense": 1.0},
        "RB Leipzig": {"attack": 1.1, "defense": 0.9},
        "Tottenham": {"attack": 1.0, "defense": 0.9},
        "Man United": {"attack": 1.0, "defense": 1.0},
        "Sevilla": {"attack": 0.9, "defense": 0.9},
        "Sporting CP": {"attack": 0.9, "defense": 0.9},
        "Shakhtar Donetsk": {"attack": 0.8, "defense": 1.0},
        "Club Brugge": {"attack": 0.8, "defense": 1.0},
        "Marseille": {"attack": 0.9, "defense": 1.0},
        "Salzburg": {"attack": 0.9, "defense": 1.0},
        "Celtic": {"attack": 0.8, "defense": 1.1},
        "Rangers": {"attack": 0.7, "defense": 1.1},
        "Copenhagen": {"attack": 0.7, "defense": 1.0},
        "Galatasaray": {"attack": 0.8, "defense": 1.0},
        "Lazio": {"attack": 1.0, "defense": 0.9},
        "Real Sociedad": {"attack": 0.9, "defense": 0.9},
    }

    random.seed(42)
    team_names = list(teams.keys())
    rows = []

    # Generar 3 temporadas de fase de grupos (6 jornadas, 8 grupos de 4)
    for season_offset in range(3):
        season_start = datetime(2021 + season_offset, 9, 14)

        # Dividir en 8 grupos de 4
        shuffled = team_names.copy()
        random.shuffle(shuffled)
        groups = [shuffled[i:i+4] for i in range(0, 32, 4)]

        matchday = 0
        for group in groups:
            # Round-robin: cada equipo juega contra los otros 3 (ida y vuelta)
            for i in range(len(group)):
                for j in range(len(group)):
                    if i == j:
                        continue
                    home = group[i]
                    away = group[j]
                    home_stats = teams[home]
                    away_stats = teams[away]

                    # Generar goles con Poisson
                    home_advantage = 0.3
                    lambda_h = home_stats["attack"] / away_stats["defense"] + home_advantage
                    lambda_a = away_stats["attack"] / home_stats["defense"]

                    hg = min(random.choices(range(7), weights=[
                        _poisson_pmf(k, lambda_h) for k in range(7)
                    ])[0], 6)
                    ag = min(random.choices(range(7), weights=[
                        _poisson_pmf(k, lambda_a) for k in range(7)
                    ])[0], 6)

                    result = "H" if hg > ag else ("D" if hg == ag else "A")
                    match_date = season_start + timedelta(days=matchday * 14 + random.randint(0, 2))

                    # Stats plausibles
                    home_shots = max(3, int(hg * 3.5 + random.gauss(5, 2)))
                    away_shots = max(2, int(ag * 3.5 + random.gauss(4, 2)))
                    home_sot = max(1, int(home_shots * random.uniform(0.3, 0.5)))
                    away_sot = max(1, int(away_shots * random.uniform(0.3, 0.5)))

                    # Cuotas plausibles basadas en fuerza relativa
                    prob_h = lambda_h / (lambda_h + lambda_a + 0.8)
                    prob_a = lambda_a / (lambda_h + lambda_a + 0.8)
                    prob_d = 1 - prob_h - prob_a
                    margin = 1.05  # 5% margen bookmaker

                    rows.append({
                        "Date": match_date.strftime("%d/%m/%Y"),
                        "HomeTeam": home,
                        "AwayTeam": away,
                        "FTHG": hg,
                        "FTAG": ag,
                        "FTR": result,
                        "HS": home_shots,
                        "AS": away_shots,
                        "HST": home_sot,
                        "AST": away_sot,
                        "HC": random.randint(2, 10),
                        "AC": random.randint(1, 9),
                        "HF": random.randint(8, 18),
                        "AF": random.randint(8, 18),
                        "HY": random.randint(0, 4),
                        "AY": random.randint(0, 4),
                        "HR": 1 if random.random() < 0.05 else 0,
                        "AR": 1 if random.random() < 0.05 else 0,
                        "B365H": round(margin / max(prob_h, 0.05), 2),
                        "B365D": round(margin / max(prob_d, 0.05), 2),
                        "B365A": round(margin / max(prob_a, 0.05), 2),
                        "Season": f"{2021+season_offset}/{2022+season_offset}",
                        "Round": f"Group Stage MD{(matchday % 6) + 1}",
                    })
                    matchday += 1

        # Añadir eliminatorias (octavos, cuartos, semis, final)
        knockout_teams = random.sample(team_names[:16], 16)
        rounds = [
            ("Round of 16", 8),
            ("Quarter-Final", 4),
            ("Semi-Final", 2),
            ("Final", 1),
        ]

        for round_name, n_matches in rounds:
            next_round = []
            for m in range(n_matches):
                home = knockout_teams[m * 2]
                away = knockout_teams[m * 2 + 1]
                home_stats = teams[home]
                away_stats = teams[away]

                lambda_h = home_stats["attack"] / away_stats["defense"] + 0.2
                lambda_a = away_stats["attack"] / home_stats["defense"]

                hg = random.choices(range(5), weights=[
                    _poisson_pmf(k, lambda_h) for k in range(5)
                ])[0]
                ag = random.choices(range(5), weights=[
                    _poisson_pmf(k, lambda_a) for k in range(5)
                ])[0]

                result = "H" if hg > ag else ("D" if hg == ag else "A")
                match_date = season_start + timedelta(days=150 + m * 7 + random.randint(0, 1))

                prob_h = lambda_h / (lambda_h + lambda_a + 0.8)
                prob_a = lambda_a / (lambda_h + lambda_a + 0.8)
                prob_d = 1 - prob_h - prob_a

                rows.append({
                    "Date": match_date.strftime("%d/%m/%Y"),
                    "HomeTeam": home,
                    "AwayTeam": away,
                    "FTHG": hg,
                    "FTAG": ag,
                    "FTR": result,
                    "HS": max(3, int(hg * 3 + random.gauss(6, 2))),
                    "AS": max(2, int(ag * 3 + random.gauss(5, 2))),
                    "HST": max(1, random.randint(2, 8)),
                    "AST": max(1, random.randint(2, 7)),
                    "HC": random.randint(3, 10),
                    "AC": random.randint(2, 9),
                    "HF": random.randint(10, 20),
                    "AF": random.randint(10, 20),
                    "HY": random.randint(1, 4),
                    "AY": random.randint(1, 4),
                    "HR": 1 if random.random() < 0.04 else 0,
                    "AR": 1 if random.random() < 0.04 else 0,
                    "B365H": round(1.05 / max(prob_h, 0.05), 2),
                    "B365D": round(1.05 / max(prob_d, 0.05), 2),
                    "B365A": round(1.05 / max(prob_a, 0.05), 2),
                    "Season": f"{2021+season_offset}/{2022+season_offset}",
                    "Round": round_name,
                })

                # Ganador avanza
                winner = home if hg >= ag else away
                next_round.append(winner)

            knockout_teams = next_round

    # Escribir CSV
    fieldnames = list(rows[0].keys())
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Generados {len(rows)} partidos de Champions League -> {filepath}")
    return filepath


def _poisson_pmf(k: int, lam: float) -> float:
    """PMF de Poisson simple (sin dependencia de scipy para el generador)."""
    import math
    return (lam ** k) * math.exp(-lam) / math.factorial(k)


if __name__ == "__main__":
    generate_champions_league_data()
    try:
        download_all()
    except Exception as e:
        print(f"No se pudieron descargar datos reales: {e}")
        print("Usa los datos generados de Champions League para desarrollo.")
