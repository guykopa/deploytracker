from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from deploytracker.domain.models import Deployment, DeploymentStatus
from deploytracker.infrastructure.db.orm_models import DeploymentORM


def _orm_to_domain(orm: DeploymentORM) -> Deployment:
    return Deployment(
        id=orm.id,
        service_name=orm.service_name,
        version=orm.version,
        environment=orm.environment,
        commit_sha=orm.commit_sha,
        deployer=orm.deployer,
        commit_timestamp=orm.commit_timestamp,
        deployed_at=orm.deployed_at,
        status=DeploymentStatus(orm.status),
        failure_detected_at=orm.failure_detected_at,
        recovered_at=orm.recovered_at,
    )


def _domain_to_orm(deployment: Deployment, existing: DeploymentORM | None = None) -> DeploymentORM:
    if existing is None:
        existing = DeploymentORM()
    existing.id = deployment.id
    existing.service_name = deployment.service_name
    existing.version = deployment.version
    existing.environment = deployment.environment
    existing.commit_sha = deployment.commit_sha
    existing.deployer = deployment.deployer
    existing.commit_timestamp = deployment.commit_timestamp
    existing.deployed_at = deployment.deployed_at
    existing.status = deployment.status.value
    existing.failure_detected_at = deployment.failure_detected_at
    existing.recovered_at = deployment.recovered_at
    return existing


class SqlAlchemyDeploymentRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, deployment: Deployment) -> Deployment:
        orm = _domain_to_orm(deployment)
        self._session.add(orm)
        self._session.flush()
        return _orm_to_domain(orm)

    def get(self, deployment_id: UUID) -> Deployment | None:
        orm = self._session.get(DeploymentORM, deployment_id)
        if orm is None:
            return None
        return _orm_to_domain(orm)

    def list_by_service(self, service: str, since: datetime) -> list[Deployment]:
        rows = (
            self._session.query(DeploymentORM)
            .filter(
                DeploymentORM.service_name == service,
                DeploymentORM.deployed_at >= since,
            )
            .order_by(DeploymentORM.deployed_at.desc())
            .all()
        )
        return [_orm_to_domain(r) for r in rows]

    def update(self, deployment: Deployment) -> Deployment:
        orm = self._session.get(DeploymentORM, deployment.id)
        if orm is None:
            raise ValueError(f"Deployment {deployment.id} not found for update")
        _domain_to_orm(deployment, existing=orm)
        self._session.flush()
        return _orm_to_domain(orm)
