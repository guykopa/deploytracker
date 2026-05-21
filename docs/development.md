# Development Guide

## Local setup

```bash
cd app

# Create and activate virtualenv
python3.11 -m venv .venv
source .venv/bin/activate

# Install dependencies (using Poetry)
pip install poetry
poetry install

# Configure local environment
cp .env.example .env
# Edit .env: set DATABASE_URL to your local Postgres
```

### `.env` variables

| Variable | Required | Description |
|---|---|---|
| `DEPLOYTRACKER_DATABASE_URL` | Yes | `postgresql+psycopg2://user:pass@localhost:5432/deploytracker` |
| `DEPLOYTRACKER_ENV` | No | `development` (default) |
| `DEPLOYTRACKER_LOG_LEVEL` | No | `INFO` (default) |
| `DEPLOYTRACKER_OTLP_ENDPOINT` | No | `http://localhost:4317` — set if you have a local OTel Collector |
| `DEPLOYTRACKER_JWT_SECRET_KEY` | Yes | 32-byte hex string — generate with `openssl rand -hex 32` |
| `DEPLOYTRACKER_ADMIN_USERNAME` | No | `admin` (default) |
| `DEPLOYTRACKER_ADMIN_PASSWORD` | Yes | Any strong password |

The `.env` file is gitignored. Never commit it.

### Run the API

```bash
cd app
uvicorn deploytracker.api.main:app --reload
```

API available at `http://localhost:8000`. OpenAPI UI at `http://localhost:8000/docs`.

---

## Local PostgreSQL

If you don't have PostgreSQL installed, run it in Docker:

```bash
docker run -d \
  --name deploytracker-pg \
  -e POSTGRES_USER=deploytracker \
  -e POSTGRES_PASSWORD=localpassword \
  -e POSTGRES_DB=deploytracker \
  -p 5432:5432 \
  postgres:16

# Set in .env:
# DEPLOYTRACKER_DATABASE_URL=postgresql+psycopg2://deploytracker:localpassword@localhost:5432/deploytracker
```

The API runs Alembic migrations automatically on startup.

---

## Running tests

```bash
cd app
make test
# Equivalent: poetry run pytest tests/ --cov=deploytracker --cov-report=xml --cov-fail-under=80 -v
```

Tests require a running PostgreSQL instance (integration tests use testcontainers — Docker must be running).

Unit tests are in `tests/unit/` and do not need a database.

```bash
# Unit tests only (no database needed)
poetry run pytest tests/unit/ -v

# Integration tests only (requires Docker)
poetry run pytest tests/integration/ -v
```

---

## Lint and type checking

```bash
make lint       # ruff check src tests
make typecheck  # mypy src/ --strict
```

Both must pass with zero errors before a PR can merge.

---

## TDD workflow

Every feature follows Red → Green → Refactor:

1. **Write the failing test first.** Unit tests go in `tests/unit/`, integration tests in `tests/integration/`.
2. **Write the minimum code to make it pass.** No more, no less.
3. **Refactor** while keeping tests green.

PRs without tests will fail CI.

---

## Adding a new endpoint

Follow the hexagonal architecture layer by layer:

### 1. Domain layer (`app/src/deploytracker/domain/`)

Define or update:
- `models.py` — SQLAlchemy ORM entity
- `schemas.py` — Pydantic request/response schemas
- `repositories.py` — abstract method on the relevant repository interface

### 2. Application layer (`app/src/deploytracker/application/`)

Implement the use case in `deployment_service.py` or a new service file. Call repository interfaces only — never SQLAlchemy directly.

### 3. Infrastructure layer (`app/src/deploytracker/infrastructure/db/repositories/`)

Implement the concrete repository method. This is the only layer that touches SQLAlchemy queries.

### 4. API layer (`app/src/deploytracker/api/routes/`)

Expose the endpoint in the appropriate router. Inject `current_user: str = Depends(get_current_user)` for any protected endpoint.

### 5. Telemetry

Add a metric increment or custom span in the use case (not the route):

```python
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("my_operation") as span:
    span.set_attribute("service.name", service_name)
    result = self._repo.do_something(...)
    return result
```

---

## Adding observability

**Custom span:**
```python
from opentelemetry import trace
tracer = trace.get_tracer(__name__)

with tracer.start_as_current_span("compute_something") as span:
    span.set_attribute("service.target", service_name)
    result = compute(...)
    span.set_attribute("result.count", len(result))
    return result
```

**Custom metric (define once in `infrastructure/telemetry/metrics.py`):**
```python
from deploytracker.infrastructure.telemetry.metrics import deployments_counter
deployments_counter.add(1, attributes={"service": dto.service_name, "status": "success"})
```

**Structured log:**
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Deployment recorded", extra={"service_name": dto.service_name, "version": dto.version})
```

!!! important
    Never export metrics or logs directly to Prometheus, Loki, or any backend. Always use OTLP (→ OTel Collector → backends).

---

## Docker build

```bash
# Build locally
make docker-build

# Build and push to ECR (requires AWS credentials + running cluster)
make docker-push
```

The Dockerfile uses a multi-stage build:
1. `builder` stage — installs Poetry + dependencies
2. `runtime` stage — copies only the installed packages + source, no Poetry

---

## Helm chart modifications

When modifying `charts/deploytracker` or `charts/observability`:

1. Bump the `version` in `Chart.yaml`.
2. Run `helm lint charts/<chart>` — must pass with no errors.
3. Run `helm template charts/<chart>` to inspect the rendered manifests.
4. Keep all configurable values in `values.yaml` with inline comments.

---

## Definition of Done

A feature is done when:

1. All tests pass: `make test` with coverage ≥ 80% on changed code.
2. `make lint` and `make typecheck` pass with zero errors.
3. Relevant ADR written if the change involves an architectural decision.
4. README or docs updated if the change is user-facing.
5. `CLAUDE.md` updated if the development workflow changed.
6. Helm chart version bumped if the chart changed.
7. CI pipeline is green on the PR.
8. Manual verification on the live cluster: deploy, hit the endpoint, observe in Grafana.
