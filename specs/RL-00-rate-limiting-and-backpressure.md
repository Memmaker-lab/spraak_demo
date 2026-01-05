# SPEC RL-00 — Rate Limiting & Backpressure

ID: RL-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
Rate limits from external STT/LLM/TTS providers are expected.
The system MUST remain stable, recover when possible, and keep UX human.

## 2. Non-crash rule
- Rate limiting MUST NOT crash any process.
- MUST NOT propagate unhandled exceptions across the control/voice boundary.

## 3. Bounded retry & backoff
- Retries MUST be bounded (max_attempts per request type).
- Backoff MUST be deterministic/testable (seeded per session if jitter is used).
- If retry_after is provided, it SHOULD be honored.
- After exhaustion, the system MUST degrade gracefully (see UX).

## 4. User-facing UX (Dutch)
The user MUST be informed without technical details.
Examples:
- "Momentje, het duurt iets langer dan normaal."
- "Ik heb even wat vertraging. Blijf je aan de lijn?"
Persistent failure:
- "Sorry, het lukt nu even niet. Zullen we het straks nog eens proberen?"

## 5. Observability (mandatory)
On any rate limit:
- emit provider.rate_limited
- emit provider.retry_scheduled (if retrying)
- emit provider.request_failed (if giving up)
Events MUST include: provider.name, provider.model, request type, attempt, backoff_ms.

## 6. Privacy
Retries MUST NOT expand prompt/transcript content.
No additional PII may be sent during retries.

## 7. Testability
Tests MUST cover:
- bounded retries (no infinite loops)
- correct backoff decisions
- correct user-facing messaging selection
- system does not crash under repeated 429s

End of Spec.
