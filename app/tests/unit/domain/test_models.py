from datetime import datetime, timedelta, timezone
from uuid import uuid4

from deploytracker.domain.models import Deployment, DeploymentStatus


def _make_deployment(**kwargs: object) -> Deployment:
    base = dict(
        id=uuid4(),
        service_name="svc",
        version="1.0.0",
        environment="production",
        commit_sha="abc123",
        deployer="alice",
        commit_timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
        deployed_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
        status=DeploymentStatus.SUCCESS,
    )
    base.update(kwargs)
    return Deployment(**base)  # type: ignore[arg-type]


class TestLeadTimeSeconds:
    def test_one_hour_lead_time(self) -> None:
        d = _make_deployment(
            commit_timestamp=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            deployed_at=datetime(2024, 1, 1, 13, 0, 0, tzinfo=timezone.utc),
        )
        assert d.lead_time_seconds == 3600

    def test_zero_lead_time(self) -> None:
        ts = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        d = _make_deployment(commit_timestamp=ts, deployed_at=ts)
        assert d.lead_time_seconds == 0

    def test_fractional_seconds_are_truncated(self) -> None:
        base = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        d = _make_deployment(
            commit_timestamp=base,
            deployed_at=base + timedelta(seconds=90, microseconds=500000),
        )
        assert d.lead_time_seconds == 90


class TestRecoveryTimeSeconds:
    def test_normal_recovery(self) -> None:
        d = _make_deployment(
            status=DeploymentStatus.RECOVERED,
            failure_detected_at=datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
            recovered_at=datetime(2024, 1, 1, 14, 30, 0, tzinfo=timezone.utc),
        )
        assert d.recovery_time_seconds == 1800

    def test_no_failure_detected_returns_none(self) -> None:
        d = _make_deployment(
            status=DeploymentStatus.SUCCESS,
            failure_detected_at=None,
            recovered_at=None,
        )
        assert d.recovery_time_seconds is None

    def test_failure_without_recovery_returns_none(self) -> None:
        d = _make_deployment(
            status=DeploymentStatus.FAILED,
            failure_detected_at=datetime(2024, 1, 1, 14, 0, 0, tzinfo=timezone.utc),
            recovered_at=None,
        )
        assert d.recovery_time_seconds is None
