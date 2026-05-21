from collections.abc import Generator
from datetime import datetime, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from deploytracker.api.auth import decode_access_token
from deploytracker.application.deployment_service import DeploymentService
from deploytracker.application.dora_calculator import DoraCalculator
from deploytracker.domain.ports import Clock
from deploytracker.infrastructure.config import Settings, get_settings
from deploytracker.infrastructure.db.database import get_session
from deploytracker.infrastructure.db.repositories.deployment_repo import SqlAlchemyDeploymentRepository
from deploytracker.infrastructure.db.repositories.service_repo import SqlAlchemyServiceRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")


class _UtcClock:
    def now(self) -> datetime:
        return datetime.now(tz=timezone.utc)


def get_db_session() -> Generator[Session, None, None]:
    with get_session() as session:
        yield session


def get_current_user(
    token: str = Depends(oauth2_scheme),
    settings: Settings = Depends(get_settings),
) -> str:
    try:
        return decode_access_token(settings, token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_deployment_service(session: Session = Depends(get_db_session)) -> DeploymentService:
    deployment_repo = SqlAlchemyDeploymentRepository(session)
    service_repo = SqlAlchemyServiceRepository(session)
    clock: Clock = _UtcClock()
    return DeploymentService(deployment_repo, service_repo, clock)


def get_dora_calculator(session: Session = Depends(get_db_session)) -> DoraCalculator:
    deployment_repo = SqlAlchemyDeploymentRepository(session)
    clock: Clock = _UtcClock()
    return DoraCalculator(deployment_repo, clock)
