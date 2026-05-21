# ADR-006: EC2 Instance Upgrade from t3.micro to t3.small

**Date:** 2026-05-21
**Status:** Accepted

## Context

The original deploytracker cluster ran on three **t3.micro** instances (1 vCPU, **1 GiB RAM**). Over the course of deploying the full LGTM observability stack alongside K3s and the application, the control-plane node repeatedly ran out of memory.

### Measured memory usage on the control-plane (t3.micro, 1 GiB):

| Process | RSS |
|---|---|
| k3s server (API server + kine SQLite) | ~250 MB |
| Grafana (was on control-plane by mistake) | ~90 MB |
| otel-collector | ~55 MB |
| Promtail | ~40 MB |
| containerd | ~35 MB |
| coredns | ~25 MB |
| OS + kernel | ~100 MB |
| **Total** | **~595 MB** |

Available: 400 MB — fine in theory. In practice, the kine SQLite database (K3s's etcd replacement) and Grafana's dashboarding engine exhibited memory spikes that pushed the node past 950 MB, triggering Linux OOM events.

Symptoms observed:
- K3s API server stopped responding (TLS handshake timeouts)
- PLEG (Pod Lifecycle Event Generator) marked unhealthy after 6+ minutes of inactivity
- kubectl timing out from the local machine
- otel-collector continuously killed by kubelet liveness probe (health endpoint unreachable due to resource contention)

Root causes identified:
1. **Grafana placed on control-plane** (`nodeSelector: role: control`) — error in initial values.yaml. Fixed by moving Grafana to `role: app`.
2. **1 GiB RAM insufficient** for K3s + full observability stack even with correct pod placement. The kine database alone exhibits 2–7 second SQL query times under swap pressure.

## Decision

Upgrade all three EC2 instances from **t3.micro (1 GiB)** to **t3.small (2 GiB RAM)**.

Simultaneously, correct Grafana's `nodeSelector` from `role: control` to `role: app` to stop burdening the control-plane.

### Why t3.small and not larger?

| Type | RAM | vCPU | Price (eu-west-3) | Notes |
|---|---|---|---|---|
| t3.micro | 1 GiB | 2 | $0.0114/h | Insufficient |
| **t3.small** | **2 GiB** | **2** | **$0.0228/h** | ✅ Selected |
| t3.medium | 4 GiB | 2 | $0.0456/h | Overkill for demo |

t3.small provides exactly double the RAM needed to absorb the observed memory spikes with comfortable headroom. Going to t3.medium would triple the cost with no observable benefit at the current workload scale.

### Why upgrade all three nodes (not just the control-plane)?

The agent nodes run Prometheus (512 MB limit), Loki (256 MB limit), Grafana (256 MB limit after relocation), and the application. Under normal load, agents stay within 1 GiB, but:
- Prometheus experiences spikes when ingesting large scrape batches
- Loki's chunk cache can grow without bound if not limited
- Upgrading all nodes maintains uniformity and avoids future asymmetric failures

### Terraform change

```hcl
# infra/terraform/ec2.tf
resource "aws_instance" "k3s_server" {
  instance_type = "t3.small"   # was t3.micro
  ...
}
```

Applied via `terraform apply` — in-place update (stop, resize, start). EBS volumes and Elastic IP are preserved. Downtime: ~2 minutes per instance.

## Consequences

### Positive

- Control-plane: 908 MB available after full stack running — no more OOM events.
- kine SQL queries return in <100 ms — kubectl is responsive.
- otel-collector stays Running without liveness probe failures.
- Agents have ~1 GB headroom for workload growth.

### Negative

- **Cost**: 3 × t3.small × $0.0228/h = ~$49/month (vs $0 on t3.micro free tier for new accounts). Not free-tier eligible.
- Budget alarm threshold should be raised from $1 to $10 to avoid false positives.

### Post-upgrade node placement

| Component | Node | Reason |
|---|---|---|
| K3s control plane | ip-10-0-1-40 (control) | Required |
| OTel Collector | All nodes (DaemonSet) | Required |
| Promtail | All nodes (DaemonSet) | Required |
| Prometheus | ip-10-0-1-136 (agent-1) | Stable PVC |
| Loki | ip-10-0-1-56 (agent-2) | Stable PVC |
| Grafana | ip-10-0-1-56 (agent-2) | Off control-plane ✅ |
| deploytracker API | ip-10-0-1-136 (agent-1) | role: app |
| PostgreSQL | ip-10-0-1-56 (agent-2) | role: app, stable PVC |

## References

- `infra/terraform/ec2.tf` — instance type definition
- `charts/observability/values.yaml` — Grafana nodeSelector
- ADR-003 — original K3s topology decision
- ADR-002 — LGTM stack RAM constraints (originally sized for t3.micro; now relaxed)
