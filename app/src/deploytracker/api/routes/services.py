from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from deploytracker.api.dependencies import get_current_user
from deploytracker.domain.models import Service
from deploytracker.domain.schemas import CreateServiceRequest, ServiceResponse
from deploytracker.infrastructure.db.database import get_session
from deploytracker.infrastructure.db.repositories.service_repo import SqlAlchemyServiceRepository

router = APIRouter(prefix="/api/v1/services", tags=["services"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ServiceResponse)
def create_service(
    body: CreateServiceRequest,
    current_user: str = Depends(get_current_user),
) -> ServiceResponse:
    with get_session() as session:
        repo = SqlAlchemyServiceRepository(session)
        if repo.get(body.name) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Service '{body.name}' already exists",
            )
        service = Service(name=body.name, team=body.team, created_at=datetime.now(tz=timezone.utc))
        saved = repo.save(service)
        return ServiceResponse(name=saved.name, team=saved.team, created_at=saved.created_at)


@router.get("", response_model=list[ServiceResponse])
def list_services(current_user: str = Depends(get_current_user)) -> list[ServiceResponse]:
    with get_session() as session:
        repo = SqlAlchemyServiceRepository(session)
        services = repo.list_all()
        return [ServiceResponse(name=s.name, team=s.team, created_at=s.created_at) for s in services]
