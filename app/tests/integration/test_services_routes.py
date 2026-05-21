import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_service_returns_201(test_client: AsyncClient) -> None:
    response = await test_client.post(
        "/api/v1/services",
        json={"name": "my-service", "team": "platform"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "my-service"
    assert data["team"] == "platform"
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_duplicate_service_returns_409(test_client: AsyncClient) -> None:
    payload = {"name": "duplicate-svc", "team": "ops"}
    await test_client.post("/api/v1/services", json=payload)
    response = await test_client.post("/api/v1/services", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_services(test_client: AsyncClient) -> None:
    await test_client.post("/api/v1/services", json={"name": "svc-a", "team": "team-a"})
    await test_client.post("/api/v1/services", json={"name": "svc-b", "team": "team-b"})

    response = await test_client.get("/api/v1/services")
    assert response.status_code == 200
    names = [s["name"] for s in response.json()]
    assert "svc-a" in names
    assert "svc-b" in names
