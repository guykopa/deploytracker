from fastapi import APIRouter
from fastapi.responses import JSONResponse

from deploytracker.infrastructure.db.database import check_connection

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def readiness() -> JSONResponse:
    if check_connection():
        return JSONResponse(status_code=200, content={"status": "ok"})
    return JSONResponse(status_code=503, content={"status": "unavailable", "detail": "database unreachable"})
