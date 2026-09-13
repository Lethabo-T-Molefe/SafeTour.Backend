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

**A note on scope.** `risk` scores from a trained, calibrated model once one
has been promoted (`scripts/train_and_score_risk_model.py`); `routing` plans
over a real Dijkstra segment graph (`routing/graph.py`); `itineraries` ranks
with a TF-IDF content-based recommender + safety re-rank
(`itineraries/recommender.py`); `assistant` calls a real, contained LLM
(`ChatAnthropic`) when `LLM_API_KEY` is set. Every one of these has a
documented, tested deterministic fallback (NFR-REL-2) for when there is no
promoted model yet, no connected segment graph for a given mode, or no LLM
key configured — none of it is a hard dependency to boot the API.

**Known gap.** FR-LOC-3's message/USSD fallback for feature phones is not
built — it is a Should-priority requirement that needs a paid third-party
telecom gateway (e.g. Africa's Talking) account and credentials this
repository does not have. `notifications/service.py`'s alert log is the
closest existing analogue (an always-available, no-external-dependency
channel); wiring a real USSD/SMS gateway is a follow-on integration, not a
code change that can be faked without a real account to test against.

## Batch jobs (out-of-band, per 24.1)

These run directly against the database — no API server needs to be
running — matching "Model training: Google Colab or Kaggle notebooks" and
"out-of-band batch jobs for ingestion and the machine-learning lifecycle":

```bash
# 1. Seed a small demo dataset for the Tshwane pilot area (synthetic — see
#    the script's docstring). Creates an admin login too.
uv run python scripts/seed_data.py

# 2. Train, evaluate, bias-audit, score and (if it clears the MLR-2 quality
#    gate) promote a risk model from whatever crime_statistics exist.
uv run python scripts/train_and_score_risk_model.py

# 3. Ingest a real SAPS-derived quarterly CSV later (FR-ADM-1) — validated
#    and idempotent; see the script's docstring for the expected columns.
uv run python scripts/ingest_saps_csv.py data/2025q4.csv --period 2025Q4
```

Re-running `train_and_score_risk_model.py` after ingesting a new quarter
re-trains on the (now time-shifted) split and re-scores — the promotion
gate is the same one `/admin/models/{v}/promote` enforces, so a run that
does not clear ROC-AUC ≥ 0.80 / PR-AUC > base rate is reported plainly and
promotes nothing, exactly like the HTTP path would.

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

The initial schema migration (`alembic/versions/ce8089693f45_initial_schema.py`,
all 25 tables) is committed and has been applied to a native local
PostgreSQL 18 + PostGIS 3.6.2 install — no Docker required for this. Against
a fresh database:

```bash
uv run alembic upgrade head
```

Subsequent schema changes: `uv run alembic revision --autogenerate -m "..."`
then `uv run alembic upgrade head`. `env.py` wires GeoAlchemy2's
`render_item`/`include_object` helpers into both migration contexts, so
autogenerate handles `Geometry` columns correctly and won't try to touch
PostGIS's own `spatial_ref_sys` table.

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
- scikit-learn, pandas, NumPy — risk model training + content-based recommender
- LangChain + `langchain-anthropic` (contained, optional — see `assistant/service.py`)
- Ruff, MyPy (strict), Pytest
