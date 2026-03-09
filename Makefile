SHELL := /bin/bash

.DEFAULT_GOAL := help

BACKEND_DIR := apps/backend
WEB_DIR := apps/web
ENV_FILE ?= .env
DEMO_ENV_FILE ?= .env.demo
API_BASE_URL ?= http://localhost:8000
PNPM ?= corepack pnpm
WEBHOOK_URL ?= http://localhost:8000/api/webhooks/notion
WEBHOOK_PAGE_ID ?= alice_page
WEBHOOK_PAYLOAD_FILE ?=

.PHONY: \
	help \
	setup env-init deps demo real replay-webhook replay-webhook-demo run-backend-demo run-backend run-web test lint \
	lint-fix backend-test backend-lint backend-lint-fix backend-deps web-deps \
	compose-logs compose-down doctor clean

help: ## Show available commands (ordered by workflow priority)
	@printf "\nNotion Graph Make Targets\n\n"
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_.-]+:.*## / {printf "  %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Primary workflows
setup: env-init deps ## Bootstrap env files and install all dependencies

env-init: ## Create .env and .env.demo from templates if missing
	@if [ ! -f "$(ENV_FILE)" ]; then cp .env.example "$(ENV_FILE)" && echo "Created $(ENV_FILE)"; else echo "$(ENV_FILE) already exists"; fi
	@if [ ! -f "$(DEMO_ENV_FILE)" ]; then cp .env.demo.example "$(DEMO_ENV_FILE)" && echo "Created $(DEMO_ENV_FILE)"; else echo "$(DEMO_ENV_FILE) already exists"; fi

deps: backend-deps web-deps ## Install backend + web dependencies

demo: ## Run demo stack in Docker (fixtures, no real Notion API)
	@if [ ! -f "$(DEMO_ENV_FILE)" ]; then echo "Missing $(DEMO_ENV_FILE). Run 'make env-init' first." && exit 1; fi
	docker compose --env-file "$(DEMO_ENV_FILE)" up --build

real: ## Run real stack in Docker (uses live Notion API)
	@if [ ! -f "$(ENV_FILE)" ]; then echo "Missing $(ENV_FILE). Run 'make env-init' first." && exit 1; fi
	docker compose --env-file "$(ENV_FILE)" up --build

replay-webhook: ## Send signed webhook to local backend using secret from .env
	@if [ ! -f "$(ENV_FILE)" ]; then echo "Missing $(ENV_FILE). Run 'make env-init' first." && exit 1; fi
	@set -a; source "$(ENV_FILE)"; set +a; \
	secret="$${NOTION_WEBHOOK_SECRET:-}"; \
	if [ -z "$$secret" ]; then \
	  echo "NOTION_WEBHOOK_SECRET is empty in $(ENV_FILE). Set it first for signed replay."; \
	  exit 1; \
	fi; \
	bash ./scripts/replay_notion_webhook.sh \
	  --url "$(WEBHOOK_URL)" \
	  --secret "$$secret" \
	  --page-id "$(WEBHOOK_PAGE_ID)" \
	  --payload-file "$(WEBHOOK_PAYLOAD_FILE)"

replay-webhook-demo: ## Send signed webhook using secret from .env.demo (demo mode)
	@if [ ! -f "$(DEMO_ENV_FILE)" ]; then echo "Missing $(DEMO_ENV_FILE). Run 'make env-init' first." && exit 1; fi
	@set -a; source "$(DEMO_ENV_FILE)"; set +a; \
	secret="$${NOTION_WEBHOOK_SECRET:-}"; \
	if [ -z "$$secret" ]; then \
	  echo "NOTION_WEBHOOK_SECRET is empty in $(DEMO_ENV_FILE). Set it first for signed replay."; \
	  exit 1; \
	fi; \
	bash ./scripts/replay_notion_webhook.sh \
	  --url "$(WEBHOOK_URL)" \
	  --secret "$$secret" \
	  --page-id "$(WEBHOOK_PAGE_ID)" \
	  --payload-file "$(WEBHOOK_PAYLOAD_FILE)"

run-backend-demo: ## Run backend locally in fixture demo mode using .env.demo
	@if [ ! -f "$(DEMO_ENV_FILE)" ]; then echo "Missing $(DEMO_ENV_FILE). Run 'make env-init' first." && exit 1; fi
	@set -a; source "$(DEMO_ENV_FILE)"; set +a; \
	export NOTION_FIXTURE_PATH=tests/fixtures/notion_fixture.json; \
	cd "$(BACKEND_DIR)" && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-backend: ## Run backend locally against real Notion API using .env
	@if [ ! -f "$(ENV_FILE)" ]; then echo "Missing $(ENV_FILE). Run 'make env-init' first." && exit 1; fi
	@set -a; source "$(ENV_FILE)"; set +a; \
	cd "$(BACKEND_DIR)" && uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

run-web: ## Run web locally (set API_BASE_URL=http://localhost:8000 by default)
	@cd "$(WEB_DIR)" && NEXT_PUBLIC_API_BASE_URL="$(API_BASE_URL)" $(PNPM) dev

test: backend-test ## Run test suite

lint: backend-lint ## Run lint checks

# Quality + dependency helpers
lint-fix: backend-lint-fix ## Auto-fix lint where possible

backend-test: ## Run backend tests
	@cd "$(BACKEND_DIR)" && uv run pytest

backend-lint: ## Run backend lint
	@cd "$(BACKEND_DIR)" && uv run ruff check .

backend-lint-fix: ## Auto-fix backend lint where safe
	@cd "$(BACKEND_DIR)" && uv run ruff check . --fix

backend-deps: ## Install backend dependencies with dev extras
	@cd "$(BACKEND_DIR)" && uv sync --extra dev

web-deps: ## Install web dependencies
	@$(PNPM) --dir "$(WEB_DIR)" install

# Operational helpers
compose-logs: ## Follow Docker logs
	docker compose logs -f

compose-down: ## Stop Docker stack
	docker compose down

doctor: ## Check required local tools
	@command -v uv >/dev/null || (echo "uv is required" && exit 1)
	@command -v corepack >/dev/null || (echo "corepack is required for pnpm" && exit 1)
	@command -v docker >/dev/null || (echo "docker is required" && exit 1)
	@echo "Tooling looks good."

clean: ## Remove local caches/artifacts
	rm -rf "$(BACKEND_DIR)/.pytest_cache" "$(BACKEND_DIR)/.ruff_cache" "$(WEB_DIR)/.next"
