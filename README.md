# TennisRank.net (ATP Analytics)

Full-stack app for comparing ATP ranking careers over time — singles and doubles, with tournament titles on the chart.

**Live UI:** viewport chart shell, shareable links, rank or points, date or age axis.

## Features

- Interactive singles / doubles charts (Chart.js)
- Player search with autocomplete; multi-player compare with stable colors
- **Shareable URLs** — players, type, axis, metric, date range, and title filters stay in the query string
- **Rank or Points** mode
- **Date or Age** x-axis (age needs birthdates from scraped bios)
- Tournament title markers (sized circles) with **GS / ATP / Challenger / ITF** filters
- Hover bios on player chips (country, DOB, height, hand, etc.)
- PNG export with baked-in legend and light `tennisrank.net` watermark
- Clear all, date-range controls, and auto-widen when a short window has no data
- Historical rankings, tournaments, and bios from ATP Tour (S3 in production)

## Tech Stack

**Backend:** FastAPI, Polars, Playwright  
**Frontend:** React, TypeScript, Chart.js, Tailwind CSS  
**Deployment:** AWS Elastic Beanstalk, Docker, S3

## Quick Start

### Local Development

Preferred path (no Docker): rebuild the frontend into `backend/static/` and run the API with uvicorn.

```bash
# One-time setup
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
# Install browsers into ~/.cache/ms-playwright (unset sandbox overrides)
env -u PLAYWRIGHT_BROWSERS_PATH ./venv/bin/playwright install chromium
# Create .admin-password.txt with a strong secret

# Day-to-day: API + built UI on :8000 (USE_S3=true for scrapes)
make dev

# Open http://localhost:8000
# Admin: http://localhost:8000/admin/dashboard  (password from .admin-password.txt)
```

For UI iteration with hot reload, use `make dev-hot` (Vite on :3000, API on :8000).

Docker alternative (builds the full image, local `./data`):

```bash
make test
```

### Shareable chart URLs

Example:

```text
/?players=s980,f324&type=singles&metric=points&axis=age&range=All&titles=gs,atp
```

| Param | Values | Default |
|-------|--------|---------|
| `players` | comma-separated ATP player ids | (none) |
| `type` | `singles` \| `doubles` | `singles` |
| `metric` | `rank` \| `points` | `rank` |
| `axis` | `date` \| `age` | `date` |
| `range` | `YTD` \| `1Y` \| `3Y` \| `5Y` \| `All` | `1Y` |
| `titles` | `gs,atp,ch,fu` or `none` | all types |

### Deployment

Install the EB CLI **outside** the project venv (see [README.dev.md](README.dev.md)), then:

```bash
make deploy   # sync-env, then commit/push if needed, eb deploy
make logs
make ssh
```

### Available Commands

```bash
make help               # Show all commands
make dev                # Rebuild frontend + run API on :8000
make dev-hot            # API :8000 + Vite HMR on :3000
make playwright-install # Install Chromium for local scrapes
make pytest             # Run unit tests
make build              # Build Docker image
make test               # Run locally in Docker
make deploy             # Deploy to AWS EB
make sync-env           # Push admin password + prod env vars only
make logs               # Stream production logs
make ssh                # SSH into EB instance
make status             # EB status + env vars
make clean              # Clean Docker images
```

## Project Structure

```text
atp-analytics/
├── backend/
│   ├── api/
│   │   ├── main.py          # FastAPI endpoints + static UI
│   │   └── admin.py         # Admin scrape / summary APIs
│   ├── scraper/             # ATP scrapers (Playwright)
│   ├── storage/             # S3 / local Parquet
│   ├── templates/           # Admin dashboard HTML
│   └── static/              # Built React assets (gitignore hashed bundles)
├── frontend/                # React app (Vite)
├── Dockerfile
├── Dockerrun.aws.json
├── Makefile
├── .admin-password.txt      # Admin password (not in git)
└── data/                    # Local Parquet (not in git)
```

## Data Scraping

Scrapes are **manual** via `/admin/dashboard` (no scheduled weekly job). Jobs run in a subprocess so the site stays up; concurrent scrapes return 409. Merges are locked and rankings deduped.

### Admin

- Scrape rankings (singles / doubles), tournaments, and player bios
- Data summary: weeks covered, bio coverage, tournament counts, system / Playwright info
- Job history and scrape controls

## Configuration

### Local

- **Required** `.admin-password.txt` (gitignored) — no default
- `make dev` / `make test` refuse to start if missing
- Admin APIs: `Authorization: Bearer <password>`
- Data in `./data/` (or S3 when `USE_S3=true`)

### Production

- `make deploy` runs `sync-env` then deploys code
- Sync sets `ADMIN_PASSWORD` from `.admin-password.txt`, `FORCE_HTTPS=true`, `ENABLE_DOCS=false`, S3 settings
- OpenAPI `/docs` off in prod; CORS same-origin unless `CORS_ORIGINS` is set
- Data in S3

## Deployment Architecture

- Docker image with Playwright preinstalled
- Elastic Beanstalk for the container
- S3 for Parquet (rankings, tournaments, players)
- GitHub for source; deploy with `make deploy`

## Development Workflow

1. Change code locally
2. `make dev` (or `make test` for a Docker smoke check)
3. Refresh data via `/admin/dashboard` while the API is running
4. `make deploy` (prompts to commit if dirty, then push + EB deploy)
5. `make logs` to monitor

More detail: [README.dev.md](README.dev.md).

## Troubleshooting

### Playwright “Executable doesn't exist” locally

- `make playwright-install`
  or `env -u PLAYWRIGHT_BROWSERS_PATH ./venv/bin/playwright install chromium`
- Unset `PLAYWRIGHT_BROWSERS_PATH` if it points at a Cursor sandbox cache
- After bumping the `playwright` package, reinstall browsers

### Player scraping returns 0 players

- Check `make logs` (prod) or the `make dev` terminal
- Confirm Chromium via `make playwright-install` (preinstalled in Docker)
- Check EB instance memory on small hosts

### Password not working

- Local: `.admin-password.txt` non-empty (`make check-password`)
- Production: `make status` / `eb printenv` for `ADMIN_PASSWORD`
- Unset → admin APIs return 503 (fail closed)

### `eb` outdated / not found on deploy

- Install outside the venv: `python3 -m pip install --user -U awsebcli` (or `pipx install awsebcli`)
- `make deploy` uses `~/.local/bin/eb`, not `./venv/bin/eb`

### Docker build fails

- `make clean && make build`

## Files Not in Git

- `.admin-password.txt`
- `data/`
- `backend/static/assets/` (hashed JS/CSS from the frontend build)
- `venv/`

## License

MIT
