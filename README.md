# ATP Analytics

A full-stack web application for tracking and visualizing ATP tennis rankings over time.

## Features

- 📊 Interactive ranking charts for singles and doubles
- 🔍 Player search with autocomplete
- 📈 Multi-player comparison with persistent color coding
- 🎾 Historical ranking data from ATP Tour
- 🏆 Tournament wins displayed on rankings chart
- 👤 Player biographical data

## Tech Stack

### Backend

- **FastAPI** - REST API
- **Polars** - Fast data processing
- **Playwright** - Web scraping (player data)
- **httpx** - HTTP requests (rankings/tournaments)
- **BeautifulSoup4** - HTML parsing

### Frontend

- **React** + **TypeScript** + **Vite**
- **Chart.js** - Data visualization
- **TailwindCSS** - Styling
- **Axios** - API communication

## Project Structure

```text
atp-analytics/
├── backend/
│   ├── api/
│   │   └── main.py                  # FastAPI endpoints
│   ├── scraper/
│   │   ├── config.py                # Configuration and constants
│   │   ├── schemas.py               # Data schema definitions
│   │   ├── http_utils.py            # HTTP utilities with retry logic
│   │   ├── player_utils.py          # Player helper functions
│   │   ├── ranking_scraper.py       # Rankings scraper
│   │   ├── player_scraper.py        # Player bio scraper
│   │   ├── tournament_scraper.py    # Tournament scraper
│   │   └── updater.py               # Update orchestration logic
│   └── storage/
│       └── data_store.py            # Parquet I/O with schema-aware loading
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── RankingsChart.tsx    # Interactive chart with tournaments
│   │   │   └── PlayerSearch.tsx     # Player search component
│   │   └── App.tsx
│   └── package.json
├── scripts/
│   ├── update_rankings.py           # Scrape rankings
│   ├── update_players.py            # Scrape player bios
│   ├── update_tournaments.py        # Scrape tournaments
│   └── data_summary.py              # View data statistics
├── data/                            # Parquet files (gitignored)
└── README.md
```

## Setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Git

### Backend Setup

1. Clone the repository:

```bash
git clone <repo-url>
cd atp-analytics
```

2. Create virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install fastapi uvicorn polars httpx beautifulsoup4 playwright
playwright install chromium
```

4. Initial data load (scrape recent rankings):

```bash
python scripts/update_rankings.py singles 10
python scripts/update_rankings.py doubles 10
python scripts/update_players.py 20
python scripts/update_tournaments.py 2024 2025 atp,gs
```

5. Start the API server:

```bash
uvicorn backend.api.main:app --reload
```

API will be available at `http://localhost:8000`

### Frontend Setup

1. Navigate to frontend:

```bash
cd frontend
```

2. Install dependencies:

```bash
npm install
```

3. Start development server:

```bash
npm run dev
```

Frontend will be available at `http://localhost:3000`

## Data Scraping

### Scrape Rankings

```bash
# Scrape last 10 weeks of singles rankings
python scripts/update_rankings.py singles 10

# Scrape last 10 weeks of doubles rankings
python scripts/update_rankings.py doubles 10

# Scrape ALL historical rankings (slow!)
python scripts/update_rankings.py singles
python scripts/update_rankings.py doubles
```

**Features:**
- Automatic retry with exponential backoff
- Skips dates with missing data
- Proper logging with INFO/WARNING/ERROR levels
- Only scrapes missing weeks (incremental updates)

### Scrape Player Biographical Data

```bash
# Scrape top 50 players by ranking (slow, uses headless browser)
python scripts/update_players.py 50

# Scrape top 100 players
python scripts/update_players.py 100

# Default: scrape top 10 players
python scripts/update_players.py
```

**Player data includes:**
- Birthdate, birthplace, country
- Height (cm) and weight (kg)
- Year turned pro
- Handedness and backhand style
- Current coach

### Scrape Tournaments

```bash
# Scrape ATP tournaments for 2024-2025
python scripts/update_tournaments.py 2024 2025 atp

# Scrape Grand Slams
python scripts/update_tournaments.py 2024 2025 gs

# Scrape multiple tournament types
python scripts/update_tournaments.py 2024 2025 atp,gs,ch,fu
```

**Tournament types:**
- `atp` - ATP Tour (includes Next Gen Finals)
- `gs` - Grand Slams
- `ch` - ATP Challenger
- `fu` - ITF Futures

**Tournament data includes:**
- Tournament name, venue, country
- Start and end dates
- Singles and doubles winners
- Tournament type classification

### View Data Statistics

```bash
# See comprehensive summary of all scraped data
python scripts/data_summary.py
```

Shows:
- Date ranges and record counts
- Data completeness percentages
- Top players by points
- Top countries by player count
- File sizes and last modified dates

## API Endpoints

### `GET /health`
Health check

### `GET /players/search?q={query}`
Search players by name
- Returns up to 10 matching players
- Fuzzy search on player names

### `GET /rankings/stored?ranking_type={singles|doubles}&player_ids={ids}&ranking_date={date}`
Get ranking history
- `ranking_type`: "singles" or "doubles"
- `player_ids`: Comma-separated player IDs
- `ranking_date`: Optional, filter by specific date
- Returns ranking data for specified players

### `GET /tournaments`
Get all tournament data
- Returns complete tournament dataset

### `POST /admin/update-rankings?ranking_type={singles|doubles}&max_weeks={n}`
Trigger ranking update (admin endpoint)
- `ranking_type`: "singles" or "doubles"
- `max_weeks`: Optional, limit number of weeks to scrape

### `POST /tasks/update-weekly`
Scheduled task endpoint for automated weekly updates
- Updates last 5 weeks of singles and doubles rankings
- Updates current year tournaments

## Architecture

### Backend Design Principles

The backend follows clean architecture principles with clear separation of concerns:

**Configuration Layer** (`config.py`)
- Centralized constants (URLs, timeouts, retry settings)
- Tournament type definitions
- No magic numbers scattered across code

**Schema Layer** (`schemas.py`)
- Single source of truth for all data schemas
- Ensures consistency across scraping and storage

**Utilities Layer** (`http_utils.py`, `player_utils.py`)
- Reusable functions with no duplication
- HTTP retry logic with exponential backoff
- Player data extraction helpers

**Scraping Layer** (scrapers)
- Each scraper handles one data source
- Returns structured DataFrames
- Graceful error handling with proper logging

**Update Layer** (`updater.py`)
- Orchestrates scraping operations
- Handles incremental updates (only new data)
- Batch DataFrame operations for efficiency

**Storage Layer** (`data_store.py`)
- Schema-aware loading (returns empty DataFrames with schema)
- Consistent save/load interface
- Automatic deduplication on upsert

### Frontend Architecture

**Smart Tooltip Positioning**
- Automatically positions to avoid blocking data
- Stays within viewport bounds
- Responsive to screen size

**Tournament Visualization**
- Diamond markers sized by tournament importance (ITF < Challenger < ATP < Grand Slam)
- Tooltip shows tournament name, type, and venue
- Color-coded by player

## Development

### Run Backend Tests

```bash
pytest
```

### Build Frontend for Production

```bash
cd frontend
npm run build
```

### Lint Frontend

```bash
npm run lint
```

### Code Style

Backend follows PEP 8 with:
- Type hints throughout
- Proper logging (no print statements)
- Private functions prefixed with `_`
- Docstrings for public functions

## Data Storage

All data is stored as Parquet files in the `data/` directory:

- `singles_rankings.parquet` - Singles ranking history
- `doubles_rankings.parquet` - Doubles ranking history
- `players.parquet` - Player information and biographical data
- `tournaments.parquet` - Tournament results with winners

**Why Parquet?**
- Efficient columnar storage
- Fast filtering and queries
- Built-in compression
- Native support in Polars

## Performance

- **Ranking scraping**: ~1-2 seconds per week
- **Player scraping**: ~2-3 seconds per player (headless browser)
- **Tournament scraping**: ~3-5 seconds per year per type
- **Batch updates**: 10-100x faster than row-by-row operations

## Notes

- **VPN Warning**: Disable VPN when scraping - ATP Tour uses Cloudflare which may block VPN traffic
- **Rate Limiting**: Player bio scraping is slow due to headless browser requirement
- **Data Updates**: Run ranking updates weekly to keep data current
- **Browser Requirement**: Playwright requires Chromium (`playwright install chromium`)
- **Retry Logic**: All scrapers have automatic retry with exponential backoff (3 attempts)
- **Incremental Updates**: Scrapers only fetch missing data, not full re-scrapes

## Troubleshooting

**"Table not found" errors when scraping rankings**
- Some dates may not have data available on ATP Tour
- Scraper automatically skips these and continues

**Timeout errors**
- Retry logic will automatically retry up to 3 times
- If persistent, check your internet connection
- Disable VPN if enabled

**Missing player data**
- Player pages may be incomplete or unavailable
- Scraper returns empty dict and continues with next player

**"No ranking table found"**
- ATP Tour site structure may have changed
- Check if site is accessible in browser
- May need scraper updates

## License

MIT

## Contributing

Pull requests welcome! Please ensure:
- Code follows existing style (PEP 8 for Python)
- Type hints included
- Proper logging (no print statements)
- Tests included for new features
- Update documentation as needed
