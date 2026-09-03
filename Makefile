# ─── PricePlus — Development Makefile ──────────────────────────────────────────
# Usage: make <target>
# All backend commands run inside backend/.venv

SHELL := /bin/bash
.DEFAULT_GOAL := help

BACKEND_DIR := backend
VENV        := $(BACKEND_DIR)/.venv
PYTHON      := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip
UVICORN     := $(VENV)/bin/uvicorn
ALEMBIC     := $(VENV)/bin/alembic
PYTEST      := $(VENV)/bin/pytest
RUFF        := $(VENV)/bin/ruff
MYPY        := $(VENV)/bin/mypy

FRONTEND_DIR := frontend

.PHONY: help install install-backend install-frontend \
        dev dev-backend dev-frontend \
        test test-unit test-integration test-cov \
        lint lint-fix type-check \
        migrate migrate-create migrate-downgrade \
        db-start db-stop redis-start redis-stop \
        setup-db clean

# ─── Help ───────────────────────────────────────────────────────────────────────
help:
	@echo ""
	@echo "PricePlus — Development Commands"
	@echo "────────────────────────────────────────────────────"
	@echo "  make install          Install all dependencies"
	@echo "  make dev              Start backend dev server"
	@echo "  make test             Run all tests"
	@echo "  make test-cov         Run tests with coverage report"
	@echo "  make lint             Run ruff linter"
	@echo "  make lint-fix         Run ruff with auto-fix"
	@echo "  make type-check       Run mypy static analysis"
	@echo "  make migrate          Run pending migrations"
	@echo "  make migrate-create m='description'  Create new migration"
	@echo "  make migrate-downgrade  Downgrade one migration"
	@echo "  make db-start         Start PostgreSQL"
	@echo "  make db-stop          Stop PostgreSQL"
	@echo "  make redis-start      Start Redis"
	@echo "  make redis-stop       Stop Redis"
	@echo "  make setup-db         Create DB users and databases"
	@echo "  make clean            Remove caches and build artifacts"
	@echo ""

# ─── Install ────────────────────────────────────────────────────────────────────
install: install-backend
	@echo "✓ Installation complete"

install-backend:
	@echo "→ Creating Python virtualenv..."
	@cd $(BACKEND_DIR) && python3 -m venv .venv
	@echo "→ Installing backend dependencies..."
	@cd $(BACKEND_DIR) && $(PIP) install --upgrade pip --quiet
	@cd $(BACKEND_DIR) && $(PIP) install -r requirements.txt -r requirements-dev.txt --quiet
	@echo "✓ Backend dependencies installed"

install-frontend:
	@echo "→ Installing frontend dependencies..."
	@cd $(FRONTEND_DIR) && npm install
	@echo "✓ Frontend dependencies installed"

# ─── Development Servers ────────────────────────────────────────────────────────
dev: dev-backend

dev-backend:
	@echo "→ Starting backend on http://localhost:8000"
	@cd $(BACKEND_DIR) && $(UVICORN) app.main:app --reload --host 0.0.0.0 --port 8000

dev-frontend:
	@echo "→ Starting frontend on http://localhost:3000"
	@cd $(FRONTEND_DIR) && npm run dev

# ─── Testing ────────────────────────────────────────────────────────────────────
test:
	@echo "→ Running all tests..."
	@cd $(BACKEND_DIR) && $(PYTEST) -v

test-unit:
	@echo "→ Running unit tests..."
	@cd $(BACKEND_DIR) && $(PYTEST) tests/unit -v

test-integration:
	@echo "→ Running integration tests..."
	@cd $(BACKEND_DIR) && $(PYTEST) tests/integration -v

test-cov:
	@echo "→ Running tests with coverage..."
	@cd $(BACKEND_DIR) && $(PYTEST) --cov=app --cov-report=term-missing --cov-report=html -v

# ─── Code Quality ───────────────────────────────────────────────────────────────
lint:
	@echo "→ Running ruff linter..."
	@cd $(BACKEND_DIR) && $(RUFF) check app/ tests/
	@echo "✓ Lint passed"

lint-fix:
	@echo "→ Running ruff with auto-fix..."
	@cd $(BACKEND_DIR) && $(RUFF) check --fix app/ tests/
	@cd $(BACKEND_DIR) && $(RUFF) format app/ tests/

type-check:
	@echo "→ Running mypy..."
	@cd $(BACKEND_DIR) && $(MYPY) app/
	@echo "✓ Type check passed"

# ─── Database Migrations ────────────────────────────────────────────────────────
migrate:
	@echo "→ Running pending migrations..."
	@cd $(BACKEND_DIR) && $(ALEMBIC) upgrade head
	@echo "✓ Migrations applied"

migrate-create:
	@if [ -z "$(m)" ]; then echo "Usage: make migrate-create m='your migration description'"; exit 1; fi
	@echo "→ Creating migration: $(m)"
	@cd $(BACKEND_DIR) && $(ALEMBIC) revision --autogenerate -m "$(m)"

migrate-downgrade:
	@echo "→ Downgrading one migration..."
	@cd $(BACKEND_DIR) && $(ALEMBIC) downgrade -1

migrate-history:
	@cd $(BACKEND_DIR) && $(ALEMBIC) history --verbose

migrate-current:
	@cd $(BACKEND_DIR) && $(ALEMBIC) current

# ─── Services ───────────────────────────────────────────────────────────────────
db-start:
	@echo "→ Starting PostgreSQL..."
	@sudo systemctl start postgresql
	@sleep 1
	@pg_isready && echo "✓ PostgreSQL is running" || echo "✗ PostgreSQL failed to start"

db-stop:
	@echo "→ Stopping PostgreSQL..."
	@sudo systemctl stop postgresql

redis-start:
	@echo "→ Starting Redis..."
	@sudo systemctl start redis-server || sudo systemctl start redis
	@sleep 0.5
	@redis-cli ping && echo "✓ Redis is running" || echo "✗ Redis failed to start"

redis-stop:
	@echo "→ Stopping Redis..."
	@sudo systemctl stop redis-server || sudo systemctl stop redis

# ─── Database Setup ─────────────────────────────────────────────────────────────
setup-db:
	@echo "→ Creating PostgreSQL user and databases..."
	@sudo -u postgres psql -c "CREATE USER priceplus WITH PASSWORD 'priceplus';" 2>/dev/null || echo "  User 'priceplus' already exists"
	@sudo -u postgres psql -c "CREATE DATABASE priceplus OWNER priceplus;" 2>/dev/null || echo "  Database 'priceplus' already exists"
	@sudo -u postgres psql -c "CREATE DATABASE priceplus_test OWNER priceplus;" 2>/dev/null || echo "  Database 'priceplus_test' already exists"
	@echo "✓ Databases ready"

# ─── Cleanup ────────────────────────────────────────────────────────────────────
clean:
	@echo "→ Cleaning build artifacts..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null; true
	@find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null; true
	@find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null; true
	@find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null; true
	@find . -name "*.pyc" -delete 2>/dev/null; true
	@find . -name ".coverage" -delete 2>/dev/null; true
	@echo "✓ Clean complete"
