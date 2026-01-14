# SPEC CUST-LOG-00 — Customer Traceability Contract

ID: CUST-LOG-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: customer

## 1. Intent
Provide transparent, traceable call records for customers: what was said, what happened, and what actions occurred, without leaking internal implementation details.

## 2. Customer surfaces
- Customer Portal UI consumes `/transparency/*`
- Customer data MUST conform to SAN-00.

## 3. Customer-visible record types (minimum)
### 3.1 Call report (document-first)
- Each session MUST have a customer report object containing:
  - session_id, started_at, ended_at, duration_ms
  - high-level outcome (ended_reason)
  - conversation summary (short)
  - transcript (optional; if enabled & consented)
  - flow steps (scenario/step transitions)
  - actions executed (later) with safe summaries

### 3.2 Customer-visible event stream (optional)
- A reduced event stream MAY be exposed, limited to:
  - call.started, call.answered, call.ended
  - flow.step_changed
  - transcript.user, transcript.assistant (if enabled)
  - action.started/action.completed/action.failed (later; sanitized)

## 4. Transcript requirements (if enabled)
- Transcript MUST be clearly labeled as recorded content.
- Transcript MUST be disableable per environment and per tenant policy.
- If transcript is disabled, the report MUST still render (metadata-only).

## 5. Actions (future-safe)
- Actions MUST include:
  - action_type, status, timestamps, safe_result_summary
- Raw results MUST NOT be exposed (SAN-00).

## 6. Traceability guarantees
- All customer-visible objects MUST be attributable to a session_id.
- Ordering MUST be stable by timestamp.
- If data is missing, the report MUST indicate gaps (e.g., "Transcript unavailable").

End of Spec.
