# SPEC OBS-00 — Observability & Control Contract

ID: OBS-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
The system MUST be debuggable and auditable without relying on raw audio or leaking PII.
A future web UI may consume these events, but this spec is UI-agnostic.

## 2. Event format (structured)
All logs MUST be JSON events.

### 2.1 Required common fields
- ts: RFC3339 timestamp (UTC)
- session_id: opaque ID
- component: "control_plane" | "voice_pipeline" | "adapter" | "action_runner"
- event_type: stable string (see taxonomy)
- severity: "debug" | "info" | "warn" | "error"
- correlation_id: per request/turn/action (opaque)
- pii: { contains_pii: bool, fields_redacted: [..] }

### 2.2 Optional common fields (when applicable)
- call: { direction, caller_hash, callee_hash }
- livekit: { room, participant, track }
- provider: { name, model, endpoint }
- latency_ms: number
- attempt: number

## 3. Event taxonomy (minimum)
### 3.1 Call/session lifecycle
- call.started
- call.answered
- call.ended { reason }

### 3.2 LiveKit lifecycle (correlated via session_id)
- livekit.room.created
- livekit.participant.joined
- livekit.participant.left
- livekit.track.published
- livekit.track.unpublished
(Use webhooks/events where available.)

### 3.3 Voice pipeline turns
- turn.started
- stt.partial
- stt.final
- llm.request
- llm.response
- tts.started
- tts.stopped { cause: "completed" | "barge_in" | "error" }
- barge_in.detected

### 3.4 Turn detection instrumentation (VAD/EOU)
- vad.state_changed { state }
- eou.prediction { confidence, decision }
- endpointing.delay_applied { ms }
(Note: keep this measurable.)

### 3.5 Provider limits & backpressure
- provider.rate_limited { retry_after_ms? }
- provider.retry_scheduled { backoff_ms, attempt }
- provider.request_failed { class }

### 3.6 Actions (future-safe)
- action.requested { action_type }
- action.completed
- action.failed

## 4. Privacy rules for events
- MUST NOT log raw phone numbers; store salted hashes only.
- MUST NOT log raw user transcripts by default.
  - If transcript logging is enabled for a test run, it MUST be explicitly flagged and redacted.
- MUST NOT include extra user context in retries/backoff events.

## 5. Control surface (minimal, safe)
The control plane MAY expose a control API, but write operations MUST be restricted and auditable.
Minimum commands (if implemented):
- call.cancel(session_id)
- call.hangup(session_id)
- pipeline.debug_toggle(session_id, enabled)
All control actions MUST emit:
- control.command_received
- control.command_applied

End of Spec.
