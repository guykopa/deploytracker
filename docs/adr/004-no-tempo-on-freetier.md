# ADR-004: Tempo Not Deployed on Free-Tier Cluster

**Date:** 2026-05-21
**Status:** Accepted

## Context

The deploytracker application emits OpenTelemetry traces via the OTel SDK. The
OpenTelemetry Collector (deployed as part of the observability stack) receives these
traces on port 4317 (gRPC) and 4318 (HTTP/protobuf).

In a full LGTM+T stack, traces would be forwarded to **Grafana Tempo** for storage and
queried from Grafana using the Tempo data source. However, the cluster runs on t2.micro
nodes with 1 GiB RAM each, and Tempo's resource requirements exceed what is available
after accounting for the application and the rest of the observability stack.

Measured resource requirements:
- Grafana Tempo (single binary, minimal config): **~300 MiB RAM** at idle
- Tempo requires a PersistentVolumeClaim backed by a block device (EBS or local path)
- Total RAM already consumed by other workloads on the observability node: ~700 MiB

Deploying Tempo would push the node past its memory limit, triggering OOMKill events
on either Tempo itself or a critical workload such as Loki or Prometheus.

## Decision

**Tempo is not deployed in the free-tier demo environment.**

Instead, the OpenTelemetry Collector is configured with the `debug` exporter for
traces, which logs a structured summary of each span to stdout. This keeps the
pipeline intact (application → Collector) without requiring persistent trace storage.

The `trace_id` and `span_id` fields are injected into every structured log line via
the OTel logging bridge, so traces remain **correlatable with logs in Loki** even
without Tempo.

The Collector configuration stub for Tempo is committed but commented out in
`charts/observability/files/otel-collector-config.yaml`, making the migration path
explicit and reviewable.

## Alternatives Considered

### Deploy Tempo Anyway

Deploying Tempo with aggressive resource limits (`requests.memory: 128Mi`,
`limits.memory: 256Mi`) was tested. Under any non-trivial trace volume the process
exceeded its memory limit and was OOMKilled within minutes. The `--storage.trace.backend=local`
mode with a small block size reduced pressure but made trace data unreliable (lost
spans on eviction). Not viable.

### Replace Tempo with Jaeger

Jaeger (all-in-one image) has a similar idle memory footprint (~250–350 MiB) and also
requires a storage backend for production use (Cassandra or Elasticsearch, both of
which are even heavier). The Jaeger in-memory mode loses all data on pod restart.
Rejected for the same reasons as Tempo, with the additional drawback that Jaeger is
not natively integrated with Grafana's unified explore view.

### Disable OTel Instrumentation in the Application

Removing the OTel SDK from the application would free ~20 MiB of heap but would
eliminate the observability pipeline entirely, making it impossible to demonstrate
trace-log correlation. Rejected: the goal of the project is to demonstrate DORA metrics
*and* modern observability patterns.

## Migration Path

When a larger instance type is available (e.g., t3.small with 2 GiB RAM), enabling
Tempo requires three steps:

1. **Collector config** — uncomment the `otlp/tempo` exporter and add it to the
   `traces` pipeline in `charts/observability/files/otel-collector-config.yaml`:
   ```yaml
   exporters:
     otlp/tempo:
       endpoint: "http://tempo.observability.svc:4317"
       tls:
         insecure: true
   ```

2. **Deploy Tempo** — add the `grafana/tempo` Helm chart as a dependency in
   `charts/observability/Chart.yaml` and provide values in
   `charts/observability/values.yaml`:
   ```yaml
   tempo:
     enabled: true
     persistence:
       enabled: true
       size: 5Gi
   ```

3. **Grafana data source** — add a Tempo data source pointing to
   `http://tempo.observability.svc:3100` and link it to Loki via the
   `derivedFields` configuration to enable trace-to-log navigation.

No application code changes are required; the OTel SDK in the application already
exports to the Collector endpoint.

## Consequences

### Positive
- The observability node remains stable; no OOMKill events from Tempo.
- The `trace_id` field in logs provides partial traceability without a dedicated
  backend — spans can be reconstructed from logs in a pinch.
- The Collector pipeline is fully operational; enabling Tempo later is a configuration
  change, not an architectural change.

### Negative
- No flame-graph or waterfall trace visualisation in the demo environment. Reviewers
  cannot see end-to-end request latency breakdowns in Grafana.
- The `debug` exporter logs every span to stdout, which increases Collector log volume
  and may obscure other diagnostic messages if trace volume is high.
- Trace data is ephemeral (in-memory in the Collector's pipeline buffer); spans are
  lost if the Collector pod restarts.

## References

- Grafana Tempo architecture — <https://grafana.com/docs/tempo/latest/getting-started/>
- OTel Collector exporters — <https://opentelemetry.io/docs/collector/configuration/#exporters>
- `charts/observability/files/otel-collector-config.yaml` — current Collector config
- ADR-002 — LGTM stack selection and RAM constraints
