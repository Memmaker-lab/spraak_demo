# SPEC SAN-00 — Customer Sanitization Rules (Default-Deny)

ID: SAN-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: customer

## 1. Intent
Ensure that customer-facing data is safe, minimally sensitive, and cannot leak internal/debug information.

## 2. Default-deny policy
- All events are treated as `operator_only` unless explicitly marked `customer_visible`.
- For customer endpoints, the server MUST only emit:
  - events with `audience="customer"` AND `visibility="customer_visible"`
  - fields permitted by the whitelist (§3)

## 3. Field whitelist (customer)
Customer-visible events MAY include only:
- Common: ts, session_id, event_type, severity
- Flow: scenario_id?, step_id?, step_label?
- Transcript (optional): user_text?, assistant_text? (if enabled by consent; see DATA-RET-00)
- Actions (later): action_type, status, safe_result_summary, started_at/ended_at

All other fields MUST be removed or replaced with safe summaries.

## 4. Forbidden fields (hard ban)
Customer endpoints MUST NEVER expose:
- secrets, tokens, api keys
- raw provider request/response payloads
- raw HTTP headers
- internal prompts (system/developer) unless explicitly approved
- internal correlation IDs (optional: replace with customer-safe ids)
- infrastructure identifiers (hostnames, internal IPs, queue names)

## 5. Sanitization function (required)
- The implementation MUST use a single sanitizer function:
  - sanitize_for_customer(event) -> sanitized_event
- Sanitization MUST be unit-tested with allow/deny cases.

## 6. Failure behavior
- If an event cannot be safely sanitized, it MUST be dropped for customer output and a security event logged:
  - security.sanitization_dropped { event_type, reason }

End of Spec.
