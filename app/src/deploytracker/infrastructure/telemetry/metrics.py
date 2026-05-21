from opentelemetry import metrics

_meter = metrics.get_meter("deploytracker", version="0.1.0")

deployments_total = _meter.create_counter(
    name="deploytracker_deployments_total",
    description="Total number of deployments recorded",
    unit="1",
)

lead_time_histogram = _meter.create_histogram(
    name="deploytracker_lead_time_seconds",
    description="Lead time from commit to deployment in seconds",
    unit="s",
)

recovery_time_histogram = _meter.create_histogram(
    name="deploytracker_recovery_time_seconds",
    description="Time to recover from a failure in seconds",
    unit="s",
)

active_failures = _meter.create_up_down_counter(
    name="deploytracker_active_failures",
    description="Number of deployments currently in failed state",
    unit="1",
)

dora_compute_duration = _meter.create_histogram(
    name="deploytracker_dora_compute_duration_seconds",
    description="Duration of DORA metrics computation in seconds",
    unit="s",
)


def record_deployment(service: str, environment: str, status: str) -> None:
    deployments_total.add(1, {"service": service, "environment": environment, "status": status})


def record_lead_time(service: str, seconds: float) -> None:
    lead_time_histogram.record(seconds, {"service": service})


def record_recovery_time(service: str, seconds: float) -> None:
    recovery_time_histogram.record(seconds, {"service": service})
    active_failures.add(-1, {"service": service})


def increment_active_failures(service: str) -> None:
    active_failures.add(1, {"service": service})


def record_dora_compute_duration(service: str, seconds: float) -> None:
    dora_compute_duration.record(seconds, {"service": service})
