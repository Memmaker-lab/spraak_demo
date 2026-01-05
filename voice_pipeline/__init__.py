"""
Voice Pipeline for spraak_demo.

Real-time audio processing: STT → LLM → TTS
No business logic or policy decisions (Control Plane responsibility).

Per SP-00:
- Voice Pipeline MUST NOT contain business/policy decisions
- Voice Pipeline handles realtime I/O and STT→LLM→TTS behavior
- All behavior MUST be observable via structured events (OBS-00)

Per VC-00:
- Telephone-native Dutch conversation
- Concise, calm, human tone
- No AI identification
"""

