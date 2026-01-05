# SPEC TS-01 — Voice Test Harness (Python)

ID: TS-01
VERSION: 1.0
STATUS: TESTABLE
APPLIES_TO: demo, production

## 1. Intent
Provide a deterministic, provider-independent way to test voice pipeline behavior:
turn-taking, barge-in, endpointing (VAD/EOU), retries/backoff, and observability.

The harness enables verification without real calls and without relying on LiveKit runtime.

## 2. Scope
The harness MUST support:
- simulated input audio timeline (speech/silence segments)
- simulated TTS playback timeline
- simulated provider responses (STT/LLM/TTS) including throttling (429) and timeouts
- capture of structured OBS-00 events for assertions

## 3. Determinism & reproducibility
- Tests MUST be deterministic.
- Any jitter/randomness MUST be seedable and recorded in logs/test output.
- Time MUST be controllable (fake clock) to assert timing windows.

## 4. Required interfaces (conceptual; implement in Python)
The voice pipeline MUST be runnable against harness adapters:
- AudioInAdapter: feeds simulated audio frames/events
- AudioOutAdapter: records TTS start/stop and dispatched frames (or stop signals)
- STTAdapter: returns partial/final transcripts per scripted timeline
- LLMAdapter: returns responses or scripted failures
- TTSAdapter: returns audio or a playback token; MUST support interrupt/stop

All adapters MUST be mockable and MUST emit OBS-00 provider.* events when invoked.

## 5. Required test scenarios (minimum set)
The suite MUST be able to implement tests for:
- VC-03: barge-in interrupts TTS (stop within reaction window; events emitted)
- VC-01: turn lifecycle event ordering and correlation_id correctness
- EOU-00: vadeou mode emits eou.prediction and endpointing.delay_applied
- RL-00: repeated 429 triggers bounded retries/backoff and emits provider.rate_limited/provider.retry_scheduled
- VC-00: long processing triggers ux.delay_acknowledged (Dutch phrasing selection is validated by message key, not raw text)

## 6. Assertions style
Tests MUST assert primarily on:
- emitted OBS-00 event stream (order, required fields, correlation)
- explicit stop/interrupt signals
- bounded retry counters/backoff decisions

Raw audio waveform comparisons are OPTIONAL and not required.

## 7. Output artifacts
For any failing test, the harness SHOULD dump:
- event stream (JSONL)
- session_id and correlation_id
- configured mode (vad_only / vadeou)
to enable rapid debugging.

End of Spec.
