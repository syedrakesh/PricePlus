# PricePlus — Production SaaS Implementation Plan

## Overview

PricePlus is a SaaS product for dropshippers who need to monitor competitor Shopify stores for price changes. Users add a competitor URL, the system discovers its products, the user selects which products to track, and the system periodically polls those products, detects price changes, stores history, and sends email alerts — all managed through a Stripe subscription.

---

## A. Current Repository Assessment

| Dimension | Status |
|---|---|
| Repository | **Empty directory** at `/home/rakesh/Desktop/D4rk_H4x0r/Desktop/Projects/PricePlus` |
| Git | Initialized (`.git` dir exists), no commits, no remote |
| Git identity | `syedrakesh` / `syedrakesh.me@gmail.com` |
| Framework | **None** — greenfield project |
| Database | PostgreSQL 16 installed, **not running** |
| Redis | Installed, **not running** |
| Docker | **Not available** / not running |
| Node.js | **v26.4.0**, npm 11.17.0 |
| Python | **3.12.3** |
| Python web frameworks | **None installed** (Django, FastAPI, Flask — all absent) |
| Python async libs | None (no celery, redis-py, sqlalchemy, alembic, stripe, psycopg2, asyncpg) |
| Playwright | Installed (useful for fallback scraping later) |
| BeautifulSoup4 | Installed (useful for HTML parsing) |
| requests | Installed (2.31.0) |
| PyJWT | Installed (2.7.0) |
| CI/CD | None |
| Tests | None |
| Linting | None configured |
| Documentation | None |
| GitHub remote | Not configured |

**Conclusion:** Completely greenfield. No code to reuse, no constraints from existing architecture. Full design freedom.

---

## B. Proposed Architecture

### Philosophy: Modular Monolith

A well-structured **modular monolith** is the correct choice for MVP. It is:
- Operationally simple (one process to deploy initially)
- Testable and maintainable
- Extensible (domains can become services later)
- Appropriate for early user numbers

**Not** microservices — that would be premature and costly.

### Tech Stack Decision

| Layer | Technology | Rationale |
|---|---|---|
| Backend framework | **FastAPI** (Python) | Async-native, modern, excellent DX, auto-docs, type-safe |
| Task queue | **Celery + Redis** | Industry-standard, battle-tested, supports scheduling |
| Database ORM | **SQLAlchemy 2.x** (async) | Best Python ORM, async support, Alembic migrations |
| Migrations | **Alembic** | Standard SQLAlchemy migration tool |
| Database | **PostgreSQL 16** | Relational, reliable, full-featured |
| Cache / Broker | **Redis** | Celery broker + result backend + rate limiting |
| Auth | **FastAPI-Users** or custom JWT | JWT-based, cookie or bearer |
| Email | **SMTP** via `smtplib` / `aiosmtplib` + templates | Simple, no external dependency for MVP |
| Stripe | **stripe-python SDK** | Official SDK |
| HTTP client | **httpx** (async) | Async HTTP, used in discovery engine |
| Frontend | **Next.js 14 (App Router)** | Modern React, SSR, excellent DX |
| Frontend styles | **Vanilla CSS modules** | Per spec |
| Validation | **Pydantic v2** | Ships with FastAPI |
| Testing | **pytest + pytest-asyncio + httpx** | Standard async Python testing |
| Linting | **ruff** | Fast Python linter |
| Type checking | **mypy** | Static analysis |
| Frontend testing | **Jest + React Testing Library** | Standard |

### System Architecture Diagram

```
┌─────────────────────────────────────────────────────┐
│                    Next.js Frontend                  │
│              (Dashboard, Onboarding, UI)             │
└─────────────────┬───────────────────────────────────┘
                  │ HTTPS / REST
┌─────────────────▼───────────────────────────────────┐
│                  FastAPI Backend                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐  │
│  │   Auth   │ │  Stores  │ │Discovery │ │Billing │  │
│  │  Module  │ │  Module  │ │  Module  │ │ Module │  │
│  └──────────┘ └──────────┘ └──────────┘ └────────┘  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐             │
│  │Monitoring│ │ Alerts   │ │Entitlement│            │
│  │  Module  │ │  Module  │ │  Module  │             │
│  └──────────┘ └──────────┘ └──────────┘             │
└─────────────────┬───────────────────────────────────┘
                  │
        ┌─────────┴──────────┐
        │                    │
┌───────▼──────┐   ┌─────────▼──────┐
│  PostgreSQL  │   │     Redis       │
│  (Primary    │   │  (Broker +      │
│   Database)  │   │   Rate Limit +  │
│              │   │   Cache)        │
└──────────────┘   └─────────┬──────┘
                             │
                   ┌─────────▼──────┐
                   │  Celery Workers │
                   │  ┌───────────┐ │
                   │  │Discovery  │ │
                   │  │  Worker   │ │
                   │  ├───────────┤ │
                   │  │Monitoring │ │
                   │  │  Worker   │ │
                   │  ├───────────┤ │
                   │  │Notification│ │
                   │  │  Worker   │ │
                   │  └───────────┘ │
                   └────────────────┘
```

### Module Boundaries

```
backend/
  app/
    core/          # config, db, security, dependencies
    modules/
      auth/        # user registration, login, JWT
      stores/      # competitor store management
      discovery/   # product discovery engine
      tracking/    # tracked product management
      monitoring/  # polling engine, snapshots, diffs
      alerts/      # notification dispatch
      billing/     # Stripe integration, entitlements
    workers/       # Celery task definitions
    scheduler/     # Celery beat schedules
```

---

## C. MVP Roadmap

```
Phase 0  — Engineering Foundation          (current)
Phase 1  — Authentication & User System
Phase 2  — Competitor Store Management
Phase 3  — Product Discovery Engine
Phase 4  — Product Selection & Tracking
Phase 5  — Monitoring Engine
Phase 6  — Price History & Diffing
Phase 7  — Email Alerts
Phase 8  — Stripe Billing & Entitlements
Phase 9  — Frontend (Dashboard & Flows)
Phase 10 — Production Hardening & Release
```

---

## D. Phase Breakdown

### Phase 0 — Engineering Foundation
**Objective:** Working dev environment, database running, migrations system, testing framework, linting, base project structure, initial commit.

Tasks:
- [ ] Start PostgreSQL and Redis (or provide setup script)
- [ ] Create virtualenv, install core dependencies
- [ ] Create repository structure (backend + frontend)
- [ ] FastAPI app skeleton (`main.py`, `core/config.py`, `core/db.py`)
- [ ] Alembic initialized, empty migration baseline
- [ ] `.env.example`, `.gitignore`, `README.md`
- [ ] pytest configured with one passing smoke test
- [ ] ruff configured
- [ ] mypy baseline config
- [ ] Makefile with dev commands
- [ ] Initial git commit
- [ ] GitHub remote setup + push

### Phase 1 — Authentication
- User model (id, email, hashed_password, is_active, created_at)
- Registration endpoint
- Login endpoint (JWT access + refresh tokens)
- Get current user endpoint
- Password hashing (bcrypt)
- Auth middleware / dependency
- Unit tests for auth logic
- Integration tests for auth endpoints

### Phase 2 — Competitor Store Management
- CompetitorStore model
- Add store endpoint (validate URL, SSRF protection)
- List/delete stores
- Store ownership enforcement
- Entitlement check (max_stores from plan)
- Tests

### Phase 3 — Product Discovery Engine
- Discovery orchestrator
- Shopify platform detector
- `/products.json` discovery strategy (paginated)
- Sitemap discovery strategy
- URL normalizer + deduplicator
- DiscoveredProduct model
- Async discovery via Celery task
- Discovery status polling endpoint
- Tests (including failure modes)

### Phase 4 — Product Selection & Tracking
- TrackedProduct model
- Select products endpoint
- Track all endpoint
- Entitlement check (max_tracked_products)
- Untrack product
- Tests

### Phase 5 — Monitoring Engine
- ProductSnapshot model
- PriceChange model
- Celery beat schedule (per-plan poll intervals)
- Monitoring task (fetch → parse → diff → store)
- Idempotency (no duplicate snapshots/alerts)
- Retry with exponential backoff
- Rate limiting per competitor store
- Tests (including duplicate job protection)

### Phase 6 — Price History & Diffing
- Price diff calculator
- Timeline endpoint for a tracked product
- Store all snapshots (never overwrite)
- Tests

### Phase 7 — Email Alerts
- Email service (async, SMTP)
- Alert model
- Notification worker
- Email template (price change details)
- Tests with mock SMTP

### Phase 8 — Stripe Billing
- Plan model + seeding
- Entitlement system (centralized)
- Stripe customer creation
- Stripe checkout session
- Stripe webhook handler (idempotent)
- Subscription model
- Tests with Stripe test mode

### Phase 9 — Frontend
- Next.js setup
- Auth pages (login, register)
- Dashboard
- Add competitor store flow
- Product discovery + selection UI
- Tracked products management
- Price history view
- Subscription / billing page

### Phase 10 — Production Hardening
- Rate limiting (API + discovery)
- Security headers
- CORS configuration
- Production logging
- Health check endpoints
- Error tracking
- Load testing baseline
- Deployment guide

---

## E. Database / Domain Design

### Core Models (MVP)

```sql
-- Users
users
  id            UUID PRIMARY KEY
  email         VARCHAR UNIQUE NOT NULL
  password_hash VARCHAR NOT NULL
  is_active     BOOLEAN DEFAULT TRUE
  created_at    TIMESTAMPTZ DEFAULT NOW()

-- Plans (seeded, not user-created)
plans
  id                   UUID PRIMARY KEY
  name                 VARCHAR UNIQUE  -- 'free', 'starter', 'pro'
  stripe_price_id      VARCHAR
  max_stores           INTEGER
  max_tracked_products INTEGER
  poll_interval_mins   INTEGER         -- minimum poll interval
  is_active            BOOLEAN DEFAULT TRUE

-- Subscriptions
subscriptions
  id                UUID PRIMARY KEY
  user_id           UUID FK users
  plan_id           UUID FK plans
  stripe_customer_id VARCHAR
  stripe_sub_id     VARCHAR UNIQUE
  status            VARCHAR           -- 'active','canceled','past_due'
  current_period_end TIMESTAMPTZ
  created_at        TIMESTAMPTZ DEFAULT NOW()
  updated_at        TIMESTAMPTZ DEFAULT NOW()

-- Competitor Stores
competitor_stores
  id           UUID PRIMARY KEY
  user_id      UUID FK users
  url          VARCHAR NOT NULL       -- normalized store URL
  display_name VARCHAR
  platform     VARCHAR DEFAULT 'shopify'
  status       VARCHAR DEFAULT 'active'  -- 'active','error','paused'
  last_error   TEXT
  created_at   TIMESTAMPTZ DEFAULT NOW()
  UNIQUE (user_id, url)

-- Discovered Products
discovered_products
  id               UUID PRIMARY KEY
  store_id         UUID FK competitor_stores
  external_id      VARCHAR            -- Shopify product ID
  handle           VARCHAR            -- Shopify handle (URL slug)
  title            VARCHAR
  product_url      VARCHAR
  image_url        VARCHAR
  current_price    NUMERIC(12,4)      -- latest known price
  currency         VARCHAR DEFAULT 'USD'
  is_available     BOOLEAN DEFAULT TRUE
  discovered_at    TIMESTAMPTZ DEFAULT NOW()
  last_seen_at     TIMESTAMPTZ DEFAULT NOW()
  UNIQUE (store_id, external_id)

-- Tracked Products
tracked_products
  id                    UUID PRIMARY KEY
  user_id               UUID FK users
  discovered_product_id UUID FK discovered_products
  is_active             BOOLEAN DEFAULT TRUE
  created_at            TIMESTAMPTZ DEFAULT NOW()
  UNIQUE (user_id, discovered_product_id)

-- Product Snapshots (price history — never deleted)
product_snapshots
  id                 UUID PRIMARY KEY
  tracked_product_id UUID FK tracked_products
  price              NUMERIC(12,4)
  currency           VARCHAR DEFAULT 'USD'
  is_available       BOOLEAN
  raw_data           JSONB             -- full product JSON for future use
  snapshotted_at     TIMESTAMPTZ DEFAULT NOW()

-- Price Changes
price_changes
  id                 UUID PRIMARY KEY
  tracked_product_id UUID FK tracked_products
  old_price          NUMERIC(12,4)
  new_price          NUMERIC(12,4)
  change_amount      NUMERIC(12,4)     -- computed: new - old
  change_percent     NUMERIC(8,4)      -- computed
  detected_at        TIMESTAMPTZ DEFAULT NOW()

-- Alerts
alerts
  id              UUID PRIMARY KEY
  user_id         UUID FK users
  price_change_id UUID FK price_changes
  channel         VARCHAR DEFAULT 'email'
  status          VARCHAR DEFAULT 'pending'  -- 'pending','sent','failed'
  sent_at         TIMESTAMPTZ
  error_message   TEXT
  created_at      TIMESTAMPTZ DEFAULT NOW()
```

### Key Indexes

```sql
-- Fast lookup of user's stores
CREATE INDEX idx_competitor_stores_user_id ON competitor_stores(user_id);

-- Fast lookup of store's products
CREATE INDEX idx_discovered_products_store_id ON discovered_products(store_id);

-- Fast lookup of user's tracked products
CREATE INDEX idx_tracked_products_user_id ON tracked_products(user_id);
CREATE INDEX idx_tracked_products_active ON tracked_products(user_id) WHERE is_active = TRUE;

-- Fast snapshot lookup (latest per product)
CREATE INDEX idx_snapshots_tracked_product ON product_snapshots(tracked_product_id, snapshotted_at DESC);

-- Price changes per product
CREATE INDEX idx_price_changes_tracked_product ON price_changes(tracked_product_id, detected_at DESC);

-- Pending alerts
CREATE INDEX idx_alerts_status ON alerts(status) WHERE status = 'pending';

-- Active subscriptions
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_stripe_sub ON subscriptions(stripe_sub_id);
```

---

## F. Agent/Team Responsibility Model

| Role | Responsibilities in this project |
|---|---|
| **Product Manager** | Scope enforcement, acceptance criteria, prevent Phase 2 creep |
| **Principal Architect** | Modular boundaries, DB design, queue design, API contracts |
| **Backend Engineer** | FastAPI endpoints, services, business logic, DB queries |
| **Data/Scraping Engineer** | Discovery engine, HTTP client, Shopify parser, URL normalizer |
| **Frontend Engineer** | Next.js dashboard, all UI flows, CSS modules |
| **QA Engineer** | pytest suites, edge case coverage, integration tests |
| **Security Engineer** | SSRF protection, auth, tenant isolation, input validation |
| **DevOps/SRE** | Makefile, env setup, start scripts, service management |
| **Code Reviewer** | Per-chunk review before commit |

---

## G. Testing Strategy

### Backend
- **Unit tests** — `pytest` for parsers, URL normalizer, price diff, entitlement calc
- **Integration tests** — `pytest-asyncio` + `httpx.AsyncClient` against real DB (test DB)
- **Fixtures** — Factory functions, not hardcoded data
- **Mocks** — HTTP calls mocked via `respx` or `unittest.mock`
- **Coverage** — `pytest-cov`, target ≥80% for core business logic

### Frontend
- **Unit tests** — Jest + React Testing Library for components
- **No E2E for MVP** — Manual verification of critical flows

### CI
- GitHub Actions (once remote configured)
- On every push: `ruff check`, `mypy`, `pytest`

---

## H. Git/GitHub Strategy

### Branching (solo project simplification)
- `main` — always deployable
- Feature branches optional but commits must be atomic

### Commit cadence
- After every validated, working chunk
- Conventional commits format: `feat:`, `fix:`, `test:`, `docs:`, `chore:`

### Remote
- GitHub remote to be configured once foundation is ready
- Push after each phase milestone

---

## I. Risks & Technical Unknowns

| Risk | Mitigation |
|---|---|
| PostgreSQL / Redis not running | Setup script / Makefile target to start services |
| No Docker available | Run services natively; provide docker-compose for future use |
| Shopify stores vary wildly | Multi-strategy discovery with graceful fallbacks |
| SSRF via user-provided URLs | Strict URL validation + IP blocklist check before any HTTP request |
| Celery beat duplicate jobs | Idempotency keys on monitoring tasks |
| Email delivery failures | Async queue, retry logic, alert status tracking |
| Stripe webhook replay | Idempotency keys via Stripe event ID |
| Large product catalogs (5000+) | Paginated discovery, streaming writes |
| Rate limiting by Shopify stores | Per-store request throttling, respect `Retry-After` |
| No `gh` CLI installed | Use `git push` directly; `gh` CLI optional for PR management |

---

## J. First Implementation Chunk (Phase 0, Task 1)

**Goal:** Create the project skeleton, install dependencies, verify the stack runs.

**Scope:**
1. `backend/` directory with virtualenv + `requirements.txt`
2. `backend/app/main.py` — FastAPI app with health check
3. `backend/app/core/config.py` — Pydantic settings
4. `backend/app/core/db.py` — Async SQLAlchemy engine
5. `alembic.ini` + `backend/alembic/` — migration scaffolding
6. `.env.example`
7. `.gitignore`
8. `Makefile` with: `install`, `dev`, `test`, `lint`, `migrate`, `db-start`, `redis-start`
9. `pytest.ini` / `pyproject.toml`
10. One smoke test that hits the health check
11. `ruff.toml` / `pyproject.toml` linting config
12. `README.md` skeleton
13. `git init`, first commit, push

**Acceptance criteria:**
- `make install` succeeds
- `make dev` starts the FastAPI server
- `GET /health` returns `{"status": "ok"}`
- `make test` runs and passes
- `make lint` passes with no errors
- Alembic can run `alembic revision --autogenerate`
- All committed and pushed

---

## Open Questions for User

> [!IMPORTANT]
> **PostgreSQL and Redis:** They are installed but not running. I will write a `Makefile` target to start them (requires sudo or configured systemd). Do you have a preferred way to manage these services, or should I include instructions to start them manually?

> [!IMPORTANT]
> **GitHub Remote:** No remote is configured. Once Phase 0 is complete, do you want me to create a new GitHub repository? If so, please confirm the desired repo name (e.g., `priceplus`) and whether it should be public or private. I can provide the `git remote add` command for you to run.

> [!IMPORTANT]
> **Email Provider:** For MVP email alerts, do you have an SMTP provider preference (Gmail SMTP, SendGrid SMTP relay, Mailgun, Resend, Postmark)? For now I'll default to generic SMTP (configurable via `.env`) so you can plug in any provider.

> [!IMPORTANT]
> **Stripe Account:** Do you have a Stripe account with test API keys ready? Stripe integration is Phase 8 — not needed now — but good to know early.

> [!NOTE]
> **Frontend Tech:** The spec says vanilla CSS. However given the scope of UI (dashboard, onboarding flows, product selection tables), I recommend **CSS Modules** with Next.js (still vanilla CSS, just scoped). This is consistent with the spec's intent. I'll proceed with this unless you object.
