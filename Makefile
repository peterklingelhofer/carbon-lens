.PHONY: help dev test lint fix migrate docker up down clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Local Development ──────────────────────────────────────────

dev: ## Start API + frontend in dev mode (hot reload)
	@echo "API → http://localhost:8000   |   App → http://localhost:5173/dashboard"
	@set -a; [ -f .env ] && . ./.env; set +a; \
		uv run serve & API_PID=$$!; \
		trap "kill $$API_PID 2>/dev/null" EXIT INT TERM; \
		cd web && npm run dev

api: ## Start API server only
	@set -a; [ -f .env ] && . ./.env; set +a; uv run serve

web: ## Start frontend dev server only
	cd web && npm run dev

# ── Testing & Quality ──────────────────────────────────────────

test: ## Run all Python tests
	uv run pytest tests/ -v

test-fast: ## Run tests without verbose output
	uv run pytest tests/ -q

lint: ## Run linter (ruff)
	uv run ruff check src tests
	cd web && npx tsc --noEmit

fix: ## Auto-fix lint errors
	uv run ruff check src tests --fix
	uv run ruff format src tests

# ── Database ───────────────────────────────────────────────────

migrate: ## Run database migrations (requires Postgres running)
	uv run alembic upgrade head

migrate-new: ## Create a new migration (usage: make migrate-new MSG="add foo table")
	uv run alembic revision --autogenerate -m "$(MSG)"

# ── Docker ─────────────────────────────────────────────────────

docker: ## Build all Docker images
	docker compose build

up: ## Start all services (Postgres + API + Web)
	docker compose up -d
	@echo ""
	@echo "  API:  http://localhost:8000"
	@echo "  Web:  http://localhost:5173"
	@echo "  Docs: http://localhost:8000/docs"
	@echo ""

down: ## Stop all services
	docker compose down

logs: ## Tail logs from all services
	docker compose logs -f

# ── Setup ──────────────────────────────────────────────────────

install: ## Install all dependencies (backend + frontend)
	uv sync --all-extras
	cd web && npm install

setup: install ## Full setup: install deps, copy env, build frontend
	@test -f .env || cp .env.example .env
	@echo "Edit .env to add your API keys (EIA, GridStatus, etc.)"
	cd web && npm run build
	@echo ""
	@echo "Ready! Run 'make dev' to start developing."

# ── Cleanup ────────────────────────────────────────────────────

clean: ## Remove build artifacts and caches
	rm -rf .pytest_cache .ruff_cache web/dist web/node_modules/.cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
