# spraak_demo specs (master)

This folder is the single source of truth for all specs.

Core:
- Control plane + Voice pipeline + DB + Ops API must comply with ENFORCED specs.

UIs:
- Ops Console (internal): primarily uses `specs/web/*`, `OBS-00*`, `API-00*`, `AUTH-00`.
- Transparency Portal (customer, optional): uses `CUST-LOG-00`, `SAN-00`, `DATA-RET-00`, `AUTH-00`.

Notes:
- `OBS-00-PATCH-*` is an ENFORCED patch to apply to OBS-00 (event_id, schema_version, ingested_at, at-least-once).
- Hosting/provider choices are intentionally not locked in (see DEPLOY-00).

Do not duplicate specs into subprojects; reference this folder.
