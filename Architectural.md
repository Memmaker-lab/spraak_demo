# Architectural.md — Architecture & Decisions (spraak_demo)

## Source of truth
- Specs in `/specs` are authoritative. This document explains how the code maps to them.

## High-level architecture

### Two main subsystems (SP-00)

#### **Control Plane**
- **Responsibilities** (CP-00):
  - session orchestration and lifecycle (CP-01)
  - call control via LiveKit telephony boundary (LK-00)
  - minimal control API for website/app (CP-03)
  - structured events (OBS-00)
- **Hard rule**: **no realtime audio** processing.

#### **Voice Pipeline**
- **Responsibilities** (SP-00, VC-*):
  - realtime media I/O (via LiveKit Agents)
  - STT → LLM → TTS
  - telephone-native UX (VC-00..VC-03)
  - structured events per OBS-00
- **Hard rule**: **no business/policy decisions** (that lives in Control Plane).

## LiveKit boundary (LK-00)
- LiveKit provides transport (rooms/participants/tracks) and telephony bridging (SIP trunks + dispatch rules).
- We correlate:
  - `session_id` (opaque; no PII encoded)
  - LiveKit room/participant identifiers

## Observability (OBS-00)
Two layers are used:
- **OBS-00 events**: stable event taxonomy and envelope (JSON)
  - Used for auditing, debugging, later UI consumption.
- **General logs**: operational logs (also JSON) for debugging.

Key implementation points:
- Every event includes `session_id`.
- `correlation_id` is used per turn / command.

## Control surface (CP-03)
- Minimal write action implemented:
  - `POST /control/call/hangup` `{ "session_id": "call-..." }`
  - Implemented by deleting the LiveKit room (telephony docs: hangup => delete_room)
  - Emits: `control.command_received`, `control.command_applied`

## Telephony dispatch
- Inbound SIP dispatch rules can specify `roomPrefix` (e.g. `call-`) and **explicit** `agentName`.
- If dispatch rule uses `agentName`, the voice worker must start with matching:
  - `LIVEKIT_AGENT_NAME="Emp AI"`

## Why these choices
- **Separation** (SP-00) keeps policy/control stable even if audio/model stack changes.
- **OBS-00** event contract enables a future website/app without coupling UI to runtime internals.
- **LiveKit-only transport** centralizes telephony + WebRTC under one reliable boundary.

## Recommended next docs (optional)
- **`DECISIONS.md`**: lightweight ADR log (1 paragraph per decision + spec references).
- **`RUNBOOK.md`**: operations (start order, ports, env vars, health checks).
- **`TROUBLESHOOTING.md`**: known failure modes (dispatch agentName mismatch, ngrok 502, webhook config).


