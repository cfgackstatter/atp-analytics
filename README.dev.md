# TennisRank.net — Development

Companion to the root [README.md](README.md). Day-to-day commands, scrape/auth details, and EB CLI setup.

## Quick Commands

### Help
- `make help` — all targets

### Local Development
- `make dev` — rebuild frontend → `backend/static/`, API on :8000 (preferred for scrapes + full app)
- `make dev-hot` — API :8000 + Vite HMR :3000 (React iteration; open :3000)
- `make playwright-install` — Chromium → `~/.cache/ms-playwright` (needed for admin scrapes under `make dev`)
- `make pytest` — unit tests
- `make test` — Docker build + run with `./data`
- `make build` — Docker image only (no cache)
- App: http://localhost:8000 — Admin: http://localhost:8000/admin/dashboard
- Password: `.admin-password.txt`

### Deployment
- `make sync-env` — push admin password + prod env vars only
- `make deploy` — `sync-env`, then commit/push if dirty, `eb deploy`
- `make logs` / `make ssh` / `make status`

### Cleanup
- `make clean` — remove local Docker images and prune

## Workflow

```bash
# One-time
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
make playwright-install
# also install awsebcli outside the venv (see below)

make dev
# Admin scrapes: http://localhost:8000/admin/dashboard

make deploy
make logs
```

### Smart Deploy Behavior

- Dirty tree: prompts for commit message, then push + deploy
- Clean tree: push (if needed) + deploy existing commits
- Does not fail on “nothing to commit”

## Chart / frontend notes

- Shareable query params: `players`, `type`, `metric`, `axis`, `range`, `titles` (see root README)
- `GET /players?ids=a,b` hydrates shared links (order preserved)
- Rankings for selected players return full history (no row cap when `player_ids` is set)
- Title markers: hollow circles, size by type (ITF → Challenger → ATP → GS)
- Player bios: chip hover tooltips (not chart tooltips)
- PNG export: legend + subtitle + watermark on canvas; no site header in the file

## Admin password & scrapes

- Local source of truth: `.admin-password.txt` (required, no default)
- `make dev` / `make test` fail if missing
- Data updates are **manual only** via `/admin/dashboard` (no weekly/EventBridge task)
- Auth: `Authorization: Bearer <password>` on `/admin/*` API routes (dashboard HTML is public)
- Rate limit: 60 requests / minute / IP on admin APIs — avoid re-triggering poll on every password keystroke
- Scrapes run in a **subprocess** (web process stays responsive); only one at a time (HTTP 409 if busy)
- Parquet/S3 merges: file write lock + rankings dedupe on `(player_id, date)`
- One Playwright browser per job; `SCRAPE_CONCURRENCY` parallel pages (default 2)
- Ranking-date cache (12h), checkpoint every 5 weeks, skip complete past tournament years
- Tiny EB hosts: `SCRAPE_CONCURRENCY=1` (optionally `PLAYWRIGHT_SINGLE_PROCESS=true`)
- Bio attempts recorded (`scrape_attempted_at`) with cooldown; prefer ATP `player_slug` from ranking hrefs
- CORS off by default; `/docs` on locally (`ENABLE_DOCS=true`), off in prod via `make sync-env`

Example:
```bash
curl -H "Authorization: Bearer $(cat .admin-password.txt)" \
  http://localhost:8000/admin/data-summary
```

## Production Environment Variables

| Command | What it does |
|---------|----------------|
| `make sync-env` | Env vars only (`ADMIN_PASSWORD` from `.admin-password.txt`, `FORCE_HTTPS=true`, S3, `ENABLE_DOCS=false`). No new code. |
| `make deploy` | `sync-env`, then commit/push if needed and `eb deploy`. |

Password-only change: edit `.admin-password.txt`, then `make sync-env`.

### Elastic Beanstalk CLI

Install **outside** the project venv (host tool — avoids dep conflicts and stale venv copies):

```bash
# preferred
pipx install awsebcli
pipx upgrade awsebcli

# or user site-packages
python3 -m pip install --user -U awsebcli
```

`make deploy` / `sync-env` / `logs` / `ssh` / `status` resolve `eb` from `~/.local/bin` (or `PATH`), **not** `./venv/bin/eb`.

```bash
eb --version          # should match what make uses
make status
```

## Files Not in Git

- `.admin-password.txt`
- `data/`
- `backend/static/assets/` (hashed frontend build)
- `venv/`
- `.env` — not required with the Makefile

## Troubleshooting

### Playwright “Executable doesn't exist”

- `make playwright-install` (unsets sandbox `PLAYWRIGHT_BROWSERS_PATH`)
- After upgrading `playwright` in `requirements.txt`, reinstall browsers

### Test / Docker fails locally

- `data/` present; `.admin-password.txt` non-empty; Docker running

### Deploy fails / “awsebcli is out of date”

- Upgrade the **user** install (`pip install --user -U awsebcli` or `pipx upgrade`), not the venv
- Confirm `which eb` → `~/.local/bin/eb`
- `make logs`; `eb status`

### Password issues

- Local: `make check-password`
- Production: `make status` for `ADMIN_PASSWORD`
- Unset → admin APIs return 503 (no fallback password)

## Reference

All commands: `Makefile` / `make help`.
