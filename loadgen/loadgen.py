#!/usr/bin/env python3
"""Load generator — simulates CI/CD pipeline deployment events."""
import os
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests

API_URL = os.getenv("DEPLOYTRACKER_API_URL", "http://deploytracker.deploytracker.svc.cluster.local:8000")
ADMIN_USERNAME = os.getenv("DEPLOYTRACKER_ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.getenv("DEPLOYTRACKER_ADMIN_PASSWORD", "change-me")
SERVICES = ["payment-service", "auth-service", "notification-service", "api-gateway", "user-service"]
ENVIRONMENTS = ["dev", "staging", "production"]
DEPLOYERS = ["github-actions", "ci-bot"]
INTERVAL_SECONDS = int(os.getenv("LOADGEN_INTERVAL_SECONDS", "60"))
FAILURE_RATE = float(os.getenv("LOADGEN_FAILURE_RATE", "0.1"))

_token: str | None = None


def get_token() -> str:
    global _token
    resp = requests.post(
        f"{API_URL}/auth/token",
        data={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
        timeout=10,
    )
    resp.raise_for_status()
    _token = resp.json()["access_token"]
    return _token


def auth_headers() -> dict[str, str]:
    token = _token or get_token()
    return {"Authorization": f"Bearer {token}"}


def ensure_services() -> None:
    teams = {
        "payment-service": "billing",
        "auth-service": "platform",
        "notification-service": "comms",
        "api-gateway": "platform",
        "user-service": "identity",
    }
    for svc, team in teams.items():
        try:
            requests.post(
                f"{API_URL}/api/v1/services",
                json={"name": svc, "team": team},
                headers=auth_headers(),
                timeout=10,
            )
        except Exception:
            pass


def simulate_deployment() -> None:
    service = random.choice(SERVICES)
    env = random.choice(ENVIRONMENTS)
    now = datetime.now(timezone.utc)
    commit_time = now - timedelta(minutes=random.randint(10, 480))

    payload = {
        "service_name": service,
        "version": f"v{random.randint(1, 5)}.{random.randint(0, 20)}.{random.randint(0, 10)}",
        "environment": env,
        "commit_sha": uuid.uuid4().hex[:40],
        "deployer": random.choice(DEPLOYERS),
        "commit_timestamp": commit_time.isoformat(),
        "deployed_at": now.isoformat(),
    }

    resp = requests.post(f"{API_URL}/api/v1/deployments", json=payload, headers=auth_headers(), timeout=10)
    if resp.status_code == 401:
        get_token()
        resp = requests.post(f"{API_URL}/api/v1/deployments", json=payload, headers=auth_headers(), timeout=10)
    if resp.status_code != 201:
        return

    deployment_id = resp.json()["id"]

    if random.random() < FAILURE_RATE:
        fail_time = now + timedelta(minutes=random.randint(1, 30))
        requests.post(
            f"{API_URL}/api/v1/deployments/{deployment_id}/fail",
            json={
                "failure_detected_at": fail_time.isoformat(),
                "reason": "Automated failure simulation",
            },
            headers=auth_headers(),
            timeout=10,
        )

        if random.random() < 0.8:
            recover_time = fail_time + timedelta(minutes=random.randint(5, 120))
            requests.post(
                f"{API_URL}/api/v1/deployments/{deployment_id}/recover",
                json={"recovered_at": recover_time.isoformat()},
                headers=auth_headers(),
                timeout=10,
            )


def main() -> None:
    print(f"Starting load generator — API: {API_URL}, interval: {INTERVAL_SECONDS}s, failure rate: {FAILURE_RATE}")
    time.sleep(30)
    print("Ensuring services exist...")
    ensure_services()
    print("Starting deployment simulation loop...")
    while True:
        try:
            simulate_deployment()
        except Exception as exc:
            print(f"Error during deployment simulation: {exc}")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
