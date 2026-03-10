"""Configuración central del proyecto."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Rutas
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# API Keys
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY", "")
ODDS_API_KEY = os.getenv("ODDS_API_KEY", "")
FOOTBALL_DATA_KEY = os.getenv("FOOTBALL_DATA_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# Bankroll
BANKROLL = float(os.getenv("BANKROLL", "1000"))
KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.25"))

# API-Football
API_FOOTBALL_BASE = "https://v3.football.api-sports.io"
API_FOOTBALL_HEADERS = {"x-apisports-key": API_FOOTBALL_KEY}

# The Odds API
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

# Football-Data.org
FOOTBALL_DATA_BASE = "https://api.football-data.org/v4"
FOOTBALL_DATA_HEADERS = {"X-Auth-Token": FOOTBALL_DATA_KEY}

# Champions League ID en API-Football
CHAMPIONS_LEAGUE_ID = 2

# Cache TTL en segundos
CACHE_TTL_FIXTURES = 3600       # 1 hora
CACHE_TTL_STATS = 86400         # 24 horas
CACHE_TTL_ODDS = 1800           # 30 minutos
