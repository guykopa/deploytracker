# deploytracker

A DevOps performance tracking service that collects deployment events from CI/CD pipelines and computes the **four DORA metrics** per service.

Built as a complete Move-to-Cloud demonstration on AWS: Terraform, Ansible, K3s, OpenTelemetry, Prometheus, Loki, Grafana, JWT authentication, and GitHub Actions.

**Documentation:** https://guykopa.github.io/deploytracker/

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

## Architecture

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
│  │ (secrets)  │  │  └── Load generator                │    │
│  └────────────┘  └──────────────────────────────────┘    │
└───────────────────────────────────────────────────────────┘

Telemetry flow:
  App → OTel Collector (OTLP gRPC 4317) → Prometheus (remote write)
                                         → Loki (OTLP HTTP)
                                         → debug exporter (traces)
```

---

## Prerequisites

- AWS account with CLI configured (`aws configure`)
- Terraform 1.7+
- Ansible 2.16+ with collections:
  ```bash
  ansible-galaxy collection install amazon.aws community.aws community.general
  ```
- Docker
- kubectl + helm 3
- Python 3.11+

---

## Quickstart

### 1. Bootstrap (one-time)

```bash
# Create the S3 bucket for Terraform state (run once ever)
bash scripts/bootstrap.sh

# Copy and fill in your secrets
cp infra/terraform/terraform.tfvars.example infra/terraform/terraform.tfvars
# Edit terraform.tfvars: set db_password, grafana_admin_password, k3s_token
```

### 2. Start a session

```bash
make infra-up      # Provision AWS: VPC, 3×EC2 t3.small, ECR, IAM, SSM, budget
make startup       # Configure K3s + build/push image + secrets + Helm deploy (all-in-one)
```

`make startup` runs the full sequence:
1. `terraform apply`
2. Ansible playbooks (bootstrap, K3s server, K3s agents, kubeconfig)
3. Docker build + push to ECR
4. Create Kubernetes namespaces + secrets (ECR credentials, DB password from SSM)
5. `helm upgrade --install observability` (Prometheus, Loki, Grafana, OTel Collector)
6. `helm upgrade --install deploytracker` (FastAPI app + PostgreSQL)

### 3. Verify

```bash
# API
curl http://$(terraform -chdir=infra/terraform output -raw k3s_server_public_ip):30080/health/ready
# → {"status":"ok"}

# Get a JWT token
curl -X POST http://<IP>:30080/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=<DEPLOYTRACKER_ADMIN_PASSWORD>"

# Call a protected endpoint
curl -H "Authorization: Bearer <token>" http://<IP>:30080/api/v1/services

# Grafana
make grafana
# http://<IP>:30030  →  admin / <grafana_admin_password from SSM>
```

### 4. Generate load (optional)

```bash
make loadgen-start   # Starts a pod simulating 5 services deploying every 10s
make loadgen-stop    # Stops it
```

### 5. Tear down (critical — avoids AWS charges)

```bash
make destroy-all     # helm uninstall + kubectl delete ns + terraform destroy
```

---

## Authentication

All `/api/v1/*` endpoints require a JWT Bearer token. The `health/*` endpoints are public.

### Get a token

```bash
curl -X POST http://<IP>:30080/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=<ADMIN_PASSWORD>"

# Response:
# {"access_token": "eyJ...", "token_type": "bearer"}
```

### Use the token

```bash
curl -H "Authorization: Bearer eyJ..." http://<IP>:30080/api/v1/services
```

Tokens are signed with HS256 and expire after 60 minutes (configurable via `DEPLOYTRACKER_JWT_EXPIRY_MINUTES`). The credentials and signing key are stored in the Kubernetes secret `deploytracker-secrets` (namespace `deploytracker`), sourced from AWS SSM Parameter Store.

---

## API reference

| Method | Path | Auth | Description |
|---|---|---|---|
| `POST` | `/auth/token` | — | Login, returns Bearer JWT |
| `GET` | `/health/live` | — | Liveness probe |
| `GET` | `/health/ready` | — | Readiness probe |
| `POST` | `/api/v1/services` | JWT | Register a service |
| `GET` | `/api/v1/services` | JWT | List all services |
| `POST` | `/api/v1/deployments` | JWT | Record a deployment event |
| `POST` | `/api/v1/deployments/{id}/fail` | JWT | Mark deployment as failed |
| `POST` | `/api/v1/deployments/{id}/recover` | JWT | Mark deployment as recovered |
| `GET` | `/api/v1/services/{name}/deployments` | JWT | List deployments for a service |
| `GET` | `/api/v1/services/{name}/dora` | JWT | Get DORA metrics for a service |
| `GET` | `/docs` | — | OpenAPI UI (Swagger) |

### Example: record a deployment event

```bash
TOKEN=$(curl -s -X POST http://<IP>:30080/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=<PASSWORD>" | jq -r .access_token)

curl -X POST http://<IP>:30080/api/v1/deployments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service_name": "payment-service",
    "version": "v1.4.2",
    "environment": "production",
    "commit_sha": "abc123def456",
    "deployer": "github-actions",
    "commit_timestamp": "2026-05-21T10:00:00Z",
    "deployed_at": "2026-05-21T10:30:00Z"
  }'
```

### Example: get DORA metrics

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://<IP>:30080/api/v1/services/payment-service/dora

# Response:
# {
#   "service": "payment-service",
#   "period_days": 30,
#   "deployment_frequency": 2.3,
#   "lead_time_p50": 3600.0,
#   "change_failure_rate": 0.12,
#   "mttr_p50": 1800.0
# }
```

---

## Local development

```bash
cd app

# Setup
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure (copy and edit)
cp .env.example .env
# Edit .env: set DATABASE_URL to your local postgres

# Run
uvicorn deploytracker.api.main:app --reload

# Test, lint, typecheck
make test        # pytest + coverage (≥ 80%)
make lint        # ruff
make typecheck   # mypy strict
```

The `.env` file is gitignored. See `.env.example` for all available variables.

---

## Infrastructure details

### EC2 instances

| Role | Private IP | Instance type | RAM |
|---|---|---|---|
| K3s server (control-plane) | 10.0.1.40 | t3.small | 2 GB |
| K3s agent-1 | 10.0.1.136 | t3.small | 2 GB |
| K3s agent-2 | 10.0.1.56 | t3.small | 2 GB |

The server has an Elastic IP (static public IP). Agents use dynamic public IPs (accessed internally by private IP only).

### Kubernetes namespaces

| Namespace | Workloads |
|---|---|
| `deploytracker` | FastAPI API, PostgreSQL 16, load generator |
| `observability` | Prometheus, Loki, Grafana, OTel Collector, Promtail, node-exporter |

### Secrets management

All secrets are stored in **AWS SSM Parameter Store** as `SecureString`:
- `/deploytracker/db_password` — PostgreSQL password
- `/deploytracker/grafana_admin_password` — Grafana admin password
- `/deploytracker/k3s_token` — K3s cluster join token

Kubernetes secrets are created from SSM values at session start by `scripts/startup.sh`. They are never committed to git.

### NodePorts

| Service | Port |
|---|---|
| deploytracker API | 30080 |
| Grafana | 30030 |

---

## Free-tier cost notes

> **Instance type was upgraded from t3.micro (1 GB) to t3.small (2 GB)** to provide sufficient RAM for K3s + the full observability stack. t3.small is **not free tier** — it costs approximately $0.020/hour per instance.

| Resource | Cost |
|---|---|
| 3 × t3.small EC2 | ~$43/month |
| 3 × 8 GB EBS gp3 | ~$2/month |
| ECR storage | <$1/month |
| SSM parameters | Free |
| **Total** | **~$45/month** |

A CloudWatch budget alarm is configured at **$10/month** — you will receive an email before costs spike. Always run `make destroy-all` at the end of work sessions.

Forbidden services (still avoided):
- EKS ($73/month for the control plane alone)
- NAT Gateway (~$32/month)
- Application Load Balancer (hourly charge)

---

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Framework | FastAPI |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 + Alembic |
| Auth | JWT (PyJWT, HS256) |
| Dependency management | Poetry (dev) / pip (Docker) |
| Testing | pytest + pytest-cov |
| Linting | Ruff |
| Type checking | mypy (strict) |
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
| Traces | OTel Collector (debug exporter; Tempo deferred — see ADR-004) |
| Dashboards | Grafana 11 |
| K8s packaging | Helm 3 |
| CI/CD | GitHub Actions |

---

## Architecture Decision Records

- [ADR-001](docs/adr/001-hexagonal-architecture.md) — Hexagonal Architecture
- [ADR-002](docs/adr/002-lgtm-vs-elastic.md) — LGTM vs Elastic Stack
- [ADR-003](docs/adr/003-k3s-vs-eks.md) — K3s vs EKS
- [ADR-004](docs/adr/004-no-tempo-on-freetier.md) — Tempo deferred
- [ADR-005](docs/adr/005-jwt-authentication.md) — JWT Authentication
- [ADR-006](docs/adr/006-t3small-upgrade.md) — t3.micro → t3.small upgrade
