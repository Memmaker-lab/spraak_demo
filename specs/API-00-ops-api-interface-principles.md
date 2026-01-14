# SPEC API-00 — Ops API Interface Principles (FastAPI + REST/OpenAPI)

ID: API-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
Define the interface between the logging DB and UI consumers (internal ops UI and customer transparency UI).

## 2. Framework & contract
- The Ops API MUST be implemented in FastAPI.
- The API MUST follow a REST resource style.
- The API MUST publish an OpenAPI schema at `/openapi.json`.

## 3. Naming & routing
- The internal interface MUST be named "Ops API".
- Internal routes MUST be under `/ops/*`.
- A customer-facing interface MAY exist and MUST be separately namespaced (e.g., `/transparency/*`).
- Customer endpoints MUST return sanitized, customer-visible subsets only.

## 4. Live updates
Baseline (required):
- The API MUST support efficient incremental fetching for event streams using either:
  - `?since=<RFC3339>` OR
  - `?cursor=<opaque>`
- The UI MUST be able to fall back to periodic full refresh if incremental is unavailable.

Optional (nice-to-have):
- The API MAY expose Server-Sent Events (SSE) for streaming events to the UI:
  - `GET /ops/sessions/{id}/events/stream` (text/event-stream)

## 5. Pagination & queryability (minimum)
List endpoints MUST support:
- time range filters (`from`, `to`) where applicable
- pagination (`limit`, and `cursor` or page tokens)
- stable ordering guarantees

## 6. Testability
- The API contract MUST be verifiable:
  - OpenAPI schema is generated from code
  - endpoints have contract tests (request/response shape)
- The UI SHOULD generate TypeScript types from OpenAPI at build-time.

End of Spec.
