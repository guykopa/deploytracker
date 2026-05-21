import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from deploytracker.domain.exceptions import (
    DeploymentNotFound,
    ServiceAlreadyExists,
    ServiceNotFound,
)
from deploytracker.infrastructure.config import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()

    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

    from deploytracker.infrastructure.db.database import init_engine
    engine = init_engine(settings)

    try:
        from deploytracker.infrastructure.telemetry.otel_setup import setup_telemetry
        setup_telemetry(app, settings, engine=engine)
    except Exception as exc:
        logger.warning("Telemetry setup failed (continuing without it): %s", exc)

    logger.info("DeployTracker started", extra={"env": settings.env})
    yield
    logger.info("DeployTracker shutting down")


app = FastAPI(title="DeployTracker", version="0.1.0", lifespan=lifespan)

from deploytracker.api.routes import auth, deployments, health, services  # noqa: E402

app.include_router(auth.router)
app.include_router(health.router)
app.include_router(services.router)
app.include_router(deployments.router)


@app.exception_handler(DeploymentNotFound)
async def deployment_not_found_handler(request: Request, exc: DeploymentNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ServiceNotFound)
async def service_not_found_handler(request: Request, exc: ServiceNotFound) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ServiceAlreadyExists)
async def service_already_exists_handler(request: Request, exc: ServiceAlreadyExists) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc)})
