from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID


class DeploymentStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    RECOVERED = "recovered"


@dataclass
class Service:
    name: str
    team: str
    created_at: datetime


@dataclass
class Deployment:
    id: UUID
    service_name: str
    version: str
    environment: str
    commit_sha: str
    deployer: str
    commit_timestamp: datetime
    deployed_at: datetime
    status: DeploymentStatus = DeploymentStatus.SUCCESS
    failure_detected_at: datetime | None = None
    recovered_at: datetime | None = None

    @property
    def lead_time_seconds(self) -> int:
        return int((self.deployed_at - self.commit_timestamp).total_seconds())

    @property
    def recovery_time_seconds(self) -> int | None:
        if self.failure_detected_at and self.recovered_at:
            return int((self.recovered_at - self.failure_detected_at).total_seconds())
        return None
