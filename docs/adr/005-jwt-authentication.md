# ADR-005: JWT Authentication for the REST API

**Date:** 2026-05-21
**Status:** Accepted

## Context

The deploytracker API exposes endpoints that create and mutate deployment records (`POST /api/v1/deployments`, `POST /api/v1/services`, etc.). Without authentication, any process that can reach the NodePort (port 30080) can inject arbitrary deployment events, corrupting DORA metrics.

The API is consumed by:
1. CI/CD pipelines (GitHub Actions) — automated, non-interactive
2. The load generator pod (internal cluster traffic)
3. Human operators via curl or the Swagger UI

Requirements:
- Stateless — no server-side session storage
- Simple to use from shell scripts and CI pipelines (standard Bearer token)
- Does not require an external identity provider (no Cognito, no OIDC in the demo)
- Credentials must not be stored in code or Helm values — they must come from secrets

## Decision

Implement **JWT Bearer token authentication** using **PyJWT** (HS256 symmetric signing).

### Flow

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

### Token structure

```json
{
  "sub": "admin",
  "exp": 1234567890
}
```

No roles, no scopes — the token is binary (valid admin or nothing). Fine for a single-user demo.

### Configuration

All auth parameters come from environment variables (loaded from Kubernetes secret `deploytracker-secrets` via `envFrom`):

| Variable | Description | Default |
|---|---|---|
| `DEPLOYTRACKER_ADMIN_USERNAME` | Admin login | `admin` |
| `DEPLOYTRACKER_ADMIN_PASSWORD` | Admin password | *(no default — must be set)* |
| `DEPLOYTRACKER_JWT_SECRET_KEY` | HS256 signing key (hex, 32 bytes) | *(no default)* |
| `DEPLOYTRACKER_JWT_ALGORITHM` | Algorithm | `HS256` |
| `DEPLOYTRACKER_JWT_EXPIRY_MINUTES` | Token TTL | `60` |

In local development these come from `app/.env` (gitignored).

### Protected vs public endpoints

| Endpoint | Auth required |
|---|---|
| `POST /auth/token` | No (it's the login endpoint) |
| `GET /health/live` | No (liveness probe must work without a token) |
| `GET /health/ready` | No |
| `GET /docs` | No |
| All `/api/v1/*` | **Yes — Bearer JWT** |

### Implementation

```
api/auth.py          — create_access_token(), decode_access_token()
api/routes/auth.py   — POST /auth/token route
api/dependencies.py  — oauth2_scheme, get_current_user() dependency
api/routes/*.py      — current_user: str = Depends(get_current_user)
```

`get_current_user` raises HTTP 401 with `WWW-Authenticate: Bearer` on:
- Missing token
- Invalid signature
- Expired token

## Alternatives Considered

### No authentication

Rejected: the API is reachable on a public IP (NodePort 30080). Without auth, anyone can inject fake deployment events.

### API key (static secret in header)

A pre-shared key in `X-API-Key` is simpler but lacks expiry semantics. Any leaked key remains valid forever until manually rotated. JWT tokens expire automatically, limiting the blast radius of a leaked token.

### OAuth2 / OIDC (Cognito, Keycloak)

Full OAuth2 would enable multi-tenant auth, fine-grained scopes, and token refresh. Rejected as over-engineered for a single-operator demo. Would require an external IdP or a separate Keycloak deployment.

### mTLS

Mutual TLS between CI/CD and the API would be robust but requires PKI management (certificate issuance, rotation) which is out of scope.

## Consequences

### Positive

- Stateless: the API does not store tokens; any pod restart does not invalidate existing tokens.
- Standard: Bearer tokens work natively with curl, GitHub Actions `secrets`, and FastAPI's Swagger UI (the Authorize button).
- Auditable: `sub` claim identifies the caller; structured logs include the username on authenticated requests.
- Zero external dependencies: PyJWT is a pure-Python library with no network calls.

### Negative

- No token revocation: a stolen token is valid until it expires (60 minutes by default). For production use, add a token blocklist or reduce expiry.
- Single static credential: the admin password is a shared secret across all clients (CI pipelines, load generator, humans). Multi-user auth would require a user database.
- HS256 symmetric key: the same key signs and verifies. If the key leaks, anyone can forge tokens. RS256 (asymmetric) would allow distributing the public key safely — acceptable future improvement.

## References

- PyJWT documentation — <https://pyjwt.readthedocs.io/>
- FastAPI security — <https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/>
- RFC 7519 — JSON Web Token — <https://tools.ietf.org/html/rfc7519>
- `app/src/deploytracker/api/auth.py`
- `app/src/deploytracker/api/routes/auth.py`
- `app/src/deploytracker/api/dependencies.py`
