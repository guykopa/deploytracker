from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from deploytracker.application.deployment_service import DeploymentService
from deploytracker.domain.exceptions import DeploymentNotFound, ServiceNotFound
from deploytracker.domain.models import Deployment, DeploymentStatus, Service
from deploytracker.domain.schemas import (
    CreateDeploymentRequest,
    MarkFailureRequest,
    MarkRecoveryRequest,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeServiceRepository:
    def __init__(self) -> None:
        self._store: dict[str, Service] = {}

    def save(self, service: Service) -> Service:
        self._store[service.name] = service
        return service

    def get(self, name: str) -> Service | None:
        return self._store.get(name)

    def list_all(self) -> list[Service]:
        return list(self._store.values())


class FakeDeploymentRepository:
    def __init__(self) -> None:
        self._store: dict[UUID, Deployment] = {}

    def save(self, deployment: Deployment) -> Deployment:
        self._store[deployment.id] = deployment
        return deployment

    def get(self, deployment_id: UUID) -> Deployment | None:
        return self._store.get(deployment_id)

    def list_by_service(self, service: str, since: datetime) -> list[Deployment]:
        return [d for d in self._store.values() if d.service_name == service and d.deployed_at >= since]

    def update(self, deployment: Deployment) -> Deployment:
        self._store[deployment.id] = deployment
        return deployment


class FakeClock:
    def __init__(self, fixed: datetime) -> None:
        self._now = fixed

    def now(self) -> datetime:
        return self._now


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def service_repo() -> FakeServiceRepository:
    repo = FakeServiceRepository()
    repo.save(Service(name="my-service", team="platform", created_at=datetime(2024, 1, 1, tzinfo=timezone.utc)))
    return repo


@pytest.fixture()
def deployment_repo() -> FakeDeploymentRepository:
    return FakeDeploymentRepository()


@pytest.fixture()
def clock() -> FakeClock:
    return FakeClock(fixed=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc))


@pytest.fixture()
def svc(
    deployment_repo: FakeDeploymentRepository,
    service_repo: FakeServiceRepository,
    clock: FakeClock,
) -> DeploymentService:
    return DeploymentService(deployment_repo, service_repo, clock)


def _make_request(**overrides: object) -> CreateDeploymentRequest:
    base: dict[str, object] = dict(
        service_name="my-service",
        version="1.2.3",
        environment="production",
        commit_sha="deadbeef",
        deployer="alice",
        commit_timestamp=datetime(2024, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
        deployed_at=datetime(2024, 6, 1, 11, 0, 0, tzinfo=timezone.utc),
    )
    base.update(overrides)
    return CreateDeploymentRequest(**base)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRecordDeployment:
    def test_creates_deployment_with_correct_fields(
        self, svc: DeploymentService, deployment_repo: FakeDeploymentRepository
    ) -> None:
        req = _make_request()
        result = svc.record_deployment(req)

        assert result.service_name == "my-service"
        assert result.version == "1.2.3"
        assert result.status == DeploymentStatus.SUCCESS
        assert result.lead_time_seconds == 3600
        assert len(deployment_repo._store) == 1

    def test_raises_service_not_found(self, svc: DeploymentService) -> None:
        req = _make_request(service_name="unknown-service")
        with pytest.raises(ServiceNotFound):
            svc.record_deployment(req)


class TestMarkFailure:
    def test_transitions_status_to_failed(
        self, svc: DeploymentService, deployment_repo: FakeDeploymentRepository
    ) -> None:
        deployment = svc.record_deployment(_make_request())
        failure_req = MarkFailureRequest(
            failure_detected_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
            reason="OOM",
        )
        updated = svc.mark_failure(deployment.id, failure_req)

        assert updated.status == DeploymentStatus.FAILED
        assert updated.failure_detected_at == failure_req.failure_detected_at

    def test_raises_deployment_not_found(self, svc: DeploymentService) -> None:
        with pytest.raises(DeploymentNotFound):
            svc.mark_failure(
                uuid4(),
                MarkFailureRequest(
                    failure_detected_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
                    reason="crash",
                ),
            )


class TestMarkRecovery:
    def test_transitions_status_to_recovered(self, svc: DeploymentService) -> None:
        deployment = svc.record_deployment(_make_request())
        svc.mark_failure(
            deployment.id,
            MarkFailureRequest(
                failure_detected_at=datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc),
                reason="crash",
            ),
        )
        recovered = svc.mark_recovery(
            deployment.id,
            MarkRecoveryRequest(recovered_at=datetime(2024, 6, 1, 13, 0, 0, tzinfo=timezone.utc)),
        )

        assert recovered.status == DeploymentStatus.RECOVERED
        assert recovered.recovered_at == datetime(2024, 6, 1, 13, 0, 0, tzinfo=timezone.utc)
        assert recovered.recovery_time_seconds == 3600

    def test_raises_deployment_not_found(self, svc: DeploymentService) -> None:
        with pytest.raises(DeploymentNotFound):
            svc.mark_recovery(
                uuid4(),
                MarkRecoveryRequest(recovered_at=datetime(2024, 6, 1, 13, 0, 0, tzinfo=timezone.utc)),
            )
