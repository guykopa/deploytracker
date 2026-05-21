import time
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from deploytracker.api.dependencies import get_current_user, get_deployment_service, get_dora_calculator
from deploytracker.application.deployment_service import DeploymentService
from deploytracker.application.dora_calculator import DoraCalculator
from deploytracker.domain.exceptions import (
    DeploymentNotFound,
    InvalidStatusTransition,
    ServiceNotFound,
)
from deploytracker.domain.models import Deployment
from deploytracker.domain.schemas import (
    CreateDeploymentRequest,
    DeploymentResponse,
    DoraMetrics,
    MarkFailureRequest,
    MarkRecoveryRequest,
)

router = APIRouter(prefix="/api/v1", tags=["deployments"])


def _deployment_response(d: Deployment) -> DeploymentResponse:
    return DeploymentResponse(
        id=d.id,
        service_name=d.service_name,
        version=d.version,
        environment=d.environment,
        commit_sha=d.commit_sha,
        deployer=d.deployer,
        commit_timestamp=d.commit_timestamp,
        deployed_at=d.deployed_at,
        status=d.status,
        failure_detected_at=d.failure_detected_at,
        recovered_at=d.recovered_at,
        lead_time_seconds=d.lead_time_seconds,
        recovery_time_seconds=d.recovery_time_seconds,
    )


@router.post("/deployments", status_code=status.HTTP_201_CREATED, response_model=DeploymentResponse)
def create_deployment(
    body: CreateDeploymentRequest,
    service: DeploymentService = Depends(get_deployment_service),
    current_user: str = Depends(get_current_user),
) -> DeploymentResponse:
    try:
        deployment = service.record_deployment(body)
    except ServiceNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _deployment_response(deployment)


@router.post("/deployments/{deployment_id}/fail", response_model=DeploymentResponse)
def mark_failure(
    deployment_id: UUID,
    body: MarkFailureRequest,
    service: DeploymentService = Depends(get_deployment_service),
    current_user: str = Depends(get_current_user),
) -> DeploymentResponse:
    try:
        deployment = service.mark_failure(deployment_id, body)
    except DeploymentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidStatusTransition as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _deployment_response(deployment)


@router.post("/deployments/{deployment_id}/recover", response_model=DeploymentResponse)
def mark_recovery(
    deployment_id: UUID,
    body: MarkRecoveryRequest,
    service: DeploymentService = Depends(get_deployment_service),
    current_user: str = Depends(get_current_user),
) -> DeploymentResponse:
    try:
        deployment = service.mark_recovery(deployment_id, body)
    except DeploymentNotFound as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except InvalidStatusTransition as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _deployment_response(deployment)


@router.get("/services/{service_name}/deployments", response_model=list[DeploymentResponse])
def list_deployments(
    service_name: str,
    since_days: int = Query(default=30, ge=1, le=365),
    svc: DeploymentService = Depends(get_deployment_service),
    current_user: str = Depends(get_current_user),
) -> list[DeploymentResponse]:
    since = datetime.now(tz=timezone.utc) - timedelta(days=since_days)
    deployments = svc.list_deployments(service_name, since=since)
    return [_deployment_response(d) for d in deployments]


@router.get("/services/{service_name}/dora", response_model=DoraMetrics)
def get_dora_metrics(
    service_name: str,
    period_days: int = Query(default=30, ge=1, le=365),
    calculator: DoraCalculator = Depends(get_dora_calculator),
    current_user: str = Depends(get_current_user),
) -> DoraMetrics:
    start = time.perf_counter()
    result = calculator.compute(service_name, period_days)

    try:
        from deploytracker.infrastructure.telemetry.metrics import record_dora_compute_duration
        record_dora_compute_duration(service_name, time.perf_counter() - start)
    except Exception:
        pass

    return DoraMetrics(
        deployment_frequency=result.deployment_frequency,
        lead_time_p50=result.lead_time_p50,
        change_failure_rate=result.change_failure_rate,
        mttr_p50=result.mttr_p50,
        period_days=result.period_days,
        service=result.service,
    )
