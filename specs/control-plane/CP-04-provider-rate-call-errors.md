# SPEC CP-04 — Telephony Provider Errors & Limits (SIP/PSTN)

ID: CP-04
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
Telephony/SIP providers and PSTN can fail in predictable ways (busy, no answer, rejected, auth issues, limits).
The system MUST handle these without crashes and with clear (non-technical) user outcomes.

This spec is provider-agnostic: it MUST NOT assume specific error codes from Twilio, CheapConnect, or any SIP gateway.

## 2. Error classification (stable categories)
The Control Plane MUST map any provider error/termination into one of these categories:

Call setup / routing:
- provider.auth_failed
- provider.misconfigured
- provider.network_error

Call outcome:
- call.busy
- call.no_answer
- call.rejected
- call.failed

Limits / throttling:
- provider.rate_limited
- provider.capacity_limited

Unknown:
- provider.unknown_error

## 3. Required behavior (non-crash, deterministic)
- Any provider error MUST result in a clean terminal session state and call.ended { reason } (CP-01).
- No provider error MUST crash the process or leave the session in a non-terminal limbo state.
- Retries (if any) MUST be bounded and explicitly configured.
  - For rate/capacity limits, bounded backoff MAY be applied (align with RL-00 style).
  - For auth/misconfiguration, retries MUST NOT loop; fail fast.

## 4. Observability requirements (OBS-00)
On any provider-related failure/limit, the Control Plane MUST emit:

- provider.event { category, detail? }
  where category is one of the stable categories in §2
- call.ended { reason }

Events MUST include:
- session_id
- direction (inbound/outbound)
- provider.name (if known)
- livekit correlation fields (room/participant) when available

Raw provider error messages/codes MAY be stored only in a redacted/debug field and MUST NOT contain secrets.

## 5. User-facing messaging (non-technical, Dutch)
User-facing phrasing is produced via the voice pipeline UX layer (VC-00), but Control Plane MUST provide a stable
"reason key" for UX selection.

Minimum mapping (examples):
- call.busy → "Het nummer is in gesprek. Zullen we later nog eens proberen?"
- call.no_answer → "Er wordt niet opgenomen. Wil je het later opnieuw proberen?"
- provider.rate_limited / provider.capacity_limited → "Momentje, het is even druk. Probeer het zo nog eens."
- provider.auth_failed / provider.misconfigured → No technical details to end user; use generic:
  "Sorry, het lukt nu even niet."

Control Plane MUST NOT expose technical details (codes, provider names) in user-facing text.

## 6. Testability (ENFORCED)
Tests MUST exist and MUST pass for:
- each category in §2 maps to a terminal call.ended reason
- no infinite retry loops (bounded retries)
- correct emission of provider.event + call.ended with session_id
- redaction rule: no secrets or raw credentials in logs

End of Spec.
