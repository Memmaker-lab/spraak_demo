# SPEC WEB-03 — Control Actions UI (Hangup/Cancel)

TOOL: Cursor (primary), Lovable (secondary for layout)
ID: WEB-03
VERSION: 1.1
STATUS: ENFORCED
APPLIES_TO: demo

## 1. Intent
Expose minimal call control from the UI with safe UX and auditable outcomes via the Ops API.

## 2. Endpoints
- POST /ops/calls/hangup { "session_id": "..." }
- POST /ops/calls/cancel { "session_id": "..." }

## 3. UI rules
- Hangup button visible only when session.status == "active"
- Cancel button visible only when session.status == "pending"
- Both actions MUST require a confirm modal.
- Buttons MUST disable while request is in-flight (idempotent UX).

## 4. Result handling
- Success: show toast + refresh session detail.
- Failure: show non-blocking error toast + keep UI responsive.

## 5. Audit visibility
- The session timeline MUST show:
  - control.command_received
  - control.command_applied
when present in the event stream.

End of Spec.
