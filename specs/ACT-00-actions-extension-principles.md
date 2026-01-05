# SPEC ACT-00 — Actions Extension Principles

ID: ACT-00
VERSION: 1.0
STATUS: PLANNED
APPLIES_TO: demo, production

## Intent
Support future actions (send email, send summary, create tasks) without compromising realtime voice stability.

## Rules
- Actions MUST be asynchronous relative to realtime audio.
- Actions MUST be idempotent (safe to retry).
- Actions MUST follow SP-00 privacy minimization.
- Actions MUST be observable via OBS-00 action.* events.
- Action execution MUST NOT block turn-taking.

End of Spec.
