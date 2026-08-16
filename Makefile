.PHONY: help build frontend-build check-venv check-eb playwright-install dev dev-hot pytest test deploy sync-env logs ssh clean status check-password

# Variables
IMAGE_NAME := atp-analytics
PASSWORD := $(shell cat ./.admin-password.txt 2>/dev/null)
VENV_PYTHON := ./venv/bin/python
VENV_UVICORN := ./venv/bin/uvicorn
# EB CLI is a host tool (not an app dependency). Prefer user/pipx install over the venv.
EB := $(firstword $(wildcard $(HOME)/.local/bin/eb) $(shell command -v eb 2>/dev/null))

check-password:
	@if [ -z "$(PASSWORD)" ]; then \
		echo "Error: .admin-password.txt is missing or empty."; \
		echo "Create it with a strong secret, then: make sync-env"; \
		exit 1; \
	fi

check-eb:
	@if [ -z "$(EB)" ] || [ ! -x "$(EB)" ]; then \
		echo "Error: Elastic Beanstalk CLI (eb) not found."; \
		echo "Install outside the project venv (recommended):"; \
		echo "  pipx install awsebcli"; \
		echo "  # or: python3 -m pip install --user -U awsebcli"; \
		exit 1; \
	fi

check-venv:
	@if [ ! -x "$(VENV_UVICORN)" ]; then \
		echo "Error: $(VENV_UVICORN) not found."; \
		echo "Create the venv and install deps:"; \
		echo "  python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"; \
		exit 1; \
	fi

# Build React into backend/static (what uvicorn/EB serve). Cleans old hashed assets.
frontend-build:
	@echo "Building frontend into backend/static/..."
	@if [ ! -d frontend/node_modules ]; then \
		echo "Installing frontend deps..."; \
		cd frontend && npm install; \
	fi
	cd frontend && npm run build
	rm -rf backend/static/assets
	mkdir -p backend/static
	cp -r frontend/dist/. backend/static/
	@echo "Frontend synced to backend/static/"

help:
	@echo "ATP Analytics Development Commands"
	@echo ""
	@echo "  make dev         - Rebuild frontend into static, run API on :8000 (latest UI+API)"
	@echo "  make dev-hot     - API :8000 + Vite :3000 with hot reload (best for UI work)"
	@echo "  make frontend-build - Rebuild React into backend/static only"
	@echo "  make playwright-install - Install Chromium for local scrapes (~/.cache/ms-playwright)"
	@echo "  make build       - frontend-build + Docker image (no cache)"
	@echo "  make pytest      - Run unit tests"
	@echo "  make test        - Run app locally in Docker with local data"
	@echo "  make sync-env    - Push ADMIN_PASSWORD + FORCE_HTTPS to EB (no code deploy)"
	@echo "  make deploy      - sync-env, then commit/push/deploy code to EB"
	@echo "  make logs        - Stream EB logs"
	@echo "  make ssh         - SSH into EB instance"
	@echo "  make clean       - Remove local Docker images"
	@echo "  make status      - Show EB status and env vars"
	@echo ""
	@echo "Admin password: required via .admin-password.txt (no default)."
	@echo "Auth: Authorization Bearer token (not query string)."
	@echo "Manual updates only: use /admin/dashboard (no scheduled tasks)."
	@echo ""

sync-env: check-password check-eb
	@echo "Syncing production env from .admin-password.txt ..."
	@echo "  ADMIN_PASSWORD=<from file>  FORCE_HTTPS=true  ENABLE_DOCS=false"
	@$(EB) setenv \
		ADMIN_PASSWORD="$(PASSWORD)" \
		FORCE_HTTPS=true \
		ENABLE_DOCS=false \
		USE_S3=true \
		AWS_REGION=us-east-1
	@echo "EB environment variables updated."

# Browsers must live under ~/.cache/ms-playwright. Cursor may set
# PLAYWRIGHT_BROWSERS_PATH to a sandbox cache that scrapes won't see.
playwright-install: check-venv
	@echo "Installing Playwright Chromium into default cache..."
	env -u PLAYWRIGHT_BROWSERS_PATH $(VENV_PYTHON) -m playwright install chromium
	@echo "Done. Re-run scrapes via /admin/dashboard under make dev."

dev: check-password check-venv frontend-build
	@if [ -n "$$PLAYWRIGHT_BROWSERS_PATH" ]; then \
		echo "Warning: PLAYWRIGHT_BROWSERS_PATH=$$PLAYWRIGHT_BROWSERS_PATH"; \
		echo "  Scrapes expect browsers in ~/.cache/ms-playwright."; \
		echo "  Fix: unset PLAYWRIGHT_BROWSERS_PATH && make playwright-install"; \
	fi
	@echo "Starting local API + built frontend (http://localhost:8000)..."
	@echo "Admin dashboard: http://localhost:8000/admin/dashboard"
	@echo "API docs: http://localhost:8000/docs"
	@echo "Tip: use 'make dev-hot' for instant frontend reload while editing React."
	env -u PLAYWRIGHT_BROWSERS_PATH \
	ADMIN_PASSWORD=$(PASSWORD) \
	USE_S3=true \
	ENABLE_DOCS=true \
	FORCE_HTTPS=false \
	$(VENV_UVICORN) backend.api.main:app --reload --host 0.0.0.0 --port 8000

# Best for frontend iteration: Vite HMR proxies /players,/rankings,/admin,/tournaments → :8000
dev-hot: check-password check-venv
	@if [ ! -d frontend/node_modules ]; then \
		echo "Installing frontend deps..."; \
		cd frontend && npm install; \
	fi
	@if [ -n "$$PLAYWRIGHT_BROWSERS_PATH" ]; then \
		echo "Warning: PLAYWRIGHT_BROWSERS_PATH=$$PLAYWRIGHT_BROWSERS_PATH"; \
		echo "  Fix: unset PLAYWRIGHT_BROWSERS_PATH && make playwright-install"; \
	fi
	@echo "Starting API (http://localhost:8000) + Vite (http://localhost:3000)..."
	@echo "Open http://localhost:3000 for the app (hot reload)."
	@echo "Admin dashboard: http://localhost:8000/admin/dashboard"
	@trap 'kill 0' EXIT INT TERM; \
	env -u PLAYWRIGHT_BROWSERS_PATH \
	ADMIN_PASSWORD=$(PASSWORD) \
	USE_S3=true \
	ENABLE_DOCS=true \
	FORCE_HTTPS=false \
	$(VENV_UVICORN) backend.api.main:app --reload --host 0.0.0.0 --port 8000 & \
	cd frontend && npm run dev & \
	wait

build: frontend-build
	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME) . --no-cache

pytest: check-venv
	@echo "Running unit tests..."
	$(VENV_PYTHON) -m pytest -q

test: check-password build
	@echo "Starting Docker test environment (http://localhost:8000)..."
	docker run -p 8000:8000 \
		-e USE_S3=false \
		-e "ADMIN_PASSWORD=$(PASSWORD)" \
		-v "$$(pwd)/data:/app/data" \
		$(IMAGE_NAME)

deploy: sync-env
	@echo "Deploying code to Elastic Beanstalk..."
	@if [ -n "$$(git status --porcelain)" ]; then \
		git add -A; \
		read -p "Commit message: " msg; \
		git commit -m "$$msg"; \
		git push; \
	else \
		echo "No changes to commit, pushing existing commits..."; \
		git push || echo "Already up to date"; \
	fi
	# Rolling updates (e.g. root volume resize) often exceed the 10m default.
	$(EB) deploy --timeout 45
	@echo "Deployment complete! Run 'make logs' to view logs."

logs: check-eb
	@echo "Streaming EB logs (Ctrl+C to exit)..."
	$(EB) logs --stream

ssh: check-eb
	@echo "Connecting to EB instance..."
	$(EB) ssh

clean:
	@echo "Cleaning up Docker images..."
	docker rmi $(IMAGE_NAME) || true
	docker system prune -f

status: check-eb
	@echo "EB Environment Status:"
	$(EB) status
	@echo ""
	@echo "Environment Variables:"
	$(EB) printenv
