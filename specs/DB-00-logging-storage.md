# SPEC DB-00 — Logging Storage (PostgreSQL + JSONB)

ID: DB-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## 1. Intent
Define the baseline database choice and storage model for structured observability events and traceability records.

## 2. Database choice (baseline)
- The system MUST use PostgreSQL as the primary logging database.
- Event payloads MUST be stored using JSONB.

Rationale (non-normative):
- JSONB supports evolving schemas with strong indexing and query capabilities.
- PostgreSQL provides reliable transactional writes and predictable ops.

## 3. Storage model (minimum)
The database MUST support:
- Append-only event ingestion (structured logs)
- Efficient retrieval by:
  - session_id
  - time range
  - event_type
  - severity
  - audience/visibility (if present)
- Retention policies (time-based deletion/partitioning)

## 4. Performance & realtime constraints
- DB writes MUST NOT occur on the realtime hot path.
- Persistence MUST follow OBS-00 sink requirements:
  - enqueue-only on hot path
  - async/batched ingestion worker
  - degrade mode under backpressure

(Reference: OBS-00 §6 Observability Sink Requirements)

## 5. Indexing (minimum expectations)
- The implementation MUST provide indexes for:
  - (session_id, ts)
  - (event_type, ts)
  - (severity, ts)
- Additional indexes MAY be added based on UI query patterns.

## 6. Evolution
- The design MUST allow future additions:
  - partitioning by time
  - separate customer-visible materialized views or tables
  - export to analytics store (optional)
without changing the event contract.

End of Spec.
