# SPEC WEB-00 — Demo Observability UI (Scope & UX)

TOOL: Lovable (primary), Cursor (secondary)
ID: WEB-00
VERSION: 1.1
STATUS: ENFORCED
APPLIES_TO: demo

## 1. Intent
Provide a demo-grade web UI to inspect voice-call sessions, live events, transcript, and execute minimal call control via the Ops API.

## 2. Pages (required)
1) Sessions: `/sessions`
2) Session detail: `/sessions/:session_id`
3) Incidents: `/incidents`
4) Live: `/live`

## 3. Sessions page (required UX)
- Default sort: newest first
- Filters (minimum): time range, status, direction, severity, provider (STT/LLM/TTS)
- Each row MUST show:
  - session_id (copy)
  - status + end reason (if ended)
  - start time + duration (if ended)
  - direction
  - highlights: turns, barge-ins, rate-limits
  - providers summary (names/models/voice)
  - worst severity badge
- Row actions:
  - Open (always)
  - Hangup (only if active)
  - Cancel (only if pending)

## 4. Session detail page (required UX)
Layout: 3-pane
- Left: timeline (grouped by turn; toggle key events vs all)
- Middle: transcript view (DEMO MODE; see §7)
- Right: event inspector (formatted fields + raw JSON + copy)

Required controls:
- Jump to first problem (first warn/error or rate-limit)
- Filters: event_type, severity
- Auto-scroll toggle for Live mode
- Hangup/Cancel buttons with confirm modal

## 5. Incidents page (required UX)
- Grouped counts over selected time range:
  - provider.rate_limited by provider/model
  - provider.request_failed by class
  - failed calls by reason
- Each group links to example sessions.

## 6. Live page (required UX)
- Live sessions list (recent + currently active)
- Selecting a session opens session detail with live auto-updating enabled.

## 7. Demo transcript mode (required)
- Transcript MUST be visible in demo UI.
- UI MUST display a clear DEMO MODE indicator.
- UI MUST provide a toggle: Show transcript (default ON in demo).
- The UI MUST be able to render without transcript fields (metadata-only fallback).

## 8. Non-goals (explicit)
- No end-user account features
- No automatic forms generation for API
- No RBAC/auth beyond demo safeguards

End of Spec.
