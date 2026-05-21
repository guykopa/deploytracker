# Infrastructure

## AWS resources

The entire infrastructure is managed by Terraform in `infra/terraform/`.

### EC2 instances

| Role | Private IP | Public IP | Instance type | RAM |
|---|---|---|---|---|
| K3s control-plane | 10.0.1.40 | Elastic IP (static) | t3.small | 2 GB |
| K3s agent-1 | 10.0.1.136 | Dynamic (private access only) | t3.small | 2 GB |
| K3s agent-2 | 10.0.1.56 | Dynamic (private access only) | t3.small | 2 GB |

The control-plane has an Elastic IP so the public API endpoint stays stable across EC2 stops/starts. Agents are only accessed from inside the VPC.

For the reasoning behind t3.small (not free-tier t3.micro), see [ADR-006](adr/006-t3small-upgrade.md).

### Security groups

| Port | Protocol | Source | Purpose |
|---|---|---|---|
| 22 | TCP | Your IP | SSH access (Ansible) |
| 30080 | TCP | 0.0.0.0/0 | deploytracker API (NodePort) |
| 30030 | TCP | 0.0.0.0/0 | Grafana UI (NodePort) |
| 6443 | TCP | VPC CIDR | K3s API server |
| All | All | VPC CIDR | Internal cluster communication |

### Storage

Each EC2 instance has an **8 GB gp3 EBS volume** for the OS and container images.

PersistentVolumes are provisioned by K3s's built-in `rancher.io/local-path` StorageClass, which creates directories on the node's EBS volume.

!!! warning "PVC node affinity"
    local-path PVCs are permanently bound to the node where they were first created. You cannot move a stateful pod (Prometheus, Loki, PostgreSQL) to a different node without deleting its PVC (data loss). Plan pod placement carefully.

---

## Kubernetes pod placement

| Component | Node | Namespace | Why there |
|---|---|---|---|
| K3s server (API, scheduler, etcd/kine) | ip-10-0-1-40 | kube-system | Required on control-plane |
| OTel Collector | All nodes (DaemonSet) | observability | Collects telemetry from every node |
| Promtail | All nodes (DaemonSet) | observability | Collects logs from every node |
| Prometheus | ip-10-0-1-136 (agent-1) | observability | Stable PVC on agent-1 |
| deploytracker API | ip-10-0-1-136 (agent-1) | deploytracker | `role: app` node selector |
| PostgreSQL 16 | ip-10-0-1-56 (agent-2) | deploytracker | Stable PVC on agent-2 |
| Loki | ip-10-0-1-56 (agent-2) | observability | Stable PVC on agent-2 |
| Grafana | ip-10-0-1-56 (agent-2) | observability | Off control-plane (see ADR-006) |
| Load generator | ip-10-0-1-56 (agent-2) | deploytracker | `role: app`, no PVC needed |

Node labels used for scheduling:
- `role=control` — control-plane only
- `role=app` — agents only (where application workloads run)

---

## Helm charts

### `charts/deploytracker`

Deploys the FastAPI application and PostgreSQL.

Key values in `charts/deploytracker/values.yaml`:

| Value | Default | Description |
|---|---|---|
| `image.repository` | (ECR URL) | Docker image for the API |
| `image.tag` | `latest` | Image tag |
| `service.nodePort` | `30080` | External API port |
| `postgresql.enabled` | `true` | Deploy PostgreSQL as a sub-chart |
| `postgresql.nodeSelector` | `role: app` | Pin PostgreSQL to agent nodes |

### `charts/observability`

Umbrella chart that deploys Prometheus, Loki, Grafana, OTel Collector, Promtail.

Key values in `charts/observability/values.yaml`:

| Component | Key settings |
|---|---|
| Grafana | `nodeSelector: role: app`, NodePort 30030 |
| Prometheus | `nodeSelector: role: app`, 8Gi PVC on agent-1 |
| Loki | `nodeSelector: role: app`, 5Gi PVC on agent-2 |
| OTel Collector | DaemonSet, `health_check` extension on port 13133 |
| Promtail | DaemonSet |

!!! note "Grafana nodeSelector"
    Grafana **must** have `nodeSelector: role: app`. Placing it on the control-plane (`role: control`) overloads the control-plane RAM budget and causes OOM events. This was the root cause of the t3.micro OOM incident documented in ADR-006.

---

## Secrets management

### SSM Parameter Store

| Path | Type | Used by |
|---|---|---|
| `/deploytracker/db_password` | SecureString | PostgreSQL init + deploytracker API |
| `/deploytracker/grafana_admin_password` | SecureString | Grafana Helm chart |
| `/deploytracker/k3s_token` | SecureString | K3s agent join |

Values are set by Terraform during `make infra-up` using the variables in `terraform.tfvars`.

### Kubernetes secrets

| Secret | Namespace | Contents |
|---|---|---|
| `deploytracker-secrets` | deploytracker | DATABASE_URL, ADMIN_USERNAME, ADMIN_PASSWORD, JWT_SECRET_KEY |
| `ecr-credentials` | deploytracker | ECR Docker registry login (expires every 12h) |

These are created by `scripts/startup.sh` at session start. They are never committed to git.

---

## CI/CD

### GitHub Actions workflows

| Workflow | Trigger | What it does |
|---|---|---|
| `.github/workflows/ci.yml` | Push/PR on `app/**` | Lint (Ruff), typecheck (mypy), test (pytest ≥80% coverage) |
| `.github/workflows/deploy.yml` | Push to `main` on `app/**` | Build Docker image, push to ECR, rolling restart of the API pod |
| `.github/workflows/docs.yml` | Push to `main` on `docs/**`, `mkdocs.yml` | Build and deploy this documentation to GitHub Pages |

### ECR image naming

```
<account>.dkr.ecr.eu-west-3.amazonaws.com/deploytracker:<sha>
<account>.dkr.ecr.eu-west-3.amazonaws.com/deploytracker:latest
```

The deploy workflow tags images with both the Git SHA and `latest`.

---

## Observability stack

### Metrics pipeline

```
FastAPI app → OTLP gRPC (4317) → OTel Collector → Prometheus remote write (9090)
                                                 → Grafana (data source: Prometheus)
```

Custom metrics defined in `app/src/deploytracker/infrastructure/telemetry/metrics.py`:
- `deploytracker_deployments_total` — counter by service and status
- `deploytracker_api_request_duration_seconds` — histogram of HTTP request durations

### Logs pipeline

```
App stdout → Promtail → Loki ← Grafana
OTel Collector → OTLP HTTP → Loki
```

Structured JSON logs. Each log line includes `trace_id` and `span_id` injected by OpenTelemetry's `LoggingInstrumentor`.

### Traces

The OTel Collector is configured with a `debug` exporter (prints to stdout). Full distributed tracing with Grafana Tempo is architecturally planned but not deployed under the current RAM budget. See [ADR-004](adr/004-no-tempo-on-freetier.md).
