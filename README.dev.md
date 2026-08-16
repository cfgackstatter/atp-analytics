# ATP Analytics Development

## Quick Commands

### Help
- `make help` - Show all available commands

### Local Development
- `make dev` - Rebuild frontend into `backend/static/`, run API on :8000 (preferred for scrapes + full app)
- `make dev-hot` - API on :8000 + Vite HMR on :3000 (best for React work; open :3000)
- `make playwright-install` - Install Chromium into `~/.cache/ms-playwright` (needed for admin scrapes under `make dev`)
- `make pytest` - Run unit tests
- `make test` - Build and run locally in Docker with `./data`
- `make build` - Build Docker image only (no cache)
- Open http://localhost:8000 (or :3000 for `dev-hot`)
- Password stored in `.admin-password.txt`

### Deployment
- `make deploy` - Auto-commit, push, and deploy to production
- `make logs` - Stream production logs in real-time
- `make ssh` - SSH into production instance

### Monitoring
- `make status` - Show EB environment status and environment variables
- `make logs` - Stream logs (Ctrl+C to exit)

### Cleanup
- `make clean` - Remove local Docker images and prune system

## Workflow

### Typical Development Cycle
```bash
# 0. One-time: venv + deps + browsers
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
make playwright-install

# 1. Make code changes
# 2. Run locally (rebuilds UI into backend/static)
make dev
# Admin scrapes: http://localhost:8000/admin/dashboard

# 3. Deploy (auto-commits, pushes, and deploys)
make deploy

# 4. Monitor deployment
make logs
```

### Smart Deploy Behavior

- If you have uncommitted changes: prompts for commit message
- If working tree is clean: pushes and deploys existing commits
- Never fails on "nothing to commit"

## Files Not in Git

- `.admin-password.txt` - Production password (keep safe!)
- `data/` - Local Parquet files
- `.env` - Not needed with Makefile

## Admin password

- Local source of truth: `.admin-password.txt` (required, no default)
- `make dev` / `make test` fail if the file is missing
- Data updates are **manual only** via `/admin/dashboard` (no weekly/EventBridge task)
- Auth: `Authorization: Bearer <password>` on `/admin/*` API routes (dashboard HTML is public)
- Rate limit: 60 requests / minute / IP on admin APIs
- Scrapes run in a **subprocess** (web process stays responsive); only one scrape at a time (HTTP 409 if busy)
- Parquet/S3 merges use a file write lock + rankings dedupe on `(player_id, date)`
- One Playwright browser per job with `SCRAPE_CONCURRENCY` parallel pages (default 2); shared retries/backoff; heavier resource blocking
- Ranking-date cache (12h), checkpoint every 5 weeks, skip complete past tournament years
- On tiny EB hosts set `SCRAPE_CONCURRENCY=1` (and optionally `PLAYWRIGHT_SINGLE_PROCESS=true`)
- Scrapers soft-fail after retries; player bio attempts recorded (`scrape_attempted_at`) with cooldown
- Prefer ATP `player_slug` from ranking hrefs (Unicode-folded name slug as fallback)
- Unit tests: `make pytest` (or `pytest`)
- CORS off by default (same-origin app); set `CORS_ORIGINS=https://a.com,https://b.com` only if needed
- `/docs` enabled locally (`ENABLE_DOCS=true`); disabled in prod via `make sync-env`

Example:
```bash
curl -H "Authorization: Bearer $(cat .admin-password.txt)" \
  http://localhost:8000/admin/data-summary
```

## Production Environment Variables

Two different things:

| Command | What it does |
|---------|----------------|
| `make sync-env` | Pushes env vars only (`ADMIN_PASSWORD` from `.admin-password.txt`, `FORCE_HTTPS=true`, S3 settings). No new code. |
| `make deploy` | Runs `sync-env`, then commits/pushes (if needed) and `eb deploy` (new code). |

Usual path after local changes: just `make deploy`.

Password-only change (no code): edit `.admin-password.txt`, then `make sync-env`.

Verify with:
```bash
make status
```

## Troubleshooting

### Playwright “Executable doesn't exist” on local rankings/player scrapes:

- `make dev` uses the venv Playwright package; browsers must match that version under `~/.cache/ms-playwright`
- Run `make playwright-install` (unsets `PLAYWRIGHT_BROWSERS_PATH` so Cursor sandbox caches are not used)
- After upgrading `playwright` in `requirements.txt`, reinstall browsers

### Test / Docker fails locally:

- Ensure `data/` directory exists with local data
- Check `.admin-password.txt` exists
- Verify Docker is running

### Deploy fails:

- Check `eb status` shows healthy environment
- Run `make logs` to see errors
- Verify git push succeeded

### Password issues:

- Local: `make check-password` / ensure `.admin-password.txt` is non-empty
- Production: Run `make status` to verify `ADMIN_PASSWORD` is set
- Unset password → admin APIs return 503 (no `changeme123` fallback)

## Reference

All commands defined in `Makefile` - run `make help` for quick reference.