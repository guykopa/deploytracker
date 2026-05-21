# ADR-002: LGTM Observability Stack vs Elastic Stack

**Date:** 2026-05-21
**Status:** Accepted

## Context

The deploytracker cluster runs on three AWS EC2 t2.micro instances (1 vCPU, 1 GiB RAM
each). The observability stack must provide metrics, logs, and (when feasible) traces
while respecting the extreme memory constraints of the free-tier environment.

Three candidate stacks were evaluated:

| Stack    | Components                                   | Approx. idle RAM |
|----------|----------------------------------------------|-----------------|
| LGTM     | Prometheus + Loki + Grafana + OTel Collector | ~350 MiB total  |
| Elastic  | Elasticsearch + Logstash + Kibana            | ~1.5 GiB+       |
| Datadog  | SaaS agent                                   | ~200 MiB agent  |

## Decision

Deploy the **LGTM stack**: Prometheus for metrics, Loki for logs, Grafana as the
unified visualisation layer, and the OpenTelemetry Collector as the ingestion gateway.

The Helm chart at `charts/observability` wraps the `kube-prometheus-stack` (for
Prometheus + Grafana) and adds Loki and the OTel Collector as sub-charts, with all
resource requests and limits tuned to stay within the 1 GiB per-node budget.

## Alternatives Considered

### Elastic Stack (Elasticsearch + Logstash + Kibana)

Elasticsearch alone requires a minimum JVM heap of 1 GiB (`-Xms1g`) before handling a
single document. On a t2.micro node this immediately causes an OOMKill. Even with the
`-Xms256m` override, the JVM bloats under load and the node becomes unresponsive.
Logstash adds another ~300 MiB. Kibana adds ~400 MiB. The total idle footprint (~2 GiB)
exceeds the entire cluster's available RAM.

Rejected: **OOM on t2.micro, cannot be mitigated without a larger instance type.**

### Datadog (SaaS)

The Datadog agent is lightweight (~200 MiB), and the SaaS backend removes the need to
host a storage tier. However, Datadog pricing for infrastructure + APM + logs starts at
roughly $23/host/month, bringing the total to ~$70/month — incompatible with a
zero-budget demo project. The free tier covers only basic metrics for up to 5 hosts with
a 1-day retention, which is insufficient for meaningful DORA trend analysis.

Rejected: **cost exceeds project budget.**

## Consequences

### Positive
- The full stack fits comfortably within the available RAM when resource limits are
  applied (Prometheus: 128 MiB, Loki: 128 MiB, Grafana: 100 MiB, OTel Collector:
  64 MiB).
- Native Grafana data sources for both Prometheus (PromQL) and Loki (LogQL) allow
  correlated dashboards without extra plugins.
- OpenTelemetry Collector acts as a vendor-neutral ingestion point: switching the
  backend later (e.g., adding Tempo for traces) requires only an exporter config
  change, not application code changes.
- All components are CNCF projects with active communities and long-term support
  commitments.

### Negative
- Loki is not a full-text search engine; complex log queries (regex across large
  time windows) are slower than Elasticsearch queries on the same data.
- No distributed tracing visualisation in the free-tier deployment (see ADR-004).
- Prometheus uses local disk storage with a configurable retention window; long-term
  metric history requires an external remote-write endpoint (e.g., Thanos, Cortex)
  which is out of scope for this demo.

## References

- Grafana LGTM stack overview — <https://grafana.com/oss/>
- Loki architecture — <https://grafana.com/docs/loki/latest/get-started/architecture/>
- Elasticsearch JVM heap sizing — <https://www.elastic.co/guide/en/elasticsearch/reference/current/advanced-configuration.html#set-jvm-heap-size>
- `charts/observability/values.yaml` — resource limit configuration
