# SPEC CP-01 — Session Lifecycle

ID: CP-01
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
Every call is represented by exactly one session_id and a complete auditable lifecycle.

## 2. Rules
- Control Plane MUST create a new session_id for each call attempt.
- session_id MUST be opaque and MUST NOT encode PII.
- Session states MUST be explicit and monotonic.

Recommended states:
- created
- dialing | ringing | inbound_ringing
- connected
- ending
- ended

## 3. Required observability (OBS-00)
The Control Plane MUST emit:
- call.started { direction }
- call.answered
- call.ended { reason }
plus any state transitions:
- session.state_changed { from, to }

Each event MUST include session_id and (if available) LiveKit correlation fields (room/participant).

## 4. Failure handling
- Any failure MUST end in call.ended { reason } without crashing.
- Provider/rate limit issues MUST follow RL-00 messaging strategy (via voice pipeline UX),
  while Control Plane emits provider.* events if the failure is at SIP/telephony boundary.

End of Spec.
