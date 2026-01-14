# SPEC AUTH-00 — Authentication, Authorization & Tenancy

ID: AUTH-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
Prevent unauthorized access and enforce strict tenant isolation for Ops and Customer interfaces.

## 2. Interfaces
- Internal: Ops API under `/ops/*`
- Customer: Transparency API under `/transparency/*` (or equivalent)

## 3. Authentication (AuthN)
- All non-public endpoints MUST require authentication.
- Acceptable mechanisms:
  - Demo: static API key (header) OR basic auth (TLS required)
  - Production: JWT bearer tokens (recommended) OR mTLS (service-to-service)

## 4. Authorization (AuthZ)
The system MUST implement role-based access control with at least:
- role: `ops_admin` (read/write)
- role: `ops_read`  (read-only)
- role: `customer_read` (read-only; customer scope only)

Rules:
- `/ops/*` endpoints MUST require `ops_admin` or `ops_read` (write requires `ops_admin`).
- `/transparency/*` endpoints MUST require `customer_read` scoped to a tenant.

## 5. Tenancy & isolation
- Customer-visible data MUST be partitioned by `tenant_id`.
- Every customer-scoped request MUST carry a tenant identity derived from auth (not from user input).
- The API MUST enforce `tenant_id` filtering server-side for all customer endpoints.
- The API MUST NOT allow cross-tenant access under any circumstances.

## 6. Auditing (security-relevant events)
The system MUST log:
- auth.success (role, subject_id, tenant_id?, path, method)
- auth.failure (reason, path, method, source_ip?)
- authz.denied (required_role, actual_role, path)
Events MUST NOT log secrets/tokens.

## 7. CORS & browser safety (if UIs are separate origins)
- CORS MUST be explicit allowlist by origin for browser clients.
- Credentials MUST NOT be allowed unless necessary.
- Preflight handling MUST be tested.

## 8. Secrets management
- Secrets MUST be provided via environment variables or a secret manager.
- Secrets MUST NOT be written to logs (OBS-00 pii/sinks MUST forbid).

End of Spec.
