# SPEC CP-03 — Control API (Website/App)

ID: CP-03
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
Provide a minimal, secure interface for:
- starting outbound calls from a website/app
- viewing session status and structured logs
- performing limited control actions

## 2. Read API (must)
The Control API MUST support:
- list sessions (filter by time/status)
- get session details (state, config summary, timestamps)
- stream/query OBS-00 events by session_id

## 3. Write API (limited; must)
The Control API MAY support:
- start outbound call (requires explicit user intent/consent)
- hang up / cancel call by session_id

All write actions MUST be auditable via:
- control.command_received
- control.command_applied

## 4. Consent & privacy
- Outbound call initiation MUST require explicit intent/consent in the request.
- Phone numbers MUST be treated as sensitive:
  - not logged raw
  - stored/transported with minimal exposure (SP-00 privacy)

## 5. Failure behavior
- API failures MUST return stable error categories (no internal traces).
- Any telephony/provider throttling MUST be surfaced as a non-technical user message (voice path)
  and as provider.* events in OBS-00.

End of Spec.
