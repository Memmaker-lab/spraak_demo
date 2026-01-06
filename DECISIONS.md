# DECISIONS.md — ADR-lite

> Lightweight architecture decision log.
> Keep each decision short and link to specs that govern it.

## Template

```
### DEC-XXX — <title>
- **Date**: YYYY-MM-DD
- **Status**: accepted | superseded | deprecated
- **Context**: <1–3 sentences>
- **Decision**: <1–3 sentences>
- **Consequences**:
  - + <positive>
  - - <negative / tradeoff>
- **Specs**: SP-00, OBS-00, LK-00, ... (links)
```

---

### DEC-001 — Strict separation: Control Plane vs Voice Pipeline
- **Date**: 2026-01-06
- **Status**: accepted
- **Context**: We need telephone-native UX while keeping orchestration/policy stable and auditable.
- **Decision**: Keep **Control Plane** audio-free and policy/decision-rich; keep **Voice Pipeline** realtime STT→LLM→TTS only.
- **Consequences**:
  - + Enables safe iteration on voice models without changing control logic.
  - - Requires explicit handoffs (e.g., hangup via CP endpoint).
- **Specs**: `specs/SP-00-system-principles.md`, `specs/control-plane/CP-00-control-plane-overview.md`

### DEC-002 — LiveKit as the only transport + telephony boundary
- **Date**: 2026-01-06
- **Status**: accepted
- **Context**: We need one consistent transport layer for WebRTC + SIP bridging.
- **Decision**: Use LiveKit rooms/participants/tracks for transport and LiveKit SIP for telephony bridging.
- **Consequences**:
  - + Unified correlation via room + participant identifiers.
  - - Requires correct dispatch rules and agent name matching.
- **Specs**: `specs/LK-00-livekit-integration-boundary.md`, `specs/control-plane/CP-02-sip-telephony-boundary.md`

### DEC-003 — OBS-00 as the stable event contract for a future UI
- **Date**: 2026-01-06
- **Status**: accepted
- **Context**: We want a future website/app without coupling to runtime internals.
- **Decision**: Emit structured JSON events per OBS-00 across all components; treat it as UI-agnostic contract.
- **Consequences**:
  - + Debuggable and auditable system behavior.
  - - Requires discipline: stable event types and required fields.
- **Specs**: `specs/OBS-00-observability-and-control-contract.md`

### DEC-004 — Telephony hangup is performed by deleting the LiveKit room
- **Date**: 2026-01-06
- **Status**: accepted
- **Context**: Ending only the agent session can leave the caller hearing silence.
- **Decision**: Implement `POST /control/call/hangup` in Control Plane that ends calls by deleting the LiveKit room.
- **Consequences**:
  - + Ends the call for all participants reliably.
  - - Requires Control Plane to be reachable from Voice Pipeline (best-effort).
- **Specs**: `specs/control-plane/CP-03-control-api.md`, LiveKit telephony docs (hangup => delete_room)


