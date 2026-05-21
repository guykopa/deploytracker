from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient


async def _create_service(client: AsyncClient, name: str = "my-service", team: str = "platform") -> None:
    await client.post("/api/v1/services", json={"name": name, "team": team})


def _deployment_payload(service_name: str = "my-service") -> dict[str, object]:
    now = datetime.now(timezone.utc)
    return {
        "service_name": service_name,
        "version": "1.0.0",
        "environment": "production",
        "commit_sha": "abc123def456",
        "deployer": "alice",
        "commit_timestamp": (now - timedelta(hours=1)).isoformat(),
        "deployed_at": now.isoformat(),
    }


@pytest.mark.asyncio
async def test_create_deployment_returns_201(test_client: AsyncClient) -> None:
    await _create_service(test_client)
    response = await test_client.post("/api/v1/deployments", json=_deployment_payload())

    assert response.status_code == 201
    data = response.json()
    assert data["service_name"] == "my-service"
    assert data["status"] == "success"
    assert data["lead_time_seconds"] == 3600
    assert data["recovery_time_seconds"] is None
    assert "id" in data


@pytest.mark.asyncio
async def test_create_deployment_unknown_service_returns_404(test_client: AsyncClient) -> None:
    response = await test_client.post("/api/v1/deployments", json=_deployment_payload("ghost-service"))
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_mark_failure_returns_200(test_client: AsyncClient) -> None:
    await _create_service(test_client)
    created = (await test_client.post("/api/v1/deployments", json=_deployment_payload())).json()
    dep_id = created["id"]

    now = datetime.now(timezone.utc)
    response = await test_client.post(
        f"/api/v1/deployments/{dep_id}/fail",
        json={"failure_detected_at": now.isoformat(), "reason": "OOM"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "failed"


@pytest.mark.asyncio
async def test_mark_recovery_returns_200(test_client: AsyncClient) -> None:
    await _create_service(test_client)
    created = (await test_client.post("/api/v1/deployments", json=_deployment_payload())).json()
    dep_id = created["id"]

    now = datetime.now(timezone.utc)
    await test_client.post(
        f"/api/v1/deployments/{dep_id}/fail",
        json={"failure_detected_at": now.isoformat(), "reason": "OOM"},
    )
    response = await test_client.post(
        f"/api/v1/deployments/{dep_id}/recover",
        json={"recovered_at": (now + timedelta(hours=1)).isoformat()},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "recovered"
    assert data["recovery_time_seconds"] == 3600


@pytest.mark.asyncio
async def test_list_deployments(test_client: AsyncClient) -> None:
    await _create_service(test_client)
    await test_client.post("/api/v1/deployments", json=_deployment_payload())

    response = await test_client.get("/api/v1/services/my-service/deployments")
    assert response.status_code == 200
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_get_dora_metrics(test_client: AsyncClient) -> None:
    await _create_service(test_client)
    await test_client.post("/api/v1/deployments", json=_deployment_payload())

    response = await test_client.get("/api/v1/services/my-service/dora")
    assert response.status_code == 200
    data = response.json()
    assert "deployment_frequency" in data
    assert "lead_time_p50" in data
    assert "change_failure_rate" in data
    assert data["service"] == "my-service"
    assert data["period_days"] == 30
