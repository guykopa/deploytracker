# Architecture Decision Records

This directory captures the architectural decisions made during the development of deploytracker, in the lightweight ADR format.

| ADR | Title | Status |
|---|---|---|
| [ADR-001](001-hexagonal-architecture.md) | Hexagonal Architecture (Ports & Adapters) | Accepted |
| [ADR-002](002-lgtm-vs-elastic.md) | LGTM Stack vs Elastic Stack | Accepted |
| [ADR-003](003-k3s-vs-eks.md) | K3s vs EKS | Accepted |
| [ADR-004](004-no-tempo-on-freetier.md) | Tempo deferred — RAM constraint | Accepted |
| [ADR-005](005-jwt-authentication.md) | JWT Authentication for the REST API | Accepted |
| [ADR-006](006-t3small-upgrade.md) | EC2 upgrade from t3.micro to t3.small | Accepted |

## Format

Each ADR contains:

- **Context** — the problem and constraints at the time of the decision
- **Decision** — what was chosen and why
- **Alternatives considered** — what was rejected and why
- **Consequences** — positive and negative outcomes
