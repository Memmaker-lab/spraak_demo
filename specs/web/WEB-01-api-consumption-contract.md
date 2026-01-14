# SPEC WEB-01 — Ops API Consumption Contract (Web UI)

TOOL: Cursor (primary), Lovable (secondary)
ID: WEB-01
VERSION: 1.1
STATUS: TESTABLE
APPLIES_TO: demo

## 1. Intent
Define the minimum Ops API contract the web UI consumes, with type-safety via OpenAPI.

## 2. Base URL
- The UI MUST use an env var `API_BASE_URL` (no hardcoded localhost).
- All requests are relative to API_BASE_URL.

## 3. Required endpoints (minimum)
Read:
- GET  `/ops/sessions`
- GET  `/ops/sessions/{session_id}`
- GET  `/ops/sessions/{session_id}/events`

Write:
- POST `/ops/calls/hangup` { "session_id": "..." }
- POST `/ops/calls/cancel` { "session_id": "..." }

## 4. Response shape (minimum fields)

### 4.1 SessionList item (for `/ops/sessions`)
MUST include:
- session_id: string
- status: "pending" | "active" | "ended" | "failed"
- direction: "inbound" | "outbound"
- started_at: RFC3339

OPTIONAL:
- ended_at: RFC3339
- end_reason: string
- duration_ms: number
- providers: { stt?, llm?, tts? } (name/model/voice strings)
- counters: { turns?, barge_ins?, rate_limits?, errors? }
- worst_severity: "info" | "warn" | "error"

### 4.2 SessionDetail (for `/ops/sessions/{id}`)
MUST include SessionList fields plus:
- livekit: { room?, participant? } (strings)
- config_snapshot? (object; safe to display)

### 4.3 Events (for `/ops/sessions/{id}/events`)
MUST be an array ordered by ts ascending, each event MUST include OBS-00 common fields:
- ts, session_id, component, event_type, severity, correlation_id, pii

OPTIONAL:
- call, subject, provider, latency_ms, attempt
- payload (any additional fields)

Transcript fields (optional):
- If present, MUST be in explicit fields (e.g., payload.transcript.*) and pii must declare it.

## 5. Live update support
- The UI MUST work with full fetch (no incremental parameters required).
- The API SHOULD support incremental fetching via:
  - `?since=<RFC3339>` OR `?cursor=<opaque>`
If unsupported, UI falls back to periodic full refresh.

## 6. Errors & timeouts (UI expectations)
- 429 or provider overload must be displayed as a non-blocking banner/toast.
- The UI MUST remain usable even if events endpoint temporarily fails (retry with backoff).

## 7. Type-safety
- The UI SHOULD generate TypeScript types from OpenAPI (`/openapi.json`) at build-time.

End of Spec.
