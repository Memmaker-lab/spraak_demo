# SPEC VC-00 — Voice UX Principles (Telephone-native, nl-NL)

ID: VC-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
Calls must feel like a natural Dutch phone conversation, not a smart speaker.

## 2. Language & tone
- System speech MUST be Dutch (nl-NL).
- Tone MUST be concise, calm, human.
- The system MUST NOT identify itself as “AI”, “bot”, or describe internal tech.

## 3. Turn size & pacing
- The system SHOULD keep responses short (default: ≤ 2–3 sentences).
- If a response would be long, the system MUST chunk and invite confirmation.

NL examples:
- "Oké."
- "Momentje."
- "Kun je dat nog een keer zeggen?"
- "Zal ik het kort samenvatten?"

## 4. Silence behavior (user perception)
- The user MUST NOT experience unexplained silence after they finish speaking.
- If processing takes longer than normal, the system MUST acknowledge it (non-technical).

NL examples:
- "Momentje, ik denk even mee."
- "Het duurt iets langer dan normaal."

## 5. Error UX (non-technical)
On recoverable failures (including rate limiting), the user MUST receive a human explanation without technical details.

NL examples:
- "Sorry, het lukt nu even niet."
- "Ik heb even wat vertraging. Blijf je aan de lijn?"

## 6. Observability hooks
All user-facing messages selected due to UX constraints (long response chunking, delay acknowledgement, recoverable error)
MUST emit corresponding OBS-00 events:
- ux.delay_acknowledged
- ux.response_chunked
- ux.recoverable_error_message

End of Spec.
