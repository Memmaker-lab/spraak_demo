# SPEC DATA-RET-00 — Retention, Consent & Deletion (Privacy/AVG Readiness)

ID: DATA-RET-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
Define minimal privacy controls for storing transcripts and traceability data, enabling later AVG compliance.

## 2. Data classes
- Operational telemetry (non-PII): metrics, timings, errors
- Customer content (PII-likely): transcripts, names, phone numbers
- Internal debug (sensitive): raw provider payloads, prompts (if stored)

## 3. Consent gate (transcripts)
- Transcript storage MUST be controlled by an explicit configuration:
  - env-level toggle (demo/prod)
  - tenant policy (customer)
- If transcript storage is disabled, transcript fields MUST NOT be persisted.

## 4. Retention (minimum)
- The system MUST support configurable retention windows per data class:
  - telemetry_retention_days
  - transcript_retention_days
  - customer_report_retention_days
Defaults MAY differ between demo and production.

## 5. Deletion (minimum capability)
The system MUST support deletion by:
- session_id
- tenant_id (customer)
Deletion MUST remove or irreversibly redact customer content within the scope.

## 6. Exports (later-safe)
- The system SHOULD be able to export a customer report for a session_id in a portable format.
- Export MUST respect sanitization and consent.

## 7. Security controls (minimum)
- Data in transit MUST use TLS.
- Data at rest SHOULD be encrypted (managed DB encryption acceptable).
- Access MUST be logged (AUTH-00 audit events).

End of Spec.
