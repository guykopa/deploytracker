# Authentication

All `/api/v1/*` endpoints require a **JWT Bearer token**. The following endpoints are public (no token needed):

| Endpoint | Reason |
|---|---|
| `POST /auth/token` | Login — this is where you get the token |
| `GET /health/live` | Kubernetes liveness probe |
| `GET /health/ready` | Kubernetes readiness probe |
| `GET /docs` | OpenAPI UI |

---

## Getting a token

```bash
curl -s -X POST http://<IP>:30080/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin&password=<ADMIN_PASSWORD>"
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

---

## Using the token

```bash
curl -H "Authorization: Bearer eyJhbG..." http://<IP>:30080/api/v1/services
```

Tokens expire after **60 minutes** (configurable via `DEPLOYTRACKER_JWT_EXPIRY_MINUTES`).

---

## Token structure

```json
{
  "sub": "admin",
  "exp": 1748000000
}
```

The token is signed with HS256 using the `DEPLOYTRACKER_JWT_SECRET_KEY` environment variable (a 32-byte hex string). There are no roles or scopes — the token is binary: valid admin or nothing.

---

## Configuration

All auth parameters are loaded from environment variables (sourced from the `deploytracker-secrets` Kubernetes secret in production, from `app/.env` in local development):

| Variable | Description | Default |
|---|---|---|
| `DEPLOYTRACKER_ADMIN_USERNAME` | Admin login username | `admin` |
| `DEPLOYTRACKER_ADMIN_PASSWORD` | Admin password | *(must be set — no default)* |
| `DEPLOYTRACKER_JWT_SECRET_KEY` | HS256 signing key (hex, 32 bytes) | *(must be set — no default)* |
| `DEPLOYTRACKER_JWT_ALGORITHM` | Signing algorithm | `HS256` |
| `DEPLOYTRACKER_JWT_EXPIRY_MINUTES` | Token TTL in minutes | `60` |

---

## Full example (CI/CD pipeline)

```bash
# 1. Fetch a token
TOKEN=$(curl -s -X POST http://$DEPLOY_API_URL/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$DEPLOYTRACKER_ADMIN_USERNAME&password=$DEPLOYTRACKER_ADMIN_PASSWORD" \
  | jq -r .access_token)

# 2. Register the service (idempotent)
curl -s -X POST http://$DEPLOY_API_URL/api/v1/services \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-service", "repository": "github.com/org/my-service"}'

# 3. Record the deployment
curl -s -X POST http://$DEPLOY_API_URL/api/v1/deployments \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"service_name\": \"my-service\",
    \"version\": \"$IMAGE_TAG\",
    \"environment\": \"production\",
    \"commit_sha\": \"$GITHUB_SHA\",
    \"deployer\": \"github-actions\",
    \"commit_timestamp\": \"$COMMIT_TIMESTAMP\",
    \"deployed_at\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
  }"
```

---

## How it works (implementation)

```
Client                           API                         K8s Secret
  │                                │                              │
  │── POST /auth/token ──────────→ │                              │
  │   username + password          │── read ADMIN_USERNAME ──────→│
  │   (form-encoded)               │   read ADMIN_PASSWORD        │
  │                                │── read JWT_SECRET_KEY ───────│
  │                                │                              │
  │                                │  verify credentials          │
  │                                │  create JWT: {sub, exp}      │
  │                                │  sign with HS256             │
  │← access_token ────────────────│                              │
  │                                │                              │
  │── GET /api/v1/services ──────→ │                              │
  │   Authorization: Bearer <tok>  │── read JWT_SECRET_KEY ───────│
  │                                │  verify signature + expiry   │
  │← 200 ─────────────────────────│                              │
```

On failure, the API returns:
- `401 Unauthorized` with `WWW-Authenticate: Bearer` header for missing, invalid, or expired tokens
- `401 Unauthorized` with `detail: "Invalid credentials"` for wrong username/password at login

Key source files:

| File | Responsibility |
|---|---|
| `app/src/deploytracker/api/auth.py` | `create_access_token()`, `decode_access_token()` |
| `app/src/deploytracker/api/routes/auth.py` | `POST /auth/token` route |
| `app/src/deploytracker/api/dependencies.py` | `get_current_user()` FastAPI dependency |

See [ADR-005](adr/005-jwt-authentication.md) for the full decision rationale.
