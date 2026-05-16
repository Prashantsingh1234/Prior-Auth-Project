# Makefile — PA Review Platform developer commands
# Usage: make <target>
# Requires: docker, docker compose, kubectl, python 3.11+

.PHONY: help dev prod build push test lint format clean migrate shell logs \
        k8s-staging k8s-prod k8s-status k8s-rollback \
        load-test smoke-test secrets-check

SHELL := /bin/bash
IMAGE  ?= pa-review-platform
TAG    ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo "dev")
REGISTRY ?= ghcr.io/your-org
NAMESPACE ?= pa-platform

# ── Help ───────────────────────────────────────────────────────────────────
help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-25s\033[0m %s\n", $$1, $$2}'

# ── Local Development ──────────────────────────────────────────────────────
dev: ## Start full local dev stack (hot-reload)
	docker compose up --build

dev-bg: ## Start dev stack in background
	docker compose up --build -d
	@echo "Stack running. API: http://localhost:8000/docs"

down: ## Stop all dev services
	docker compose down

restart: ## Restart API container only
	docker compose restart pa-api

logs: ## Tail all service logs
	docker compose logs -f

logs-api: ## Tail API logs only
	docker compose logs -f pa-api

logs-worker: ## Tail worker logs only
	docker compose logs -f pa-worker

shell: ## Open a shell inside the running API container
	docker compose exec pa-api /bin/bash

# ── Production (docker compose) ────────────────────────────────────────────
prod: ## Start production stack (requires .env with real values)
	@echo "WARNING: Ensure .env has production values."
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

prod-down: ## Stop production stack
	docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# ── Build & Push ──────────────────────────────────────────────────────────
build: ## Build production Docker image
	docker build \
		--target production \
		--build-arg BUILD_DATE=$(shell date -u +%Y-%m-%dT%H:%M:%SZ) \
		--build-arg GIT_SHA=$(shell git rev-parse HEAD) \
		-t $(IMAGE):$(TAG) \
		-t $(IMAGE):latest \
		.

push: build ## Build and push to registry
	docker tag $(IMAGE):$(TAG) $(REGISTRY)/$(IMAGE):$(TAG)
	docker tag $(IMAGE):latest $(REGISTRY)/$(IMAGE):latest
	docker push $(REGISTRY)/$(IMAGE):$(TAG)
	docker push $(REGISTRY)/$(IMAGE):latest
	@echo "Pushed: $(REGISTRY)/$(IMAGE):$(TAG)"

# ── Database ───────────────────────────────────────────────────────────────
migrate: ## Run Alembic migrations (against local docker MySQL)
	docker compose exec pa-api alembic upgrade head

migrate-rollback: ## Roll back last Alembic migration
	docker compose exec pa-api alembic downgrade -1

migrate-status: ## Show current Alembic revision
	docker compose exec pa-api alembic current

migrate-history: ## Show Alembic migration history
	docker compose exec pa-api alembic history --verbose

new-migration: ## Create a new migration (NAME=describe_the_change)
	@if [ -z "$(NAME)" ]; then echo "Usage: make new-migration NAME=add_something"; exit 1; fi
	docker compose exec pa-api alembic revision --autogenerate -m "$(NAME)"

# ── Testing ────────────────────────────────────────────────────────────────
test: ## Run full test suite
	pytest app/tests/ --tb=short -q

test-unit: ## Run unit tests only
	pytest app/tests/unit/ --tb=short -q

test-integration: ## Run integration tests (requires running docker stack)
	pytest app/tests/integration/ --tb=short -q

test-security: ## Run security tests + bandit SAST
	pytest app/tests/security/ -v
	bandit -r app/ -ll --exclude app/tests/

test-cov: ## Run tests with HTML coverage report
	pytest app/tests/ \
		--cov=app \
		--cov-report=html \
		--cov-report=term-missing \
		--cov-fail-under=70
	@echo "Coverage report: htmlcov/index.html"

load-test: ## Run Locust load test (TARGET_URL required)
	@if [ -z "$(TARGET_URL)" ]; then echo "Usage: make load-test TARGET_URL=http://localhost:8000"; exit 1; fi
	locust \
		-f app/tests/load/locustfile.py \
		--host=$(TARGET_URL) \
		--users=50 \
		--spawn-rate=5 \
		--run-time=120s \
		--headless \
		--csv=load-results

smoke-test: ## Quick smoke test against TARGET_URL
	@if [ -z "$(TARGET_URL)" ]; then echo "Usage: make smoke-test TARGET_URL=http://localhost:8000"; exit 1; fi
	curl -f $(TARGET_URL)/api/v1/health/live && echo "Live check OK"
	curl -f $(TARGET_URL)/api/v1/health/ready && echo "Ready check OK"

# ── Lint & Format ──────────────────────────────────────────────────────────
lint: ## Run all linters
	ruff check app/
	ruff format --check app/
	black --check app/

format: ## Auto-format code
	ruff format app/
	black app/
	ruff check --fix app/

typecheck: ## Run mypy type checks (advisory)
	mypy app/ --ignore-missing-imports --no-error-summary || true

# ── Kubernetes ─────────────────────────────────────────────────────────────
k8s-staging: ## Apply k8s manifests to staging namespace
	kubectl apply -k k8s/ --namespace=pa-platform-staging

k8s-prod: ## Apply k8s manifests to production namespace (requires approval)
	@echo "Deploying to PRODUCTION. Press Ctrl+C within 10s to cancel."
	@sleep 10
	kubectl apply -k k8s/ --namespace=$(NAMESPACE)

k8s-status: ## Show pod status in namespace
	kubectl get pods,svc,hpa,pdb --namespace=$(NAMESPACE)

k8s-logs: ## Stream API pod logs from k8s
	kubectl logs -l app=pa-api --namespace=$(NAMESPACE) -f --tail=100

k8s-rollback: ## Roll back last API deployment
	kubectl rollout undo deployment/pa-api --namespace=$(NAMESPACE)
	kubectl rollout status deployment/pa-api --namespace=$(NAMESPACE)

k8s-restart: ## Force pod restart (e.g. after secret rotation)
	kubectl rollout restart deployment/pa-api --namespace=$(NAMESPACE)
	kubectl rollout restart deployment/pa-worker --namespace=$(NAMESPACE)

# ── Secrets ────────────────────────────────────────────────────────────────
secrets-check: ## Verify all required env vars are set in .env
	@python -c "
	import os, sys
	required = [
	    'SECRET_KEY', 'DATABASE_URL', 'REDIS_URL',
	    'OPENAI_API_KEY', 'PINECONE_API_KEY',
	]
	missing = [k for k in required if not os.getenv(k)]
	if missing:
	    print('MISSING required env vars:', ', '.join(missing))
	    sys.exit(1)
	print('All required secrets present.')
	"

generate-secret-key: ## Generate a new SECRET_KEY
	@python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"

# ── Utilities ──────────────────────────────────────────────────────────────
clean: ## Remove Docker containers, volumes, and caches
	docker compose down -v --remove-orphans
	docker system prune -f
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true

env-setup: ## Copy .env.example to .env (first-time setup)
	@if [ -f .env ]; then echo ".env already exists — not overwriting."; else cp .env.example .env && echo ".env created. Edit it before starting."; fi

openapi: ## Download OpenAPI spec from running server
	curl -s http://localhost:8000/openapi.json | python -m json.tool > openapi.json
	@echo "Saved to openapi.json"

deps-update: ## Update requirements.txt from pyproject.toml
	pip compile pyproject.toml -o requirements.txt
	pip compile pyproject.toml --extra dev -o requirements-dev.txt