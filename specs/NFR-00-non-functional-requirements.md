# SPEC NFR-00 — Non-Functional Requirements Overview

ID: NFR-00
VERSION: 1.0
STATUS: ENFORCED
APPLIES_TO: demo, production

## Relevance
NOW = enforced via specs/tests
LATER = relevant but not enforced yet (design must not block it)
OUT = out of scope

## Categories (selected)

### NOW
- Reliability / Fault handling
  Relevance: NOW
  Specs: SP-00, CP-01, CP-02, CP-04, RL-00, OBS-00, (EH-xx PLANNED)

- Latency & responsiveness
  Relevance: NOW
  Specs: SP-00, OBS-00, (VC-xx PLANNED), (EOU-00 PLANNED)
  Notes: measure transport + detection + model latencies separately.

- Security & privacy
  Relevance: NOW
  Specs: SP-00, OBS-00, LK-00, CP-02, CP-03

- Observability & auditability
  Relevance: NOW
  Specs: SP-00, CP-01, CP-03, CP-04, OBS-00, LK-00

- Testability
  Relevance: NOW
  Specs: SP-00, OBS-00, RL-00, TS-01, VC-02, VC-03

- Conversational UX
  Relevance: NOW
  Specs: SP-00, VC-00, VC-02, RL-00

- Epistemic quality (AI rules)
  Relevance: NOW
  Specs: SP-00 (Verified-Knowledge-Only)

### LATER
- Scalability
  Relevance: LATER
  Specs: (SC-xx PLANNED)

- Compliance details
  Relevance: LATER
  Specs: (CO-xx PLANNED)

- Accessibility
  Relevance: LATER
  Specs: (AX-xx PLANNED)

- Resource efficiency
  Relevance: LATER
  Specs: (RE-xx PLANNED)

### OUT
- Extreme performance tuning
- Multi-region HA
- Hard real-time guarantees

Rule: Any new NFR MUST be added here and mapped to concrete specs.
End of Spec.
