# Architecture — PricePlus

## System Overview

PricePlus is a **modular monolith** SaaS application that allows dropshippers to monitor competitor Shopify stores for price changes.

### Design philosophy

- **Modular monolith first** — single deployable unit, clear domain boundaries
- **Extract to services only when there is a demonstrated, concrete need**
- **Async-native** — FastAPI async endpoints + Celery workers + asyncpg
- **Queue-based side effects** — email, monitoring jobs, discovery runs all go through the queue
- **Never block HTTP requests** with expensive operations (discovery, polling, email)

---

## Component Architecture

```
┌──────────────────────────────────────────────────┐
│              Next.js Frontend (Phase 9)           │
│        Dashboard / Onboarding / Billing UI        │
└────────────────────┬─────────────────────────────┘
                     │ REST (JSON) over HTTPS
┌────────────────────▼─────────────────────────────┐
│                FastAPI Backend                    │
│                                                   │
│  /api/v1/auth         — JWT auth endpoints        │
│  /api/v1/stores       — competitor stores         │
│  /api/v1/discovery    — discovery trigger/status  │
│  /api/v1/tracking     — tracked products          │
│  /api/v1/monitoring   — snapshots, price history  │
│  /api/v1/alerts       — notification history      │
│  /api/v1/billing      — Stripe checkout/portal    │
│                                                   │
│  /health              — no-dependency health check│
└────────────┬────────────────────────┬────────────┘
             │                        │
    ┌────────▼───────┐      ┌─────────▼──────────┐
    │  PostgreSQL 16  │      │   Redis             │
    │                │      │   ├─ DB 0: broker    │
    │  users         │      │   ├─ DB 1: results   │
    │  plans         │      │   └─ DB 15: test     │
    │  subscriptions │      └─────────┬────────────┘
    │  competitor_   │               │
    │    stores      │      ┌─────────▼──────────┐
    │  discovery_    │      │  Celery Workers     │
    │    runs        │      │                     │
    │  discovered_   │      │  discovery_worker   │
    │    products    │      │  monitoring_worker  │
    │  tracked_      │      │  notification_worker│
    │    products    │      │                     │
    │  product_      │      │  + Celery Beat      │
    │    snapshots   │      │  (scheduler)        │
    │  price_changes │      └────────────────────┘
    │  alerts        │
    └────────────────┘
```

---

## Module Boundaries

### `app/core/`
Cross-cutting concerns. No domain logic.
- `config.py` — Pydantic Settings, env-driven
- `db.py` — async SQLAlchemy engine, session factory, Base
- `logging.py` — structured logging configuration
- `security.py` — JWT creation/validation, password hashing (Phase 1)
- `dependencies.py` — shared FastAPI dependencies (Phase 1)

### `app/modules/auth/`
User registration, login, JWT tokens. No business domain logic.

### `app/modules/stores/`
Competitor store management. SSRF-protected URL validation. Entitlement checks.

### `app/modules/discovery/`
**Sitemap-first product discovery engine.**
- Orchestrator coordinates the full discovery pipeline
- Sitemap fetcher handles `sitemapindex` and `urlset`
- Product URL validator enforces `/products/{handle}` pattern
- URL normalizer ensures canonical, deduplicated URLs
- `ProductDataExtractor` fetches `/products/{handle}.json` (separate from discovery)
- All discovery runs tracked in `discovery_runs` table

### `app/modules/tracking/`
Tracked product management. Entitlement enforcement (max_tracked_products).

### `app/modules/monitoring/`
Price polling engine. Snapshots, diffs, price change detection. Idempotent.

### `app/modules/alerts/`
Email notification dispatch. Async via Celery. Future channels plug in here.

### `app/modules/billing/`
Stripe integration. Plans, subscriptions, entitlements. Webhook handler.

### `app/workers/`
Celery task definitions (thin — delegates to module services).

### `app/scheduler/`
Celery beat schedule configuration.

---

## Discovery Architecture (Sitemap-First)

```
User: Add competitor store URL
         ↓
URL Validation + SSRF Check
         ↓
Shopify Platform Detection
         ↓
DiscoveryRun created (status=pending)
         ↓  [Celery Task]
Fetch /sitemap.xml
         ↓
Parse root sitemap
  ├─ <sitemapindex> → extract <sitemap><loc> entries
  └─ <urlset>       → treat as single product sitemap
         ↓
Identify product sitemaps
  (match: sitemap_products_*.xml — with query params intact)
  (ignore: pages, collections, blogs)
         ↓
Per product sitemap [parallel Celery sub-tasks]:
  Fetch sitemap XML
       ↓
  Parse <url> entries
       ↓
  Extract <loc>, <lastmod>, <image:image>
       ↓
  Validate: must match /products/{handle}
       ↓
  Normalize URL
       ↓
  Upsert to discovered_products
         ↓
Update DiscoveryRun progress counters
         ↓
DiscoveryRun status = completed | partial | failed
         ↓
ProductDataExtractor [separate]:
  Fetch /products/{handle}.json per product
       ↓
  Extract title, price, currency, availability
       ↓
  Fallback: HTML parse if .json unavailable
       ↓
  Update discovered_products record
```

**Important distinctions:**
- `/products.json` — NOT used for catalog discovery
- `/products/{handle}.json` — used only for individual product data, after URL is discovered via sitemap
- A failure in one product sitemap does not abort the entire discovery run

---

## Monitoring Architecture

```
Celery Beat Scheduler
  (per-plan poll intervals: free=60min, starter=30min, pro=15min)
         ↓
Create monitoring task per active tracked_product
  (idempotency: skip if already queued or running)
         ↓
Monitoring Worker:
  Fetch /products/{handle}.json
       ↓
  Parse current price + availability
       ↓
  Compare with latest ProductSnapshot
       ↓
  If changed:
    Create ProductSnapshot (new state)
    Create PriceChange record
    Queue Alert notification
  If unchanged:
    Create ProductSnapshot (same state)
    No alert
         ↓
Notification Worker:
  Send email (async SMTP)
  Update Alert status
```

**Idempotency:** Price changes are keyed on `(tracked_product_id, old_price, new_price, detected_at::date)` to prevent duplicate alerts from duplicate jobs.

---

## Data Architecture

See [database.md](database.md) for full schema.

Key principles:
- All primary keys are UUIDs
- All timestamps are `TIMESTAMPTZ` (timezone-aware)
- Price snapshots are **never deleted or overwritten** — always append
- Subscription limits are read from `plans` table — never hard-coded

---

## Security Architecture

### SSRF Protection
User-provided competitor URLs are validated:
1. URL must have scheme `https://` or `http://`
2. Hostname must resolve to a public IP
3. Resolved IP must not be in private/loopback/link-local ranges
4. No redirects to internal addresses permitted

### Authentication
- JWT-based (access + refresh tokens)
- Passwords hashed with bcrypt
- Tokens stored in httpOnly cookies (no localStorage)

### Tenant Isolation
- Every query is scoped to `user_id`
- No cross-user data access possible through API
- DB-level: no row-level security (RLS) for MVP, enforced at service layer

### Stripe Webhooks
- Signature verified on every webhook event
- Events are idempotent (Stripe event ID used as idempotency key)

---

## ADR Index

| ID | Title | Status |
|---|---|---|
| ADR-001 | Modular monolith over microservices | Accepted |
| ADR-002 | FastAPI over Django/Flask | Accepted |
| ADR-003 | Sitemap-first discovery (no /products.json catalog) | Accepted |
| ADR-004 | Celery + Redis for async work | Accepted |
| ADR-005 | UUID primary keys | Accepted |
