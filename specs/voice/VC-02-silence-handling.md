# SPEC VC-02 — Silence Handling (Telephone-native)

ID: VC-02
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
Silence must be interpretable on the phone. The user MUST never be left in unexplained silence.

## 2. Silence types (operational)
- User silence: user is not speaking.
- Processing silence: system is working (STT/LLM/TTS) and not speaking.

## 3. Core rules
- If processing silence exceeds a threshold, the system MUST acknowledge delay in Dutch (non-technical).
- If user silence persists after a prompt, the system MUST follow a bounded reprompt + graceful close strategy.

## 4. Acceptance criteria (measurable)
- The system MUST emit events enabling measurement of:
  user_last_audio_ts → first system feedback (tts.started OR ux.delay_acknowledged)
- The system MUST produce a delay acknowledgement when processing silence is “long”.
  (Threshold is configurable; must be logged per session.)

## 5. User-facing UX (Dutch; examples)
Delay acknowledgement:
- "Momentje, ik denk even mee."
- "Het duurt iets langer dan normaal."

Reprompt:
- "Ben je er nog?"
Graceful close:
- "Oké, ik hoor even niks. Ik hang op. Fijne dag!"

## 6. Required observability (OBS-00)
- ux.delay_acknowledged
- silence.timer_started { kind: "processing" | "user" }
- silence.timer_fired { kind, threshold_ms }
- call.ended { reason } when silence triggers termination

## 7. Testability (ENFORCED)
Tests MUST pass for:
- delay acknowledgement is emitted when processing is long
- delay acknowledgement is non-technical (validated via message key/category)
- silence close path terminates cleanly and emits call.ended reason

End of Spec.
