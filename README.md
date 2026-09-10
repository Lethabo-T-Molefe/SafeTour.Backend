# SafeTour AI Sentinel — Backend

The FastAPI backend for **SafeTour AI Sentinel**, a safety-aware mobility and
daily-decision platform for South Africa. It joins official crime data,
contextual signals and moderated community reports into relative risk
estimates, and uses those to power safety-aware routing, itinerary planning
and a set of everyday safety features (emergency check-ins, companion mode,
community reports).

This repository implements the platform described in `Docs/SafeTour_Consolidated.pdf`
(business case, requirements, architecture, API and database design).

## Architecture

A **modular monolith**: one FastAPI service, one PostgreSQL + PostGIS
database, with each business capability living in its own module under
`src/safetour/modules/`. Every module follows the same shape:

```
modules/<name>/
├── domain.py          # Framework-free entities, repository protocols, exceptions
├── service.py          # Business logic — the only thing with unit tests that need no DB
├── models.py            # SQLAlchemy ORM models + concrete repository implementations
├── schemas.py            # Pydantic request/response models
├── routes.py              # FastAPI router — thin controllers only
├── dependencies.py         # FastAPI DI wiring (service factories)
└── __init__.py               # Public surface: router + any explicit cross-module exports
```

| Module | Responsibility | Key requirements |
|---|---|---|
| `auth` | Registration, login, JWT + refresh tokens, lockout | FR-AUTH-1/2, NFR-SEC-2 |
| `users` | Persona and preferences profile | FR-AUTH-3/4/5 |
| `geo` | Shared spatial reference: precincts, segments, attractions/stops | Section 25 |
| `risk` | Risk scoring, heat map, model registry & promotion gate | FR-RISK-*, MLR-* |
| `routing` | Safety-aware route options (stateless) | FR-ROUTE-*, FR-MODE-* |
| `itineraries` | Itinerary generation, ranking, persistence | FR-ITIN-1/2/3 |
| `assistant` | Conversational planning — contained, provenance-validated | FR-ITIN-5, MLR-6 |
| `reports` | Community reports with verification, weighting and decay | FR-REP-* |
| `emergency` | Trip sharing, check-ins, companion mode, quick help | FR-EMG-* |
| `notifications` | Push subscriptions, alert preferences, alert log | FR-NOT-2 |
| `feedback` | Ratings and comments with rate limiting + content filter | FR-FDBK-1 |
| `admin` | Ingestion, model lifecycle, moderation, audit log, purge job | FR-ADM-* |

`shared/` holds cross-cutting concerns: settings, the async DB session,
argon2id/JWT security helpers, exception handlers, and optional external
clients (weather, power status) that degrade to "omit the signal" on failure.

**A note on scope.** This is the initial repository for the project — the
module boundaries, database schema, API contracts and auth are real and
tested, but `risk`, `routing`, `itineraries` and `assistant` currently use
clearly-marked naive/deterministic placeholder logic in place of the trained
ML model, segment-graph router and content-based recommender, which are
separate, later deliverables per the delivery timeline. Look for the
docstrings marking each extension point (e.g. `risk/service.py`'s
`_naive_fallback`).

## Quick start

```bash
# 1. Copy env and adjust secrets / DB URL
cp .env.example .env

# 2. Install (Python 3.12 via uv)
uv sync

# 3. Run API (AUTO_CREATE_TABLES=true in .env.example creates tables on boot
#    for local dev; use Alembic migrations for anything shared/production)
uv run uvicorn safetour.main:app --reload --host 0.0.0.0 --port 8000
```

- App: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health, readiness (DB ping): http://localhost:8000/api/v1/ready

### Docker

```bash
cp .env.example .env
docker compose up --build
```

This starts the API alongside `postgis/postgis:16-3.4-alpine` and applies
migrations on boot.

### Migrations

The first migration has not been generated yet — do this once against a
running PostGIS instance (`docker compose up -d db` covers that):

```bash
uv run alembic revision --autogenerate -m "initial schema"
uv run alembic upgrade head
```

Subsequent schema changes follow the same two commands.

### Tests / lint / types

```bash
uv run pytest
uv run ruff check .
uv run mypy src
```

`tests/unit/` covers domain and security logic with no database required
(lockout, report decay/weighting, JWT/argon2id, time bands, the ML
promotion quality gate, haversine distance, emergency transience rules).
`tests/integration/` and `tests/e2e/` are scaffolded for work that needs a
live database.

## API surface

Bearer JWT auth is required on every endpoint that reads or changes a
user's own data; `admin/*` additionally requires `is_admin`. See
`/docs` for the full OpenAPI contract. Highlights, matching section 26:

| Method & path | Purpose |
|---|---|
| `POST /api/v1/auth/register`, `/login`, `/refresh`, `/logout` | Account and session lifecycle |
| `GET/PUT /api/v1/users/me`, `/me/preferences`, `/me/export`, `DELETE /me` | Profile and persona, data rights |
| `GET /api/v1/risk`, `/risk/heatmap` | Risk score/band lookup and the heat-map layer |
| `POST /api/v1/routes` | Safety-aware route options |
| `POST /api/v1/itineraries`, `GET /{id}`, `PUT /{id}/save` | Itinerary generation and persistence |
| `POST /api/v1/assistant/plan` | Conversational planning |
| `POST /api/v1/reports`, `/reports/{id}/confirm` | Community reports |
| `POST /api/v1/trips`, `/{id}/share`, `/{id}/checkin`, `/trips/companion` | Emergency features |
| `GET /api/v1/emergency/quick-help` | One-interaction emergency numbers + nearest safe points |
| `POST /api/v1/notifications/subscribe` | Push registration |
| `POST /api/v1/feedback` | Rate a recommendation |
| `POST /api/v1/admin/ingest`, `/retrain`, `/models/{v}/promote` | Data + model lifecycle |

## Stack

- FastAPI + Uvicorn, Pydantic Settings
- SQLAlchemy (async) + asyncpg + GeoAlchemy2/Shapely (PostGIS)
- Alembic
- Argon2id (`argon2-cffi`) + PyJWT
- LangChain-core (contained, optional — see `assistant/service.py`)
- Ruff, MyPy (strict), Pytest
