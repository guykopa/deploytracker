import statistics
from dataclasses import dataclass
from datetime import timedelta

from deploytracker.domain.models import Deployment, DeploymentStatus
from deploytracker.domain.ports import Clock, DeploymentRepository


@dataclass
class DoraMetrics:
    deployment_frequency: float
    lead_time_p50: float
    change_failure_rate: float
    mttr_p50: float | None
    period_days: int
    service: str


class DoraCalculator:
    def __init__(self, repo: DeploymentRepository, clock: Clock) -> None:
        self._repo = repo
        self._clock = clock

    def compute(self, service: str, period_days: int) -> DoraMetrics:
        since = self._clock.now() - timedelta(days=period_days)
        deployments = self._repo.list_by_service(service, since=since)
        return DoraMetrics(
            deployment_frequency=self._frequency(deployments, period_days),
            lead_time_p50=self._median_lead_time(deployments),
            change_failure_rate=self._failure_rate(deployments),
            mttr_p50=self._median_recovery_time(deployments),
            period_days=period_days,
            service=service,
        )

    def _frequency(self, deployments: list[Deployment], period_days: int) -> float:
        return len(deployments) / period_days if period_days > 0 else 0.0

    def _median_lead_time(self, deployments: list[Deployment]) -> float:
        times = [d.lead_time_seconds for d in deployments]
        return statistics.median(times) if times else 0.0

    def _failure_rate(self, deployments: list[Deployment]) -> float:
        if not deployments:
            return 0.0
        failed = sum(
            1 for d in deployments if d.status in (DeploymentStatus.FAILED, DeploymentStatus.RECOVERED)
        )
        return failed / len(deployments)

    def _median_recovery_time(self, deployments: list[Deployment]) -> float | None:
        times = [d.recovery_time_seconds for d in deployments if d.recovery_time_seconds is not None]
        return statistics.median(times) if times else None
