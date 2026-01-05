# SPEC EOU-00 — End-Of-Utterance (EOU) alongside VAD (Experiment)

ID: EOU-00
VERSION: 1.0
STATUS: TESTABLE
APPLIES_TO: demo, production

## 1. Intent
Evaluate whether EOU improves turn-taking quality compared to VAD-only endpointing,
without increasing perceived latency or harming interruption behavior.

EOU decisions are instrumented and comparable across runs.

## 2. Definitions (operational)
- VAD: acoustic voice activity state changes (speech/non-speech).
- EOU: model-based prediction that the user’s utterance is complete.
This spec does not assume a specific EOU model; only observable behavior matters.

## 3. Non-negotiables (must not regress)
- Barge-in MUST still stop TTS immediately (VC-03, OBS-00).
- The user MUST NOT experience unexplained silence (VC-00).
- The system MUST remain stable under provider rate limits (RL-00).

## 4. Experiment modes
The system MUST support these modes (configurable per session):
- mode = "vad_only"
- mode = "vadeou"  (VAD + EOU gating)

The session config MUST be logged:
- turn_detection.mode
- vad parameters (if applicable)
- eou threshold(s) or policy label

## 5. Measurable outcomes (minimum)
For each session, the system MUST log metrics sufficient to compute:

### 5.1 Endpointing delay
- time_user_last_audio_ms → turn.started
- time_user_last_audio_ms → llm.request
- time_user_last_audio_ms → tts.started

### 5.2 False endpointing / clipping proxy
- frequency of user continuing speech within X ms after endpoint decision
  (logged via subsequent vad.state_changed / stt.partial after endpoint)

### 5.3 Over-waiting proxy
- frequency of delay acknowledgements (ux.delay_acknowledged)
- frequency of long endpoint delays (endpointing.delay_applied)

### 5.4 Interruption robustness
- count of barge_in.detected per call
- time_to_tts_stop_ms (tts.stopped cause="barge_in")

## 6. Required observability events (OBS-00)
During the experiment, the voice pipeline MUST emit:
- vad.state_changed { state }
- eou.prediction { confidence, decision }
- endpointing.delay_applied { ms }
- turn.started
- tts.started / tts.stopped
- ux.delay_acknowledged (when used)

## 7. Testability requirements
The test suite MUST include deterministic simulations for:
- user speech → silence → endpoint decision
- user resumes speaking shortly after endpoint decision (clipping proxy)
- barge-in during TTS (must still stop)
- long processing path triggers ux.delay_acknowledged

Tests MUST assert:
- required events are emitted with session_id
- mode selection is respected and logged
- no crashes under repeated provider throttling signals (mocked 429)

End of Spec.
