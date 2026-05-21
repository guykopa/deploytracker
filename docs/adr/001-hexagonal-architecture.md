# ADR-001: Hexagonal Architecture (Ports & Adapters)

**Date:** 2026-05-21
**Status:** Accepted

## Context

The deploytracker application tracks deployment events and computes DORA metrics
(Deployment Frequency, Lead Time for Changes, Change Failure Rate, Time to Restore).
The core logic — event ingestion, metric computation, aggregation windows — must be
exercised in unit tests without spinning up a real database or HTTP server.

A naive approach (direct SQLAlchemy calls inside route handlers) would make it
impossible to test the domain logic in isolation and would tightly couple the
business rules to a specific persistence technology.

## Decision

Adopt **Hexagonal Architecture** (also known as Ports & Adapters, coined by Alistair
Cockburn).

The codebase is organised into three concentric layers:

```
src/deploytracker/
├── domain/          # Pure business logic — no I/O, no frameworks
│   ├── models.py    # Entities & value objects (dataclasses / Pydantic)
│   ├── ports.py     # Abstract repository interfaces (Protocols)
│   └── services.py  # Use-case orchestrators
├── adapters/        # Concrete implementations of ports
│   ├── persistence/ # SQLAlchemy repository implementations
│   └── http/        # FastAPI routers (inbound adapter)
└── infrastructure/  # Wiring: DI container, config, app factory
```

**Ports** are Python `Protocol` (or ABC) classes defined in `domain/ports.py`.
They express *what* the domain needs (e.g. `DeploymentRepository.save()`), not *how*
it is done.

**Adapters** implement those ports. Tests inject in-memory adapters; production
injects SQLAlchemy adapters.

## Alternatives Considered

### Layered Architecture (N-tier)
Classic `presentation → service → repository` separation. Simpler to understand and
widely adopted. Rejected because service classes typically import concrete repository
classes, making it hard to swap the persistence layer without modifying service code.
Unit tests still require a running database or complex mocking.

### Clean Architecture (Uncle Bob)
Similar goals, but prescribes additional entity/use-case/interface-adapter/framework
rings with stricter dependency inversion at every boundary. Rejected as over-engineered
for a single-service application; the additional abstractions (Use Case classes,
DTOs at every boundary) would add significant boilerplate without proportional benefit
at this scale.

## Consequences

### Positive
- Domain logic is testable in complete isolation with plain `pytest` — no DB, no HTTP
  stack required.
- Adapters are interchangeable: switching from SQLite (CI) to PostgreSQL (production)
  requires only a different adapter instantiation; the domain code is untouched.
- The domain layer has zero external dependencies, which keeps it fast to import and
  easy to reason about.
- Encourages thinking in terms of business invariants rather than database schemas.

### Negative
- More boilerplate than a simple CRUD approach: every persistence operation requires a
  port interface, a concrete adapter, and wiring in the DI container.
- Steeper learning curve for contributors unfamiliar with the pattern; requires a brief
  orientation before making changes.
- Risk of "ports proliferation" if every small helper is wrapped in a protocol — the
  team must exercise discipline to keep the abstraction meaningful.

## References

- Alistair Cockburn, *Hexagonal Architecture* (2005) — <https://alistair.cockburn.us/hexagonal-architecture/>
- Martin Fowler, *Patterns of Enterprise Application Architecture* (2002), Chapter 9
- FastAPI dependency injection documentation — <https://fastapi.tiangolo.com/tutorial/dependencies/>
