# SPEC VC-01 — Turn-Taking (Telephone-native)

ID: VC-01
VERSION: 1.0
STATUS: TESTABLE
APPLIES_TO: demo, production

## 1. Intent
Turn-taking MUST feel natural on the phone: quick, predictable, and observable.

## 2. Turn lifecycle (observable contract)
A "turn" starts when the system commits to responding to a user utterance.

Rules:
- A turn MUST have a unique correlation_id.
- A turn MUST emit turn.started before llm.request.
- The system MUST NOT start TTS for a turn without a preceding llm.response
  (except for fixed UX phrases like delay acknowledgement; those MUST emit ux.* events per VC-00).

## 3. Endpointing (mode-aware)
Turn creation MUST be driven by an endpoint decision derived from:
- VAD-only mode, or
- VAD + EOU mode (EOU-00)

Rules:
- The endpoint decision MUST be logged via:
  - vad.state_changed events
  - and, in vadeou mode, eou.prediction and endpointing.delay_applied as applicable.
- Endpointing MUST NOT cause unexplained silence (VC-00).

## 4. Responsiveness requirements (measurable)
The system MUST emit timestamps/events enabling these measurements per turn:
- user_last_audio_ts → turn.started
- user_last_audio_ts → llm.request
- user_last_audio_ts → tts.started

Targets are set by the implementation phase; this spec requires measurability now.
(Thresholds may be tightened in a later version bump.)

## 5. Required observability (OBS-00)
Per turn:
- turn.started
- llm.request
- llm.response
- tts.started
- tts.stopped { cause: "completed" | "barge_in" | "error" }
Plus endpointing instrumentation per mode (EOU-00).

## 6. Failure behavior (handoff to RL-00 / VC-00)
If providers fail or rate limit:
- behavior MUST follow RL-00
- user-facing phrasing MUST follow VC-00 (non-technical Dutch)
- events MUST still be emitted (provider.* and ux.*)

## 7. Testability requirements (TESTABLE)
Tests SHOULD cover:
- correct event order in a happy-path turn
- correct correlation_id usage
- correct mode logging (vad_only vs vadeou)
- no TTS without llm.response (except ux.* phrases)

End of Spec.
