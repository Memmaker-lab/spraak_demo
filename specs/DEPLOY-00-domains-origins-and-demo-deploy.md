# SPEC DEPLOY-00 — Domains, Origins & Demo Deployment Constraints

ID: DEPLOY-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo

## 1. Intent
Define the demo domain layout and browser-origin constraints so UI↔API integration is predictable, secure-by-default, and testable.

## 2. Demo domain layout (recommended)
- Public landing (optional): `www.intari.nl`
- Internal tracing UI (Ops Console): `ops.intari.nl`
- Backend API (Ops API): `api.intari.nl`
- Customer portal (optional/later): `customer.intari.nl`

## 3. TLS (required)
- All public endpoints MUST use HTTPS (TLS).
- Plain HTTP MUST NOT be used for any UI or API surface.

## 4. CORS policy (required)
- The API MUST enforce an explicit allowlist of browser origins.
- Minimum allowlist for demo:
  - `https://ops.intari.nl`
  - `https://www.intari.nl` (if it calls the API)
  - `https://customer.intari.nl` (if enabled)
- The API MUST reject requests from origins not on the allowlist.

## 5. Auth posture by surface (demo)
- Ops Console (`ops.intari.nl`) MUST be access restricted:
  - acceptable demo controls: basic auth, IP allowlist, or access proxy
- Ops API write endpoints MUST require authenticated access (AUTH-00).
- Customer portal endpoints MUST enforce tenant scoping (AUTH-00) and sanitization (SAN-00).

## 6. Environment configuration (required)
All apps MUST be configurable via environment variables:
- UI apps:
  - API_BASE_URL (e.g., `https://api.intari.nl`)
- API:
  - OPS_CONSOLE_ORIGIN (for allowlist)
  - CUSTOMER_PORTAL_ORIGIN (if enabled)
  - AUTH_MODE = demo | prod

## 7. Non-goals (demo)
- No requirement to lock in a hosting provider (Vercel/Netlify/Pages/Render are interchangeable)
- DNS record details are out of scope

End of Spec.
