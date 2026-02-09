# backend/scraper/config.py
"""Configuration and constants for scraping."""

# HTTP Configuration
REQUEST_TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # Exponential: 1s, 2s, 4s

# ATP Tour URLs
ATP_BASE_URL = "https://www.atptour.com"
RANKINGS_URLS = {
    "singles": f"{ATP_BASE_URL}/en/rankings/singles",
    "doubles": f"{ATP_BASE_URL}/en/rankings/doubles",
}
RESULTS_ARCHIVE_URL = f"{ATP_BASE_URL}/en/scores/results-archive"
PLAYER_OVERVIEW_URL = f"{ATP_BASE_URL}/en/players"

# Tournament Types
VALID_TOURNAMENT_TYPES = {'gs', 'atp', 'ch', 'fu'}

# Month Mapping
MONTH_MAP = {
    'January': '01', 'February': '02', 'March': '03', 'April': '04',
    'May': '05', 'June': '06', 'July': '07', 'August': '08',
    'September': '09', 'October': '10', 'November': '11', 'December': '12'
}

# Bio Data Columns
BIO_COLUMNS = [
    "birthdate", "weight_kg", "height_cm", "turned_pro",
    "country", "birthplace", "handedness", "backhand", "coach"
]