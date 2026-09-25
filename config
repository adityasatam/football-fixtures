from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_FILE = DATA_DIR / "football_fixtures_2026_27.csv"

API_BASE_URL = "https://openfootapi.com/v1"
SEASON = "2026/27"
TIMEZONE = "Asia/Kolkata"

# OpenFoot API competition IDs verified against its 2026/27 coverage catalog.
COMPETITIONS = {
    "Premier League": "comp_premier_league_eng",
    "La Liga": "comp_laliga_es",
    "Serie A": "comp_serie_a_it",
    "Bundesliga": "comp_bundesliga_de",
    "Ligue 1": "comp_ligue_1_fr",
    "Champions League": "comp_uefa_champions_league",
    "Europa League": "comp_uefa_europa_league",
    "Conference League": "comp_uefa_conference_league",
    "UEFA Nations League": "comp_uefa_nations_league",
}

REQUEST_TIMEOUT_SECONDS = 30
MAX_RETRIES = 3

CSV_COLUMNS = [
    "fixture_id",
    "competition",
    "competition_id",
    "season",
    "date_ist",
    "time_ist",
    "datetime_ist",
    "datetime_utc",
    "home_team",
    "home_team_id",
    "away_team",
    "away_team_id",
    "status",
    "venue",
    "last_updated",
]
