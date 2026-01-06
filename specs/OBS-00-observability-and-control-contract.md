# SPEC OBS-00 — Observability & Control Contract

ID: OBS-00
VERSION: 1.2
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

### 3.9 Call timeline & latency (extended)

To support a full per-call timeline in a future UI, the following MUST hold:

1. **Cross-component correlation**
   - All events MUST use a `session_id` that is identical between Control Plane and Voice Pipeline for the same call.
   - Within a call, `correlation_id` MUST be used to group:
     - turns (Voice Pipeline): one `correlation_id` per user→agent turn.
     - commands (Control Plane): one `correlation_id` per control action (e.g. hangup).

2. **Latency measurement (RECOMMENDED, MAY become ENFORCED)**
   - Where available, the following events SHOULD include `latency_ms` (numeric, milliseconds):
     - `stt.final` — STT processing latency for the committed transcript.
     - `llm.response` — model inference/planning latency per turn.
     - `tts.stopped` — TTS synth+playback duration for the agent response.
     - `provider.rate_limited` / `provider.retry_scheduled` — wait/backoff durations.
     - `control.command_applied` — end-to-end duration of the control action (e.g. hangup).
   - Absence of `latency_ms` does not break compatibility, but does limit the usefulness of per-call timeline UIs.

3. **Minimal cross-component timeline (per session_id)**
   - Across all components combined, a call timeline MUST at least be reconstructible from:
     - Call lifecycle (Control Plane):
       - `call.started { direction }`
       - `call.answered`
       - `call.ended { reason }`
       - `session.state_changed { from, to }`
     - LiveKit lifecycle (Control Plane):
       - `livekit.room.created`
       - `livekit.participant.joined`
       - `livekit.participant.left`
       - `livekit.track.published` / `livekit.track.unpublished`
     - Voice turns (Voice Pipeline):
       - `turn.started { user_last_audio_ts_ms? }`
       - `stt.final { transcript_length, language, latency_ms? }`
       - `llm.request`
       - `llm.response { latency_ms? }`
       - `tts.started`
       - `tts.stopped { cause, latency_ms? }`
       - `barge_in.detected`
     - Silence handling (Voice Pipeline, VC-02):
       - `silence.timer_started { kind, threshold_ms }`
       - `silence.timer_fired { kind, threshold_ms }`
       - `ux.delay_acknowledged { message_key }`
       - `call.ended { reason: "user_silence_timeout" }`
     - Control actions (Control Plane, CP-03):
       - `control.command_received { command }`
       - `control.command_applied { command, result, latency_ms? }`

4. **Queryability for UI**
   - The system MUST expose a way (e.g. via CP-03 Control API) to:
     - fetch all events for a given `session_id`,
     - optionally filtered by `event_type`, `component`, `since`, `until`,
     - ordered by timestamp (oldest first).
   - This interface MUST be sufficient for a UI to render a complete per-call timeline with timestamps (`ts`) and, where present, `latency_ms`.

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
