# SPEC LK-00 — LiveKit Integration Boundary

ID: LK-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
LiveKit provides realtime transport (WebRTC) and telephony bridging.
Our system builds around LiveKit for media/session transport while keeping STT/LLM external.

## 2. Transport choice
- WebRTC transport MUST use LiveKit rooms/participants/tracks model.
- Telephony integration MUST use LiveKit telephony (SIP trunks/dispatch rules) where applicable.

## 3. Correlation & session mapping
- Each call MUST map to exactly one session_id.
- session_id MUST be correlated to LiveKit room + participant identifiers in OBS-00 events.
- LiveKit lifecycle signals SHOULD be captured via webhooks/events for reliable auditing.

## 4. Voice pipeline implementation note (Python)
If LiveKit Agents are used, they MUST be treated as part of the Voice Pipeline boundary.
Agent APIs for endpointing/interruptions/tool calls MUST still comply with SP-00 separation and OBS-00 logging.

## 5. External model providers
- STT and LLM MAY be external cloud providers.
- LiveKit TTS MAY be used, but all providers MUST follow SP-00 privacy rules and RL-00 rate limiting behavior.

End of Spec.
