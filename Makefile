# ============================================================
# Polymarket Agent - Makefile
# ============================================================

.PHONY: help dev build up down logs db-upgrade db-migrate test lint clean

# ----- Variables -----
APP_NAME      := polymarket-agent
COMPOSE_FILE  := docker-compose.yml
PY            := python
 PIP           := $(PY) -m pip
 UV            := $(PY) -m uvicorn
 MIGRATE       := $(PY) -m alembic
 COMPOSE       := docker compose

# ----- Colors -----
GREEN  := \033[0;32m
YELLOW := \033[0;33m
NC     := \033[0m

# ============================================================
# Help
# ============================================================
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-18s$(NC) %s\n", $$1, $$2}'

# ============================================================
# Development
# ============================================================
dev: ## Run locally with uvicorn (requires venv and DB)
	@echo "$(YELLOW)Starting dev server...$(NC)"
	$(UV) apps.server:app --reload --port 8000

# ============================================================
# Docker
# ============================================================
build: ## Build Docker image
	@echo "$(YELLOW)Building Docker image...$(NC)"
	docker build -t $(APP_NAME):latest .

up: ## Start all services (postgres + redis + app)
	@echo "$(YELLOW)Starting services...$(NC)"
	$(COMPOSE) up -d

down: ## Stop all services
	@echo "$(YELLOW)Stopping services...$(NC)"
	$(COMPOSE) down

logs: ## Tail app logs
	$(COMPOSE) logs -f app

logs-all: ## Tail all service logs
	$(COMPOSE) logs -f

restart: down up ## Restart all services

# ============================================================
# Database
# ============================================================
db-upgrade: ## Run Alembic migrations
	@echo "$(YELLOW)Running database migrations...$(NC)"
	$(COMPOSE) exec app alembic upgrade head

db-migrate: ## Generate migration from model changes
	@echo "$(YELLOW)Generating migration...$(NC)"
	$(COMPOSE) exec app alembic revision --autogenerate -m "$(MSG)"

db-downgrade: ## Downgrade last migration
	@echo "$(YELLOW)Downgrading...$(NC)"
	$(COMPOSE) exec app alembic downgrade -1

db-shell: ## Open psql shell
	$(COMPOSE) exec postgres psql -U postgres -d polymarket_agent

# ============================================================
# Testing
# ============================================================
test: ## Run all tests (unit + integration)
	@echo "$(YELLOW)Running tests...$(NC)"
	pytest tests/ -v --tb=short

test-unit: ## Run unit tests only
	@echo "$(YELLOW)Running unit tests...$(NC)"
	pytest tests/unit/ -v --tb=short

test-integration: ## Run integration tests only
	@echo "$(YELLOW)Running integration tests...$(NC)"
	pytest tests/integration/ -v --tb=short

test-replay: ## Run replay tests only
	@echo "$(YELLOW)Running replay tests...$(NC)"
	pytest tests/replay/ -v --tb=short

test-cov: ## Run tests with coverage report
	@echo "$(YELLOW)Running tests with coverage...$(NC)"
	pytest tests/ --cov=apps --cov-report=term-missing --cov-report=html

# ============================================================
# Linting & Type Checking
# ============================================================
lint: ## Run ruff lint
	@echo "$(YELLOW)Linting...$(NC)"
	ruff check apps/ libs/ tests/

lint-fix: ## Run ruff with auto-fix
	@echo "$(YELLOW)Auto-fixing lint issues...$(NC)"
	ruff check apps/ libs/ tests/ --fix

typecheck: ## Run mypy type checking
	@echo "$(YELLOW)Type checking...$(NC)"
	mypy apps/ libs/ --ignore-missing-imports

format: lint-fix typecheck ## Full code quality check + format

# ============================================================
# Utility
# ============================================================
clean: ## Remove build artifacts, cache, and venv
	@echo "$(YELLOW)Cleaning...$(NC)"
	rm -rf build dist *.egg-info
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .ruff_cache

bootstrap: ## One-time environment bootstrap (create venv + install deps)
	@echo "$(YELLOW)Bootstrapping environment...$(NC)"
	$(PY) -m venv venv && \
		./venv/Scripts/pip install -e .[dev]

.DEFAULT_GOAL := help
