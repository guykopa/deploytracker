from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from deploytracker.application.dora_calculator import DoraCalculator
from deploytracker.domain.models import Deployment, DeploymentStatus

# ---------------------------------------------------------------------------
# Fakes (same pattern as deployment_service tests)
# ---------------------------------------------------------------------------


class FakeDeploymentRepository:
    def __init__(self, deployments: list[Deployment] | None = None) -> None:
        self._store = deployments or []

    def save(self, deployment: Deployment) -> Deployment:
        self._store.append(deployment)
        return deployment

    def get(self, deployment_id: object) -> Deployment | None:
        return None

    def list_by_service(self, service: str, since: datetime) -> list[Deployment]:
        return [d for d in self._store if d.service_name == service and d.deployed_at >= since]

    def update(self, deployment: Deployment) -> Deployment:
        return deployment


class FakeClock:
    def __init__(self, fixed: datetime) -> None:
        self._now = fixed

    def now(self) -> datetime:
        return self._now


NOW = datetime(2024, 6, 30, 0, 0, 0, tzinfo=timezone.utc)


def _make_deployment(
    deployed_at: datetime,
    status: DeploymentStatus = DeploymentStatus.SUCCESS,
    lead_time_hours: int = 1,
    failure_detected_at: datetime | None = None,
    recovered_at: datetime | None = None,
) -> Deployment:
    commit_timestamp = deployed_at - timedelta(hours=lead_time_hours)
    return Deployment(
        id=uuid4(),
        service_name="svc",
        version="1.0.0",
        environment="production",
        commit_sha="abc",
        deployer="alice",
        commit_timestamp=commit_timestamp,
        deployed_at=deployed_at,
        status=status,
        failure_detected_at=failure_detected_at,
        recovered_at=recovered_at,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDoraCalculatorEmpty:
    def test_empty_deployments_returns_zero_metrics(self) -> None:
        calculator = DoraCalculator(FakeDeploymentRepository([]), FakeClock(NOW))
        result = calculator.compute("svc", period_days=30)

        assert result.deployment_frequency == 0.0
        assert result.lead_time_p50 == 0.0
        assert result.change_failure_rate == 0.0
        assert result.mttr_p50 is None


class TestDeploymentFrequency:
    def test_frequency_calculation(self) -> None:
        deployments = [
            _make_deployment(NOW - timedelta(days=i)) for i in range(6)
        ]
        calculator = DoraCalculator(FakeDeploymentRepository(deployments), FakeClock(NOW))
        result = calculator.compute("svc", period_days=30)

        assert result.deployment_frequency == pytest.approx(6 / 30)

    def test_zero_period_returns_zero_frequency(self) -> None:
        calculator = DoraCalculator(FakeDeploymentRepository([]), FakeClock(NOW))
        result = calculator.compute("svc", period_days=0)
        assert result.deployment_frequency == 0.0


class TestLeadTimeP50:
    def test_median_lead_time(self) -> None:
        # Lead times: 1h, 2h, 3h → median = 2h = 7200s
        deployments = [
            _make_deployment(NOW - timedelta(days=1), lead_time_hours=1),
            _make_deployment(NOW - timedelta(days=2), lead_time_hours=2),
            _make_deployment(NOW - timedelta(days=3), lead_time_hours=3),
        ]
        calculator = DoraCalculator(FakeDeploymentRepository(deployments), FakeClock(NOW))
        result = calculator.compute("svc", period_days=30)

        assert result.lead_time_p50 == pytest.approx(7200.0)


class TestChangeFailureRate:
    def test_no_failures(self) -> None:
        deployments = [_make_deployment(NOW - timedelta(days=i)) for i in range(5)]
        calculator = DoraCalculator(FakeDeploymentRepository(deployments), FakeClock(NOW))
        result = calculator.compute("svc", period_days=30)

        assert result.change_failure_rate == 0.0

    def test_partial_failures(self) -> None:
        deployments = [
            _make_deployment(NOW - timedelta(days=1), status=DeploymentStatus.SUCCESS),
            _make_deployment(NOW - timedelta(days=2), status=DeploymentStatus.FAILED),
            _make_deployment(NOW - timedelta(days=3), status=DeploymentStatus.RECOVERED),
            _make_deployment(NOW - timedelta(days=4), status=DeploymentStatus.SUCCESS),
        ]
        calculator = DoraCalculator(FakeDeploymentRepository(deployments), FakeClock(NOW))
        result = calculator.compute("svc", period_days=30)

        assert result.change_failure_rate == pytest.approx(0.5)


class TestMttrP50:
    def test_mttr_with_recovered_deployments(self) -> None:
        # Two recoveries: 1h and 3h → median = 2h = 7200s
        deployments = [
            _make_deployment(
                NOW - timedelta(days=1),
                status=DeploymentStatus.RECOVERED,
                failure_detected_at=NOW - timedelta(days=1, hours=2),
                recovered_at=NOW - timedelta(days=1, hours=1),  # 1h recovery
            ),
            _make_deployment(
                NOW - timedelta(days=2),
                status=DeploymentStatus.RECOVERED,
                failure_detected_at=NOW - timedelta(days=2, hours=4),
                recovered_at=NOW - timedelta(days=2, hours=1),  # 3h recovery
            ),
        ]
        calculator = DoraCalculator(FakeDeploymentRepository(deployments), FakeClock(NOW))
        result = calculator.compute("svc", period_days=30)

        assert result.mttr_p50 == pytest.approx(7200.0)

    def test_no_recovery_means_none(self) -> None:
        deployments = [
            _make_deployment(NOW - timedelta(days=1), status=DeploymentStatus.FAILED),
        ]
        calculator = DoraCalculator(FakeDeploymentRepository(deployments), FakeClock(NOW))
        result = calculator.compute("svc", period_days=30)

        assert result.mttr_p50 is None
