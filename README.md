# spraak_demo

Telephone-native AI voice demo built around LiveKit transport (WebRTC + SIP telephony), with external STT/LLM and optional TTS.
This repository is **spec-first** and **test-driven**. Code is generated/iterated with Cursor under strict rules.

## Repository truth
The authoritative behavior is defined in `/specs`.

If anything conflicts:
1) Specs override code
2) Specs override prompts/tooling
3) Specs override docs/README

Start here:
- `specs/SP-00-system-principles.md`
- `specs/NFR-00-non-functional-requirements.md`
- `specs/OBS-00-observability-and-control-contract.md`

## Key principles (summary)
- **Verified-knowledge-only**: no assumptions. Use official docs, specs, or tests/experiments.
- **Security & privacy by design**: minimize PII, treat external providers as untrusted boundaries.
- **Strict separation**:
  - Control Plane: orchestration, policy, session, call control, observability (no audio).
  - Voice Pipeline: realtime audio + STT→LLM→TTS (no business logic/policy decisions).
- **Python-only (current phase)**.

## Specs workflow
Each spec has:
- ID (stable), VERSION, STATUS, APPLIES_TO, minimal CHANGELOG

Allowed STATUS:
- PLANNED, TESTABLE, ENFORCED, OPTIONAL, DEPRECATED

Rules:
- Do **not** change specs to fit code.
- ENFORCED specs must have passing tests.
- TESTABLE specs may have failing tests (but must be testable).

## Observability contract
All components emit structured JSON events per `OBS-00`.
A future UI can be built on top of these events, but the contract is UI-agnostic.

## Cursor rules
Project rules live in `.cursor/rules/*.mdc`.
They enforce: spec-first behavior, no assumptions, privacy-first logging, rate-limit handling, and required instrumentation.

## Pull Request (PR) workflow (required)
All changes happen via PRs (including specs).

### Branch naming
Use one of:
- `spec/<id>-<short-name>` (e.g. `spec/VC-02-silence-handling`)
- `feat/<short-name>`
- `fix/<short-name>`
- `chore/<short-name>`

### Commit messages (recommended)
- `spec(<ID>): <change>` (e.g. `spec(VC-02): add silence close path criteria`)
- `test(<ID>): <change>`
- `feat: <change>`
- `fix: <change>`

### PR requirements
A PR must include:
1) **Intent**: what problem/insight is addressed?
2) **Specs impacted**: list spec IDs (and STATUS changes if any)
3) **Verification**:
   - link to tests added/updated
   - or explain why verification is not feasible (rare)
4) **Privacy check**: confirm no new PII exposure/logging

### When changing specs
Classify the change explicitly:
- Type A Discovery → new spec
- Type B Refinement → version bump
- Type C False assumption → deprecate + replacement
- Type D Scope shift → add profile/applicability

### PR review checklist (quick)
- [ ] No duplicated rules across specs
- [ ] ENFORCED specs have tests (or PR adds them)
- [ ] OBS-00 events emitted/updated where needed
- [ ] No assumptions: docs/tests cited in PR description if relevant
- [ ] No raw phone numbers or sensitive text in logs by default

## What to build first (high level)
1) Control Plane outbound call via LiveKit SIP (CP-00..CP-04, LK-00, OBS-00)
2) Voice pipeline happy path (VC-00, VC-01 TESTABLE, RL-00)
3) Telephone-natural behavior (VC-02, VC-03 ENFORCED)
4) EOU experiment (EOU-00)

---

## License
TBD
