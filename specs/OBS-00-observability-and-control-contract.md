# SPEC OBS-00 — Observability & Control Contract

ID: OBS-00
VERSION: 1.1
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
The system MUST be debuggable and auditable through structured events.
A future website/app may consume these events, but this contract is UI-agnostic.

PII logging is allowed for internal audit/ops, but external exposure to cloud providers MUST be minimized.

## 2. Event format (structured)
All logs MUST be JSON events.

### 2.1 Required common fields
- ts: RFC3339 timestamp (UTC)
- session_id: opaque ID
- component: "control_plane" | "voice_pipeline" | "adapter" | "action_runner"
- event_type: stable string (see taxonomy)
- severity: "debug" | "info" | "warn" | "error"
- correlation_id: per request/turn/action (opaque)
- pii: { contains_pii: bool, fields: [..], handling: "none" | "masked" | "restricted" }

### 2.2 Optional common fields (when applicable)
- call: { direction, caller_hash?, callee_hash? }
- subject: { phone_number?, name?, email? }  (PII allowed; must be declared via pii.*)
- livekit: { room?, participant?, track? }
- provider: { name?, model?, endpoint? }
- latency_ms: number
- attempt: number

## 3. Event taxonomy (minimum)

### 3.1 Call/session lifecycle
- call.started { direction }
- call.answered
- call.ended { reason }
- session.state_changed { from, to }

### 3.2 LiveKit lifecycle (correlated via session_id)
- livekit.room.created
- livekit.participant.joined
- livekit.participant.left
- livekit.track.published
- livekit.track.unpublished

### 3.3 Voice pipeline turns
- turn.started { user_last_audio_ts_ms? }
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

### 3.5 Provider limits & backpressure
- provider.rate_limited { retry_after_ms? }
- provider.retry_scheduled { backoff_ms, attempt }
- provider.request_failed { class }

### 3.6 Actions (future-safe)
- action.requested { action_type }
- action.completed
- action.failed

### 3.7 UX hooks (telephone-native)
- ux.delay_acknowledged { message_key }
- ux.response_chunked { message_key? }
- ux.recoverable_error_message { message_key }

### 3.8 Control surface (auditable)
- control.command_received { command }
- control.command_applied { command, result? }

## 4. Privacy rules for events
- PII logging is allowed for audit/ops, but MUST be intentional:
  - PII MUST appear only in explicit fields (e.g., subject.*), not buried in free-text.
  - Any event containing PII MUST set:
    pii.contains_pii=true and list pii.fields + pii.handling.
  - Prefer pii.handling="masked" for routine logs; use "restricted" only when necessary.
- Logs MUST NOT contain secrets (API keys, credentials, tokens).
- Transcripts:
  - Raw transcripts MAY be logged only if explicitly enabled per session/config and MUST be flagged:
    pii.contains_pii=true, pii.fields includes "transcript".
  - When transcript logging is disabled, logs MUST contain only non-content metadata
    (timing, lengths, model/provider, decision signals).
- External boundary rule:
  - Logged PII MUST NOT be forwarded to external STT/LLM/TTS providers unless strictly required.
  - Retries/backoff MUST NOT expand user content sent externally (RL-00).

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
