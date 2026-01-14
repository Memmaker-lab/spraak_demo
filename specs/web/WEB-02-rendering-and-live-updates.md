# SPEC WEB-02 — Rendering Rules (Timeline, Transcript, Live)

TOOL: Cursor (primary)
ID: WEB-02
VERSION: 1.1
STATUS: TESTABLE
APPLIES_TO: demo

## 1. Intent
Define deterministic rendering from OBS-00 events into timeline, transcript, metrics, and live merging.

## 2. Timeline rendering
- Default view: key events only.
- Key events include:
  - call.started, call.answered, call.ended
  - turn.started
  - stt.final
  - llm.request, llm.response
  - tts.started, tts.stopped
  - barge_in.detected
  - provider.rate_limited, provider.retry_scheduled, provider.request_failed
  - action.failed
- Toggle "Show all" renders all events.

## 3. Turn grouping
- Group events by correlation_id when present.
- If correlation_id is missing, group by proximity:
  - new group starts at turn.started
  - otherwise group into last open turn bucket

## 4. Transcript rendering (demo)
- Transcript is derived from events when text is available:
  - user text: from stt.final payload (if present)
  - assistant text: from llm.response payload (if present)
- If text is absent, render metadata-only bubbles:
  - "User spoke (X ms)" and "Assistant spoke (Y ms)" where available.
- Transcript visibility follows WEB-00 demo toggle.

## 5. Metrics strip computation
Compute from events:
- turns: count(turn.started)
- barge-ins: count(barge_in.detected)
- rate-limits: count(provider.rate_limited)
- latencies:
  - STT: stt.final.latency_ms if present else omitted
  - LLM: llm.response.latency_ms if present else omitted
  - TTS: tts.started.latency_ms or derived if present else omitted
Show avg and p95 when sufficient samples exist.

## 6. Jump-to-first-problem
Define "problem event" as:
- severity in {warn,error} OR event_type in {provider.rate_limited, provider.request_failed}
Jump selects earliest matching event by ts.

## 7. Live updates (polling)
- Live polling MUST be user-controllable via a "Live" toggle.
- Default polling:
  - visible tab: every 3–5 seconds (configurable)
  - hidden tab: pause OR poll no more than every 30–60 seconds
- The UI MUST pause or degrade polling when:
  - document.visibilityState != "visible"
  - the user disables Live
- Live merge rules:
  - dedupe by (ts,event_type,correlation_id) if an event_id is absent
  - maintain stable order by ts
  - auto-scroll only when enabled; never force-scroll on the user

End of Spec.
