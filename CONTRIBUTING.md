# Contributing

All changes via PR. Specs in `/specs` are the source of truth.

## Non-negotiables
- No assumptions: use specs, official docs, or tests/experiments.
- Python-only (current phase).
- Minimize exposure to external cloud providers (STT/LLM/TTS): send only what's required.
- Structured JSON events per `OBS-00`.
- Separation: Control Plane (no audio) vs Voice Pipeline (no business/policy).
- PII logging is allowed for audit/ops, but MUST be intentional: explicit fields, access-aware, never leaked to providers.

## Specs
Each spec: ID, VERSION, STATUS, APPLIES_TO, minimal CHANGELOG.
STATUS: PLANNED | TESTABLE | ENFORCED | OPTIONAL | DEPRECATED
ENFORCED => passing tests. Don't change specs to fit code.

## Branch / commits
Branches: `spec/<ID>-<name>` | `feat/<name>` | `fix/<name>` | `chore/<name>`
Commits: `spec(<ID>): ...` | `test(<ID>): ...` | `feat: ...` | `fix: ...`

## PR checklist
- Intent + impacted spec IDs (and any STATUS change)
- Verification: tests added/updated (`pytest`)
- Observability: new/changed `OBS-00` events
- Data boundary check: no extra PII sent to external providers

