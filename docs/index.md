# deploytracker

A DevOps performance tracking service that collects deployment events from CI/CD pipelines and computes the **four DORA metrics** per service.

Built as a complete Move-to-Cloud demonstration on AWS: Terraform, Ansible, K3s, OpenTelemetry, Prometheus, Loki, Grafana, JWT authentication, and GitHub Actions.

---

## What it does

Every time a CI/CD pipeline deploys code, it sends a signed event to deploytracker. The service stores the event in PostgreSQL and computes:

| Metric | Description |
|---|---|
| **Deployment Frequency** | How often code reaches production (deployments/day) |
| **Lead Time for Changes** | Median time between commit and production deployment |
| **Change Failure Rate** | % of deployments that caused an incident |
| **MTTR** | Median time to recover from an incident |

Results are visualized in real-time Grafana dashboards and accessible via a JWT-secured REST API.

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Framework | FastAPI |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 + Alembic |
| Auth | JWT (PyJWT, HS256) |
| Cloud | AWS eu-west-3 |
| IaC | Terraform 1.7+ |
| Config management | Ansible 2.16+ |
| Container runtime | Docker |
| Orchestration | K3s 1.31 |
| Container registry | AWS ECR |
| Secrets | AWS SSM Parameter Store |
| Observability SDK | OpenTelemetry Python |
| Metrics | Prometheus + OTel Collector |
| Logs | Loki + Promtail |
| Dashboards | Grafana 11 |
| K8s packaging | Helm 3 |
| CI/CD | GitHub Actions |

---

## Repository layout

```
deploytracker/
├── .github/workflows/          # GitHub Actions CI/CD pipelines
├── app/                        # FastAPI application (Hexagonal Architecture)
│   ├── src/deploytracker/
│   │   ├── api/                # Presentation layer (routes, middleware, auth)
│   │   ├── application/        # Use cases (deployment service, DORA calculator)
│   │   ├── domain/             # Entities, schemas, business exceptions
│   │   └── infrastructure/     # DB, OTel, config (concrete adapters)
│   ├── tests/
│   │   ├── unit/               # Domain and application logic tests
│   │   └── integration/        # API + DB tests with testcontainers
│   ├── Dockerfile              # Multi-stage build
│   └── pyproject.toml
├── loadgen/                    # Load generator (CronJob simulating deployments)
├── infra/
│   ├── terraform/              # AWS provisioning (VPC, EC2, ECR, IAM, SSM, budget)
│   └── ansible/                # K3s cluster bootstrap and configuration
├── charts/
│   ├── deploytracker/          # Helm chart for the application
│   └── observability/          # Helm umbrella chart (Prom + Loki + Grafana + OTel)
├── dashboards/                 # Grafana dashboard JSON exports
├── docs/                       # This documentation site
├── scripts/                    # Helper scripts (bootstrap, startup, destroy)
├── Makefile                    # Single entry point for all operations
└── README.md
```
