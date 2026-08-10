.PHONY: help build dev test deploy sync-env logs ssh clean status check-password

# Variables
IMAGE_NAME := atp-analytics
PASSWORD := $(shell cat ./.admin-password.txt 2>/dev/null)

check-password:
	@if [ -z "$(PASSWORD)" ]; then \
		echo "Error: .admin-password.txt is missing or empty."; \
		echo "Create it with a strong secret, then: make sync-env"; \
		exit 1; \
	fi

help:
	@echo "ATP Analytics Development Commands"
	@echo ""
	@echo "  make dev         - Run locally with uvicorn + S3 (fast, no Docker)"
	@echo "  make build       - Build Docker image (no cache)"
	@echo "  make test        - Run locally in Docker with local data"
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

sync-env: check-password
	@echo "Syncing production env from .admin-password.txt ..."
	@echo "  ADMIN_PASSWORD=<from file>  FORCE_HTTPS=true  ENABLE_DOCS=false"
	eb setenv \
		ADMIN_PASSWORD="$(PASSWORD)" \
		FORCE_HTTPS=true \
		ENABLE_DOCS=false \
		USE_S3=true \
		AWS_REGION=us-east-1
	@echo "EB environment variables updated."

dev: check-password
	@echo "Starting local dev server (http://localhost:8000)..."
	@echo "Admin dashboard: http://localhost:8000/admin/dashboard"
	@echo "API docs: http://localhost:8000/docs"
	ADMIN_PASSWORD=$(PASSWORD) \
	USE_S3=true \
	ENABLE_DOCS=true \
	FORCE_HTTPS=false \
	uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000

build:
	@echo "Building frontend..."
	cd frontend && npm run build && cp -r dist/* ../backend/static/
	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME) . --no-cache

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
	eb deploy
	@echo "Deployment complete! Run 'make logs' to view logs."

logs:
	@echo "Streaming EB logs (Ctrl+C to exit)..."
	eb logs --stream

ssh:
	@echo "Connecting to EB instance..."
	eb ssh

clean:
	@echo "Cleaning up Docker images..."
	docker rmi $(IMAGE_NAME) || true
	docker system prune -f

status:
	@echo "EB Environment Status:"
	eb status
	@echo ""
	@echo "Environment Variables:"
	eb printenv