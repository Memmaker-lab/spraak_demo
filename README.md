# spraak_demo

This repo contains **spec-first** system specifications and Cursor rules for a telephone-native Dutch voice demo.
Implementation is intentionally left to Cursor (Python-only, current phase).

Start here:
- `specs/SP-00-system-principles.md`
- `specs/NFR-00-non-functional-requirements.md`
- `specs/OBS-00-observability-and-control-contract.md`

Cursor rules:
- `.cursor/rules/00-global.mdc` (Always)
- `.cursor/rules/10-spec-authoring.mdc` (Auto attached to specs)
- `.cursor/rules/20-voice-instrumentation.mdc` (Auto attached to voice/pipeline)
