.PHONY: help build test deploy logs ssh clean status

# Variables
IMAGE_NAME := atp-analytics
PASSWORD := $(shell cat ./.admin-password.txt 2>/dev/null || echo "changeme123")

help:
	@echo "ATP Analytics Development Commands"
	@echo ""
	@echo "  make build       - Build Docker image (no cache)"
	@echo "  make test        - Run locally with test data"
	@echo "  make deploy      - Deploy to AWS Elastic Beanstalk"
	@echo "  make logs        - Stream EB logs"
	@echo "  make ssh         - SSH into EB instance"
	@echo "  make clean       - Remove local Docker images"
	@echo "  make status      - Show EB status and env vars"
	@echo ""

build:
	@echo "Building Docker image..."
	docker build -t $(IMAGE_NAME) . --no-cache

test: build
	@echo "Starting local test environment..."
	docker run -p 8000:8000 \
		-e USE_S3=false \
		-e ADMIN_PASSWORD=$(PASSWORD) \
		-v $$(pwd)/data:/app/data \
		$(IMAGE_NAME)

deploy:
	@echo "Deploying to Elastic Beanstalk..."
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
