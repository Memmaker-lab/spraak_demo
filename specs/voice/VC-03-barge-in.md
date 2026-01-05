# SPEC VC-03 — Barge-in (User Interrupts TTS)

ID: VC-03
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
In a natural phone call, the user can interrupt. The system MUST yield immediately.

## 2. Core rule
If user speech starts while TTS is playing, TTS MUST stop immediately.

## 3. Acceptance criteria (measurable)
- A barge-in MUST be detected when user speech begins during TTS playback.
- TTS MUST stop within a bounded reaction window.
  Target: ≤ 100ms from detected user speech start to TTS stop event.
  (If transport makes this unverifiable, the system MUST still emit timestamps enabling measurement.)

## 4. Required observability (OBS-00)
On every barge-in:
- emit barge_in.detected
- emit tts.stopped { cause: "barge_in" }
- include latency_ms where measurable (time_to_tts_stop_ms)

## 5. Non-regression rules
- Barge-in MUST work regardless of turn detection mode (vad_only or vadeou).
- Barge-in MUST NOT crash or deadlock the pipeline.
- Barge-in MUST take precedence over provider retries/backoff (RL-00).

## 6. Testability (ENFORCED)
Tests MUST exist and MUST pass for:
- barge-in during TTS stops playback
- correct event emission and correlation (session_id, correlation_id)
- no extra TTS audio after stop (best-effort, validated via stop signal + no further audio frames dispatched in harness)

End of Spec.
