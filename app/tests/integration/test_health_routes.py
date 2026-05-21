import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_liveness(test_client: AsyncClient) -> None:
    response = await test_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_readiness_with_db(test_client: AsyncClient) -> None:
    response = await test_client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
