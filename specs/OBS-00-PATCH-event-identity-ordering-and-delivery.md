# SPEC OBS-00 — PATCH: Event Identity, Ordering & Delivery Semantics

ID: OBS-00-PATCH
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
Strengthen OBS-00 to support robust deduplication, pagination, and live streaming without ambiguity.

## 2. New required fields (add to OBS-00 common fields)
All events MUST include:
- event_id: ULID or UUID (unique per event)
- schema_version: string (e.g., "obs-00@1.2")
- ingested_at: RFC3339 timestamp set by the ingesting service

## 3. Delivery semantics
- Event delivery is AT-LEAST-ONCE.
- Consumers (UI, processors) MUST deduplicate using `event_id`.
- Ordering:
  - canonical order is by `ts`, tie-broken by `event_id`
  - ingestion order MAY differ; `ingested_at` enables stable cursors

## 4. Cursor recommendations (for API endpoints)
For incremental fetching, prefer cursor based on:
- (ingested_at, event_id) monotonic pagination.

## 5. Compatibility
- If legacy events without event_id exist, they MUST be treated as non-deduplicable legacy and should be phased out.

End of Spec.
