# PricePlus

> Shopify competitor price monitoring SaaS — discover products, track prices, get alerted when they change.

## Status: Phase 0 — Engineering Foundation ✅

---

## Quick Start

### 1. Prerequisites

| Requirement | Version |
|---|---|
| Python | ≥ 3.12 |
| Node.js | ≥ 18 |
| PostgreSQL | 16 |
| Redis | 7+ |

### 2. Start Services

```bash
# PostgreSQL
sudo systemctl start postgresql

# Redis
sudo systemctl start redis-server
```

### 3. Install dependencies

```bash
make install
```

### 4. Set up databases

```bash
# One-time: creates the priceplus user and both databases
make setup-db
```

### 5. Configure environment

```bash
cp .env.example backend/.env
# Edit backend/.env if needed (defaults work for local dev)
```

### 6. Run migrations

```bash
make migrate
```

### 7. Start the backend

```bash
make dev
# API running at http://localhost:8000
# Docs at http://localhost:8000/docs (dev only)
```

### 8. Verify

```bash
curl http://localhost:8000/health
# {"status":"ok","service":"priceplus-api","version":"0.1.0"}
```

---

## Development Commands

```bash
make help          # Show all available commands
make test          # Run all tests
make test-cov      # Tests with coverage report
make lint          # Ruff linter
make lint-fix      # Ruff with auto-fix
make type-check    # mypy static analysis

make migrate                        # Apply all pending migrations
make migrate-create m="description" # Create new migration
make migrate-downgrade              # Rollback one migration
```

---

## Project Structure

```
PricePlus/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API versioned routers
│   │   ├── core/            # config, db, logging, security
│   │   ├── modules/         # domain modules
│   │   │   ├── auth/        # Phase 1
│   │   │   ├── stores/      # Phase 2
│   │   │   ├── discovery/   # Phase 3
│   │   │   ├── tracking/    # Phase 4
│   │   │   ├── monitoring/  # Phase 5
│   │   │   ├── alerts/      # Phase 7
│   │   │   └── billing/     # Phase 8
│   │   ├── workers/         # Celery task definitions
│   │   └── scheduler/       # Celery beat schedules
│   ├── alembic/             # Database migrations
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── pyproject.toml       # ruff + mypy + pytest config
├── frontend/                # Next.js (Phase 9)
├── docs/                    # Architecture docs
├── Makefile
├── .env.example
└── .gitignore
```

---

## Architecture

**Modular monolith** — FastAPI + Celery + Redis + PostgreSQL + Next.js.

See [docs/architecture.md](docs/architecture.md) for full design documentation.

---

## Development Phases

| Phase | Description | Status |
|---|---|---|
| 0 | Engineering Foundation | ✅ Complete |
| 1 | Authentication & Users | 🔲 Next |
| 2 | Competitor Store Management | 🔲 |
| 3 | Product Discovery (Sitemap-First) | 🔲 |
| 4 | Product Selection & Tracking | 🔲 |
| 5 | Monitoring Engine | 🔲 |
| 6 | Price History & Diffing | 🔲 |
| 7 | Email Alerts | 🔲 |
| 8 | Stripe Billing | 🔲 |
| 9 | Frontend Dashboard | 🔲 |
| 10 | Production Hardening | 🔲 |

---

## Testing

```bash
# All tests (no DB required for smoke tests)
make test

# With coverage
make test-cov
```

Tests use `pytest-asyncio` in auto mode. Integration tests require running PostgreSQL and Redis.

---

## Security Notes

- User-provided competitor URLs are treated as **untrusted input**
- SSRF protection is built into the discovery engine (Phase 3)
- Never commit `.env` — only `.env.example` is tracked
- JWT secrets must be changed before any deployment
