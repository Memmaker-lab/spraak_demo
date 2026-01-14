# SPEC WEB-04 — Visual Design System

TOOL: Lovable (primary)
ID: WEB-04
VERSION: 1.1
STATUS: TESTABLE
APPLIES_TO: demo

## 1. Intent
A calm, modern, high-readability dashboard suitable for long debugging sessions.

## 2. Style references (conceptual)
- Trace-view layout (timeline left, inspector right)
- Incident grouping + drilldown
- Minimal tables with subtle badges

## 3. Design rules
- Lots of whitespace, thin borders, subtle shadows
- Monospace only for IDs/timestamps/JSON
- Badges for status and severity (subtle, consistent)
- Dark mode optional (not required)
- Avoid visual noise: no heavy charts in v1

## 4. Components (minimum)
- Sessions table with sticky header
- Filter bar (chips + dropdowns)
- Timeline list with grouping/collapse
- Transcript bubble view
- Inspector panel with raw JSON + copy
- Toasts and confirm modals

End of Spec.
