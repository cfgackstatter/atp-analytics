# ATP Analytics

A full-stack web application for tracking and visualizing ATP tennis rankings over time.

## Features

- 📊 Interactive ranking charts for singles and doubles
- 🔍 Player search with autocomplete
- 📈 Multi-player comparison with persistent color coding
- 🎾 Historical ranking data from ATP Tour
- 🏆 Tournament wins displayed on rankings chart

## Tech Stack

**Backend:** FastAPI, Polars, Playwright  
**Frontend:** React, TypeScript, Chart.js, TailwindCSS  
**Deployment:** AWS Elastic Beanstalk, Docker, S3

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Test locally with Docker
make test

# Access at http://localhost:8000
# Admin password from .admin-password.txt
```

### Deployment

```bash
# Deploy to production
make deploy

# View production logs
make logs

# SSH into production
make ssh
```

### Available Commands

```bash
make help      # Show all commands
make build     # Build Docker image
make test      # Run locally
make deploy    # Deploy to AWS EB
make logs      # Stream production logs
make ssh       # SSH into EB instance
make clean     # Clean Docker images
```

## Project Structure

```text
atp-analytics/
├── backend/
│   ├── api/
│   │   ├── main.py          # FastAPI endpoints
│   │   └── admin.py         # Admin endpoints
│   ├── scraper/             # Data scrapers
│   └── storage/             # S3/local storage
├── frontend/                # React app
├── Dockerfile               # Production container
├── Dockerrun.aws.json       # EB Docker config
├── Makefile                 # Development commands
├── .admin-password.txt      # Admin password (not in git)
└── data/                    # Local data (not in git)
```

## Data Scraping

Player scraping uses Playwright (headless browser) and is managed **manually** through the admin interface at `/admin/dashboard`. There is no scheduled/weekly update endpoint. Scrapes run in a dedicated subprocess so the site stays up; concurrent scrapes are rejected (409) and data merges are locked/deduped.

### Admin Features:

- Scrape ATP rankings (singles/doubles)
- Scrape tournament results
- Scrape player records used for search (names / ids; bios are not shown in the UI)
- View scraping job history

## Configuration

### Local Environment

- **Required** password in `.admin-password.txt` (gitignored) — no default
- Makefile refuses to start `dev`/`test` if the file is missing
- Admin APIs use `Authorization: Bearer <password>` (never query-string)
- Data stored in `./data/` directory

### Production Environment

- `make deploy` syncs env vars then deploys code (see `make sync-env`)
- Env sync sets `ADMIN_PASSWORD` from `.admin-password.txt`, `FORCE_HTTPS=true`, `ENABLE_DOCS=false`, and S3 settings
- OpenAPI `/docs` is off in production; CORS is same-origin only unless `CORS_ORIGINS` is set
- Data stored in S3

## Deployment Architecture

- Docker: Single container with Playwright pre-installed
- Elastic Beanstalk: Handles container orchestration
- S3: Data storage (Parquet files)
- GitHub: Source control and deployment trigger

## Development Workflow

1. Make changes locally
2. Test with `make test`
3. Deploy with `make deploy` (auto-commits, pushes, deploys)
4. Monitor with `make logs`

## Troubleshooting

### Player scraping returns 0 players:

- Check logs: `make logs`
- Verify Playwright browsers installed in container
- Check production environment has sufficient memory

### Password not working:

- Local: Check `.admin-password.txt` exists and is non-empty (`make check-password`)
- Production: Verify `ADMIN_PASSWORD` is set with `eb printenv` / `make status`
- If unset, admin APIs return 503 (fail closed — no fallback password)

### Docker build fails:

- Clear cache: `make clean && make build`
- Check Dockerfile syntax
- Verify base image is accessible

## Files Not in Git

- `.admin-password.txt` - Production password
- `data/` - Local Parquet files

## License

MIT