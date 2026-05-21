# Architecture

## Overview

```
Developer / CI-CD pipeline
        │
        │  POST /api/v1/deployments  (Bearer JWT)
        ▼
┌───────────────────────────────────────────────────────────┐
│                    AWS eu-west-3                           │
│                                                           │
│  ┌──────────┐    ┌──────────────────────────────────┐    │
│  │ ECR      │    │  K3s cluster (3 × t3.small)       │    │
│  │ registry │    │                                   │    │
│  └────┬─────┘    │  control-plane (ip-10-0-1-40)     │    │
│       │          │  ├── K3s server (API, scheduler)  │    │
│       │ pull     │  ├── OTel Collector (DaemonSet)   │    │
│       ▼          │  └── Promtail (DaemonSet)          │    │
│  ┌────────────┐  │                                   │    │
│  │deploytrack-│  │  agent-1 (ip-10-0-1-136)          │    │
│  │er API pod  │  │  ├── deploytracker API (FastAPI)  │    │
│  │(FastAPI)   │  │  ├── Prometheus server             │    │
│  └────────────┘  │  └── Promtail                      │    │
│                  │                                   │    │
│  ┌────────────┐  │  agent-2 (ip-10-0-1-56)           │    │
│  │ SSM        │  │  ├── PostgreSQL 16                 │    │
│  │ Parameter  │  │  ├── Loki                          │    │
│  │ Store      │  │  ├── Grafana (NodePort 30030)      │    │
│  │ (secrets)  │  │  └── Load generator (CronJob)      │    │
│  └────────────┘  └──────────────────────────────────┘    │
└───────────────────────────────────────────────────────────┘
```

### Telemetry flow

```
App (OTLP gRPC :4317) → OTel Collector
                             ├── Prometheus remote write  → Prometheus (agent-1)
                             ├── OTLP HTTP logs           → Loki (agent-2)
                             └── debug exporter           → stdout (traces)

Promtail (DaemonSet) → Loki (agent-2)
Grafana              → Prometheus, Loki (data sources)
```

---

## Application: Hexagonal Architecture

The FastAPI application follows a strict Hexagonal (Ports & Adapters) architecture. Dependencies flow inward only.

```
api/ (presentation)
        │
        ▼
application/ (use cases)
        │
        ▼
domain/ (entities, ports)
        ↑
infrastructure/ (adapters: DB, OTel, config)
```

### Layer responsibilities

| Layer | Package | Responsibilities |
|---|---|---|
| **Domain** | `domain/` | Entities (`Deployment`, `Service`), Pydantic schemas, abstract repository interfaces, business exceptions |
| **Application** | `application/` | Use cases (`DeploymentService`, `DoraCalculator`) — orchestrates domain objects using repository interfaces |
| **Infrastructure** | `infrastructure/` | SQLAlchemy repositories, OTel SDK initialization, settings (`pydantic-settings`) |
| **API** | `api/` | FastAPI routes, JWT auth middleware, HTTP request/response translation |

### Key files

```
app/src/deploytracker/
├── domain/
│   ├── models.py           # SQLAlchemy ORM models
│   ├── schemas.py          # Pydantic request/response schemas
│   ├── repositories.py     # Abstract repository interfaces (ports)
│   └── exceptions.py       # Domain exceptions
├── application/
│   ├── deployment_service.py   # Deployment CRUD use cases
│   └── dora_calculator.py      # DORA metric computations
├── infrastructure/
│   ├── config.py               # Settings (pydantic-settings, env vars)
│   ├── db/
│   │   ├── session.py          # SQLAlchemy engine + session factory
│   │   └── repositories/       # Concrete repository implementations
│   └── telemetry/
│       ├── setup.py            # OTel SDK initialization
│       └── metrics.py          # Custom metric instruments
└── api/
    ├── main.py                 # FastAPI app factory, lifespan
    ├── auth.py                 # JWT create/decode functions
    ├── dependencies.py         # FastAPI dependencies (get_db, get_current_user)
    └── routes/
        ├── auth.py             # POST /auth/token
        ├── deployments.py      # /api/v1/deployments
        ├── services.py         # /api/v1/services
        └── health.py           # /health/live, /health/ready
```

---

## Infrastructure

### Terraform resources

| Resource | Description |
|---|---|
| `aws_vpc` | /16 VPC in eu-west-3 |
| `aws_subnet` | Single public subnet /24 |
| `aws_instance × 3` | t3.small EC2 (control-plane + 2 agents) |
| `aws_eip` | Elastic IP on control-plane only |
| `aws_ecr_repository` | Container registry for deploytracker image |
| `aws_iam_role` | EC2 instance role with SSM read + ECR pull |
| `aws_ssm_parameter × 3` | SecureString secrets (DB password, Grafana password, K3s token) |
| `aws_budgets_budget` | CloudWatch budget alarm at $10/month |
| `aws_s3_bucket` | Terraform remote state backend |

### Ansible playbooks

| Playbook | What it does |
|---|---|
| `bootstrap.yml` | Install Docker, utilities on all nodes |
| `k3s-server.yml` | Install K3s server on control-plane, disable Traefik |
| `k3s-agents.yml` | Join agent nodes to the cluster |
| `kubeconfig.yml` | Fetch kubeconfig and patch server URL to Elastic IP |

### Kubernetes cluster

| Node | Private IP | Role | Key workloads |
|---|---|---|---|
| ip-10-0-1-40 | 10.0.1.40 | control-plane | K3s server, OTel Collector, Promtail |
| ip-10-0-1-136 | 10.0.1.136 | agent-1 | deploytracker API, Prometheus, Promtail |
| ip-10-0-1-56 | 10.0.1.56 | agent-2 | PostgreSQL, Loki, Grafana, loadgen |

Node labels: `role=control` (control-plane), `role=app` (agents).

### Kubernetes namespaces

| Namespace | Workloads |
|---|---|
| `deploytracker` | FastAPI API, PostgreSQL 16, load generator CronJob |
| `observability` | Prometheus, Loki, Grafana, OTel Collector, Promtail, node-exporter |

---

## Secrets management

All secrets are stored in **AWS SSM Parameter Store** as `SecureString`:

| SSM path | Used by |
|---|---|
| `/deploytracker/db_password` | PostgreSQL + deploytracker API |
| `/deploytracker/grafana_admin_password` | Grafana Helm values |
| `/deploytracker/k3s_token` | K3s agent join |

At session start, `scripts/startup.sh` reads these from SSM and creates the Kubernetes secret `deploytracker-secrets` in the `deploytracker` namespace. This secret is never committed to git.

---

## DORA metrics computation

All metrics are computed over a rolling 30-day window by the `DoraCalculator` use case.

| Metric | Formula |
|---|---|
| Deployment Frequency | `total_deployments / 30` (deployments/day) |
| Lead Time for Changes | `p50(deployed_at − commit_timestamp)` in seconds |
| Change Failure Rate | `failed_deployments / total_deployments` |
| MTTR | `p50(recovered_at − failed_at)` in seconds |

The API endpoint `GET /api/v1/services/{name}/dora` returns these four values.
