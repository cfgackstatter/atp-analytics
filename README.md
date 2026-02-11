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

**Backend:** FastAPI, Polars, Playwright, BeautifulSoup4  
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

Player scraping uses Playwright (headless browser) and is managed through the admin interface at `/admin`.

### Admin Features:

- Scrape ATP rankings (singles/doubles)
- Scrape player biographical data
- Scrape tournament results
- View scraping job history

## Configuration

### Local Environment

- Password stored in `.admin-password.txt` (gitignored)
- Data stored in `./data/` directory
- Set via Makefile for local testing

### Production Environment

- Password set once: `eb setenv ADMIN_PASSWORD=$(cat .admin-password.txt)`
- Data stored in S3
- Environment variables managed via EB console

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

- Local: Check `.admin-password.txt` exists
- Production: Verify set with `eb printenv`

### Docker build fails:

- Clear cache: `make clean && make build`
- Check Dockerfile syntax
- Verify base image is accessible

## Files Not in Git

- `.admin-password.txt` - Production password
- `data/` - Local Parquet files

## License

MIT