# SPEC SP-00 — System Principles

ID: SP-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Scope
This repository defines a telephone-native AI voice system built around LiveKit transport.
The system must sound and behave like a natural phone call (nl-NL).

## 2. Authority & Discipline
- Specs are the primary source of truth.
- Implementation MUST conform to specs; specs MUST NOT be edited to match implementation.
- ENFORCED specs MUST have tests. TESTABLE specs MAY have failing tests.

### 2.1 Spec lifecycle
Each spec MUST include: ID, VERSION, STATUS, APPLIES_TO, and a minimal CHANGELOG.
Allowed STATUS: PLANNED, TESTABLE, ENFORCED, OPTIONAL, DEPRECATED.

### 2.2 Handling new insights (explicit)
- Type A (Discovery): add new spec.
- Type B (Refinement): clarify criteria → bump VERSION.
- Type C (False assumption): mark DEPRECATED + replacement spec.
- Type D (Scope shift): introduce profile/applicability, do not rewrite history.

## 3. Language Policy
- Specs: English.
- User-facing speech examples: Dutch (nl-NL).
- Identifiers / log keys / test names: English.

## 4. Verified-Knowledge-Only (AI / Cursor behavior)
- NO ASSUMPTIONS: the assistant MUST NOT invent APIs, behavior, configs, limits, or “likely” defaults.
- SOURCE OF TRUTH REQUIRED: any technical claim MUST be backed by one of:
  (a) a spec in this repo, (b) official docs, (c) a reproducible test/experiment, (d) explicit user input.
- DOCUMENTATION-FIRST: prefer official docs over prior knowledge.
- VERIFY BEFORE ASSERT: when feasible, propose and run a minimal test before claiming correctness.
- CLARIFY OVER GUESSING: if ambiguous, the assistant MUST explain what’s unclear and ask.

## 5. Implementation Constraint (current phase)
All components and tests MUST be implemented in Python for the current phase.

## 6. Architectural Invariants
- Strict separation:
  - Control Plane: orchestration, policies, configuration, call control, observability.
  - Voice Pipeline: realtime I/O and STT→LLM→TTS pipeline behavior.
- Control Plane MUST NOT process realtime audio.
- Voice Pipeline MUST NOT contain business/policy decisions.
- Every call/session MUST have exactly one session_id (opaque; no PII encoded).
- All behavior MUST be observable via structured events (see OBS-00).

## 7. LiveKit Boundary (high level)
- WebRTC transport MUST use LiveKit (rooms/participants/tracks model).
- Telephony bridging (inbound/outbound) MUST be via LiveKit telephony (SIP trunks/dispatch rules where applicable).
- System MUST capture relevant LiveKit lifecycle signals via webhooks/events for correlation and audit.
(Details: LK-00)

## 8. Security & Privacy by Design
- Data minimization: send/store only what is required for the immediate purpose.
- External providers (STT/LLM/TTS) are treated as untrusted boundaries:
  - MUST redact/anonymize identifiers where possible.
  - MUST NOT send raw phone numbers unless strictly required.
- Logs MUST be privacy-aware by default (see OBS-00).
- In conflicts between convenience and privacy, privacy wins unless an ENFORCED spec says otherwise.

## 9. Rate limiting is expected
External AI rate limits/throttling MUST be handled gracefully:
- no crashes
- bounded retries/backoff
- user gets a human explanation (not technical)
(Details: RL-00)

## 10. Forward-compatible actions (tools)
The architecture MUST allow adding asynchronous actions (email, summaries, etc.) without blocking realtime voice.
(Details: ACT-00)

End of Spec.
