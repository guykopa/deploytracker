from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from .models import DeploymentStatus


class CreateServiceRequest(BaseModel):
    name: str
    team: str


class ServiceResponse(BaseModel):
    name: str
    team: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CreateDeploymentRequest(BaseModel):
    service_name: str
    version: str
    environment: str
    commit_sha: str
    deployer: str
    commit_timestamp: datetime
    deployed_at: datetime


class MarkFailureRequest(BaseModel):
    failure_detected_at: datetime
    reason: str


class MarkRecoveryRequest(BaseModel):
    recovered_at: datetime


class DeploymentResponse(BaseModel):
    id: UUID
    service_name: str
    version: str
    environment: str
    commit_sha: str
    deployer: str
    commit_timestamp: datetime
    deployed_at: datetime
    status: DeploymentStatus
    failure_detected_at: datetime | None
    recovered_at: datetime | None
    lead_time_seconds: int
    recovery_time_seconds: int | None

    model_config = {"from_attributes": True}


class DoraMetrics(BaseModel):
    deployment_frequency: float
    lead_time_p50: float
    change_failure_rate: float
    mttr_p50: float | None
    period_days: int
    service: str
