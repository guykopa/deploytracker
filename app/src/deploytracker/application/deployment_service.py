import logging
import uuid
from datetime import datetime

from deploytracker.domain.exceptions import (
    DeploymentNotFound,
    InvalidStatusTransition,
    ServiceNotFound,
)
from deploytracker.domain.models import Deployment, DeploymentStatus
from deploytracker.domain.ports import Clock, DeploymentRepository, ServiceRepository
from deploytracker.domain.schemas import (
    CreateDeploymentRequest,
    MarkFailureRequest,
    MarkRecoveryRequest,
)

logger = logging.getLogger(__name__)

# Valid status transitions: what transitions are allowed
_ALLOWED_TRANSITIONS: dict[DeploymentStatus, set[DeploymentStatus]] = {
    DeploymentStatus.SUCCESS: {DeploymentStatus.FAILED},
    DeploymentStatus.FAILED: {DeploymentStatus.RECOVERED},
    DeploymentStatus.RECOVERED: set(),
}


class DeploymentService:
    def __init__(
        self,
        deployment_repo: DeploymentRepository,
        service_repo: ServiceRepository,
        clock: Clock,
        metrics: object | None = None,
    ) -> None:
        self._deployment_repo = deployment_repo
        self._service_repo = service_repo
        self._clock = clock
        self._metrics = metrics

    def record_deployment(self, dto: CreateDeploymentRequest) -> Deployment:
        service = self._service_repo.get(dto.service_name)
        if service is None:
            raise ServiceNotFound(dto.service_name)

        deployment = Deployment(
            id=uuid.uuid4(),
            service_name=dto.service_name,
            version=dto.version,
            environment=dto.environment,
            commit_sha=dto.commit_sha,
            deployer=dto.deployer,
            commit_timestamp=dto.commit_timestamp,
            deployed_at=dto.deployed_at,
            status=DeploymentStatus.SUCCESS,
        )
        saved = self._deployment_repo.save(deployment)

        logger.info(
            "deployment_recorded",
            extra={
                "deployment_id": str(saved.id),
                "service": saved.service_name,
                "version": saved.version,
                "environment": saved.environment,
                "lead_time_seconds": saved.lead_time_seconds,
            },
        )

        if self._metrics is not None:
            self._emit_deployment_metrics(saved)

        return saved

    def mark_failure(self, deployment_id: uuid.UUID, request: MarkFailureRequest) -> Deployment:
        deployment = self._deployment_repo.get(deployment_id)
        if deployment is None:
            raise DeploymentNotFound(deployment_id)

        allowed = _ALLOWED_TRANSITIONS[deployment.status]
        if DeploymentStatus.FAILED not in allowed:
            raise InvalidStatusTransition(deployment.status, DeploymentStatus.FAILED)

        deployment.status = DeploymentStatus.FAILED
        deployment.failure_detected_at = request.failure_detected_at
        updated = self._deployment_repo.update(deployment)

        logger.info(
            "deployment_failed",
            extra={
                "deployment_id": str(updated.id),
                "service": updated.service_name,
                "reason": request.reason,
            },
        )

        return updated

    def mark_recovery(self, deployment_id: uuid.UUID, request: MarkRecoveryRequest) -> Deployment:
        deployment = self._deployment_repo.get(deployment_id)
        if deployment is None:
            raise DeploymentNotFound(deployment_id)

        allowed = _ALLOWED_TRANSITIONS[deployment.status]
        if DeploymentStatus.RECOVERED not in allowed:
            raise InvalidStatusTransition(deployment.status, DeploymentStatus.RECOVERED)

        deployment.status = DeploymentStatus.RECOVERED
        deployment.recovered_at = request.recovered_at
        updated = self._deployment_repo.update(deployment)

        logger.info(
            "deployment_recovered",
            extra={
                "deployment_id": str(updated.id),
                "service": updated.service_name,
                "mttr_seconds": updated.recovery_time_seconds,
            },
        )

        return updated

    def list_deployments(self, service_name: str, since: datetime) -> list[Deployment]:
        return self._deployment_repo.list_by_service(service_name, since=since)

    def _emit_deployment_metrics(self, deployment: Deployment) -> None:
        # Import here to avoid hard dependency at module load time.
        # The metrics object passed in is the preferred path; this is a fallback.
        try:
            from deploytracker.infrastructure.telemetry.metrics import (
                record_deployment,
                record_lead_time,
            )
            record_deployment(deployment.service_name, deployment.environment, deployment.status.value)
            record_lead_time(deployment.service_name, deployment.lead_time_seconds)
        except ImportError:
            pass
