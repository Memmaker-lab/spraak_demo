# SPEC CP-00 — Control Plane Overview

ID: CP-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
The Control Plane orchestrates calls, sessions, configuration, and control actions.
It MUST remain audio-free and policy/decision-rich (SP-00).

## 2. Responsibilities (must)
- Create and manage session_id and session lifecycle.
- Store session configuration (STT/LLM/TTS providers, turn detection mode).
- Initiate and terminate calls via LiveKit Telephony (SIP).
- Provide a minimal control API for the website/app (read + limited write).
- Emit structured events per OBS-00 for all state transitions.

## 3. Prohibitions (must not)
- MUST NOT process realtime audio.
- MUST NOT call STT/LLM/TTS directly for realtime turns (voice pipeline only).

## 4. Boundaries
- SIP provider (Twilio/CheapConnect/etc) connects to LiveKit via trunks.
- Inbound routing uses dispatch rules to join calls to rooms.
- Outbound calling uses CreateSIPParticipant to dial PSTN numbers.

End of Spec.
