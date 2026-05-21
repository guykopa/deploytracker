from uuid import UUID

from .models import DeploymentStatus


class DeploymentNotFound(Exception):
    def __init__(self, deployment_id: UUID) -> None:
        super().__init__(f"Deployment {deployment_id} not found")
        self.deployment_id = deployment_id


class ServiceNotFound(Exception):
    def __init__(self, service_name: str) -> None:
        super().__init__(f"Service '{service_name}' not found")
        self.service_name = service_name


class ServiceAlreadyExists(Exception):
    def __init__(self, service_name: str) -> None:
        super().__init__(f"Service '{service_name}' already exists")
        self.service_name = service_name


class InvalidStatusTransition(Exception):
    def __init__(self, from_status: DeploymentStatus, to_status: DeploymentStatus) -> None:
        super().__init__(f"Cannot transition from {from_status} to {to_status}")
        self.from_status = from_status
        self.to_status = to_status
