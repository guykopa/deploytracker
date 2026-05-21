# API Reference

The API is a FastAPI application. The full interactive OpenAPI UI is available at `http://<IP>:30080/docs` when the cluster is running.

---

## Base URL

```
http://<k3s_server_public_ip>:30080
```

---

## Endpoints

### Authentication

#### `POST /auth/token`

Login and receive a JWT Bearer token.

**Request** — `application/x-www-form-urlencoded`:

| Field | Required | Description |
|---|---|---|
| `username` | Yes | Admin username |
| `password` | Yes | Admin password |

**Response** `200 OK`:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error** `401 Unauthorized`:
```json
{"detail": "Invalid credentials"}
```

---

### Health

#### `GET /health/live`

Kubernetes liveness probe. Always returns 200 if the process is running.

```json
{"status": "ok"}
```

#### `GET /health/ready`

Kubernetes readiness probe. Returns 200 only if the database connection is healthy.

```json
{"status": "ok"}
```

Returns `503 Service Unavailable` if the database is unreachable.

---

### Services

All `/api/v1/*` endpoints require `Authorization: Bearer <token>`.

#### `POST /api/v1/services`

Register a new service. Idempotent — re-registering an existing service returns 200 without error.

**Request body**:
```json
{
  "name": "payment-service",
  "repository": "github.com/my-org/payment-service"
}
```

**Response** `201 Created`:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "payment-service",
  "repository": "github.com/my-org/payment-service",
  "created_at": "2026-05-21T10:00:00Z"
}
```

#### `GET /api/v1/services`

List all registered services.

**Response** `200 OK`:
```json
[
  {
    "id": "550e8400-...",
    "name": "payment-service",
    "repository": "github.com/my-org/payment-service",
    "created_at": "2026-05-21T10:00:00Z"
  }
]
```

---

### Deployments

#### `POST /api/v1/deployments`

Record a deployment event.

**Request body**:
```json
{
  "service_name": "payment-service",
  "version": "v1.4.2",
  "environment": "production",
  "commit_sha": "abc123def456",
  "deployer": "github-actions",
  "commit_timestamp": "2026-05-21T10:00:00Z",
  "deployed_at": "2026-05-21T10:30:00Z"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `service_name` | string | Yes | Must match a registered service |
| `version` | string | Yes | Git tag or semantic version |
| `environment` | string | Yes | e.g. `production`, `staging` |
| `commit_sha` | string | Yes | Full or short commit hash |
| `deployer` | string | Yes | Who/what triggered the deploy |
| `commit_timestamp` | ISO 8601 | Yes | When the commit was made |
| `deployed_at` | ISO 8601 | Yes | When the deploy completed |

**Response** `201 Created`:
```json
{
  "id": "660f9500-...",
  "service_name": "payment-service",
  "version": "v1.4.2",
  "environment": "production",
  "status": "success",
  "commit_sha": "abc123def456",
  "deployer": "github-actions",
  "commit_timestamp": "2026-05-21T10:00:00Z",
  "deployed_at": "2026-05-21T10:30:00Z",
  "failed_at": null,
  "recovered_at": null
}
```

#### `POST /api/v1/deployments/{id}/fail`

Mark a deployment as failed (e.g., triggered by a rollback or incident alert).

**Path parameter**: `id` — deployment UUID

**Response** `200 OK`: updated deployment object with `status: "failed"` and `failed_at` timestamp.

#### `POST /api/v1/deployments/{id}/recover`

Mark a failed deployment as recovered.

**Path parameter**: `id` — deployment UUID

**Response** `200 OK`: updated deployment object with `status: "recovered"` and `recovered_at` timestamp.

#### `GET /api/v1/services/{name}/deployments`

List all deployments for a service, newest first.

**Path parameter**: `name` — service name

**Response** `200 OK`: array of deployment objects.

---

### DORA Metrics

#### `GET /api/v1/services/{name}/dora`

Compute DORA metrics for a service over the last 30 days.

**Path parameter**: `name` — service name

**Response** `200 OK`:
```json
{
  "service": "payment-service",
  "period_days": 30,
  "deployment_frequency": 2.3,
  "lead_time_p50": 3600.0,
  "change_failure_rate": 0.12,
  "mttr_p50": 1800.0
}
```

| Field | Unit | Description |
|---|---|---|
| `deployment_frequency` | deployments/day | Total deployments in window ÷ 30 |
| `lead_time_p50` | seconds | Median time from commit to deploy |
| `change_failure_rate` | ratio 0–1 | Failed deploys ÷ total deploys |
| `mttr_p50` | seconds | Median time from failure to recovery |

Returns `404 Not Found` if the service does not exist.

---

## Error responses

| Status | Meaning |
|---|---|
| `400 Bad Request` | Invalid request body (validation error) |
| `401 Unauthorized` | Missing, invalid, or expired JWT |
| `404 Not Found` | Service or deployment not found |
| `422 Unprocessable Entity` | FastAPI validation failure (field type mismatch, etc.) |
| `503 Service Unavailable` | Database unreachable (readiness probe only) |
