# SPEC CP-02 — SIP Telephony Boundary (Provider-agnostic)

ID: CP-02
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
Support inbound and outbound PSTN calls using SIP providers (e.g., Twilio or others)
bridged through LiveKit Telephony.

## 2. Inbound calls
- Inbound calls MUST be accepted via LiveKit inbound trunks.
- Inbound routing to a room MUST be configured via LiveKit SIP dispatch rules.
- The system MUST correlate inbound call metadata to session_id for audit (OBS-00).

## 3. Outbound calls
- Outbound calls MUST be initiated by creating a SIP participant through LiveKit Telephony APIs.
- Outbound calling MUST require an outbound trunk configured in LiveKit.

## 4. Provider abstraction
- The system MUST treat the SIP provider as replaceable configuration.
- Provider-specific settings (Twilio/CheapConnect) MUST be isolated to configuration and adapters,
  not scattered through business logic.

## 5. Security (telephony boundary)
- The system SHOULD enable secure trunking (TLS/SRTP) where supported.
- Credentials and secrets MUST NOT be logged.

End of Spec.
