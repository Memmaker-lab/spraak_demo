## Voice Pipeline

Telephone-native Dutch voice AI using LiveKit Agents.

### Architecture

The Voice Pipeline implements real-time audio processing:

```
┌─────────────┐
│   Caller    │
│  (Phone)    │
└──────┬──────┘
       │ SIP
       ▼
┌─────────────────────────────────────────┐
│         LiveKit Room                     │
│  ┌────────────────────────────────────┐ │
│  │      Voice Pipeline Agent          │ │
│  │                                    │ │
│  │  STT (Groq) → LLM (Groq) → TTS    │ │
│  │                            (Azure) │ │
│  │                                    │ │
│  │  VAD: Silero                       │ │
│  │  Observability: OBS-00 events      │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

### Responsibilities (per SP-00)

**Voice Pipeline MUST:**
- Handle real-time audio I/O
- Process STT → LLM → TTS pipeline
- Emit structured events (OBS-00)
- Implement telephone-native UX (VC-00, VC-01, VC-02, VC-03)

**Voice Pipeline MUST NOT:**
- Contain business logic or policy decisions (Control Plane responsibility)
- Make call routing decisions
- Manage session state beyond turn tracking

### Specifications

The Voice Pipeline implements:

- **VC-00**: Voice UX Principles (Dutch, concise, human tone)
- **VC-01**: Turn-Taking (observable turn lifecycle, VAD-only mode)
- **VC-02**: Silence Handling (delay acknowledgement, graceful close)
- **VC-03**: Barge-in (immediate TTS stop on user speech)
- **OBS-00**: Observability (structured JSON events)
- **RL-00**: Rate Limiting (graceful provider error handling)

### Providers

- **STT**: Groq `whisper-large-v3` (Dutch)
- **LLM**: Groq `qwen/qwen3-32b` (configurable)
- **TTS**: Azure Speech `nl-NL-FennaNeural` (configurable)
- **VAD**: Silero (default LiveKit VAD)

### Configuration

Set the following environment variables (see `.env_local`):

```bash
# LiveKit
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_api_key
LIVEKIT_API_SECRET=your_api_secret

# Groq (STT + LLM)
GROQ_API_KEY=your_groq_key
GROQ_MODEL_LLM=qwen/qwen3-32b  # Optional, default

# Azure TTS
AZURE_SPEECH_KEY=your_azure_key
AZURE_SPEECH_REGION=westeurope
AZURE_SPEECH_VOICE=nl-NL-FennaNeural  # Optional, default
AZURE_SPEECH_OUTPUT_FORMAT=Raw48Khz16BitMonoPcm  # Optional
```

### Running the Agent

#### 1. Install dependencies

```bash
pip install -r requirements.txt
```

Or with uv:

```bash
uv pip install -r requirements.txt
```

#### 2. Set environment variables

```bash
# Copy and edit .env_local with your credentials
source .env_local  # or use direnv
```

#### 3. Run the agent worker

```bash
python -m voice_pipeline.agent
```

Or using the LiveKit CLI:

```bash
livekit-agents start voice_pipeline.agent
```

The agent will:
1. Connect to LiveKit Cloud
2. Wait for dispatch (inbound call or API trigger)
3. Join the room and start conversation
4. Emit structured logs to stdout

### Dispatch Configuration

The agent must be dispatched to rooms via:

1. **LiveKit Dispatch Rules** (for inbound calls):
   - Go to LiveKit Cloud → Agents → Dispatch
   - Create rule: "On inbound call → dispatch agent"
   - Agent name: must match `LIVEKIT_AGENT_NAME` when using explicit dispatch (telephony recommended)

2. **API dispatch** (for outbound calls):
   ```python
   from livekit import api
   
   livekit_api = api.LiveKitAPI(
       url=LIVEKIT_URL,
       api_key=LIVEKIT_API_KEY,
       api_secret=LIVEKIT_API_SECRET,
   )
   
   # Dispatch agent to room
   await livekit_api.room.create_room(api.CreateRoomRequest(name="my-room"))
   ```

### Observability

All events are emitted as structured JSON to stdout per OBS-00:

```json
{
  "ts": "2026-01-05T16:30:00Z",
  "session_id": "room_abc123",
  "component": "voice_pipeline",
  "event_type": "turn.started",
  "severity": "info",
  "correlation_id": "turn_1704470400000"
}
```

Key events:
- `vad.state_changed` - VAD state transitions
- `turn.started` - New turn begins (user speech committed)
- `stt.final` - Final STT result (metadata only)
- `llm.request` - LLM request started
- `llm.response` - LLM response ready
- `tts.started` - Agent starts speaking
- `tts.stopped` - Agent stops speaking (cause: completed | barge_in | error)
- `barge_in.detected` - User interrupted TTS (VC-03)
- `ux.delay_acknowledged` - Processing took long; user got a Dutch acknowledgement (VC-02)
- `silence.timer_started` / `silence.timer_fired` - Silence instrumentation (VC-02)
- `call.ended` - Graceful close path on user silence (VC-02)

See `LOGGING.md` for log aggregation and analysis.

### Silence handling thresholds (VC-02)

You can tune VC-02 timing with environment variables (milliseconds):

```bash
# Processing silence: after this, agent says “Momentje, ik denk even mee.”
VP_PROCESSING_DELAY_ACK_MS=900

# User silence: after agent finished speaking, reprompt after this delay
VP_USER_SILENCE_REPROMPT_MS=7000

# User silence: after this total delay, graceful close + call.ended
VP_USER_SILENCE_CLOSE_MS=14000
```

### Testing

Run tests:

```bash
pytest tests/test_voice_*.py -v
```

Tests cover:
- Configuration loading
- Instructions conformance to VC-00
- Observability event emission
- Barge-in detection (VC-03)
- Turn lifecycle (VC-01)

### Telephony Integration

For inbound calls:

1. Configure SIP trunk in LiveKit Cloud
2. Set up dispatch rule to trigger agent
3. Call the phone number
4. Agent answers and starts conversation

#### Agent name matching (common pitfall)

If your SIP dispatch rule includes `roomConfig.agents[].agentName` (e.g. `"Emp AI"`),
you MUST start the worker with the same agent name:

```bash
export LIVEKIT_AGENT_NAME="Emp AI"
python -m voice_pipeline.agent dev
```

If you don't, the worker registers under the default/empty agent name and won't be selected.

For outbound calls:

1. Use Control Plane to initiate call
2. Control Plane dispatches agent to room
3. Agent joins and starts conversation

See `control_plane/README.md` for call control.

### Control Plane hangup (CP-03)

For real telephony calls, ending only the agent session can leave the caller hearing silence.
To hang up for all participants, start the Control Plane and set:

```bash
export CONTROL_PLANE_URL=http://127.0.0.1:8000
```

The voice pipeline will then call:

```text
POST /control/call/hangup  { "session_id": "<room_name>" }
```

LiveKit ends the call by deleting the room (telephony docs: hangup -> delete_room).

### Customization

#### Change LLM instructions

Edit `voice_pipeline/instructions.py`:

```python
AGENT_INSTRUCTIONS = """
Je bent een doktersassistent...
"""
```

#### Change TTS voice

Set in `.env_local`:

```bash
AZURE_SPEECH_VOICE=nl-NL-ColetteNeural
```

See [Azure voices](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=tts) for options.

#### Change LLM model

Set in `.env_local`:

```bash
GROQ_MODEL_LLM=llama-3.3-70b-versatile
```

See [Groq models](https://console.groq.com/docs/models) for options.

### Troubleshooting

**Agent not dispatched:**
- Check dispatch rules in LiveKit Cloud
- Verify agent worker is running
- Check logs for connection errors

**No audio:**
- Verify SIP trunk configuration
- Check LiveKit room participants
- Verify provider API keys

**Poor transcription:**
- Check audio quality (SIP codec)
- Verify STT language setting (nl)
- Check Groq API status

**Slow responses:**
- Check LLM latency in logs (`latency_from_user_audio_ms`)
- Consider faster LLM model
- Check network latency to providers

### Development

File structure:

```
voice_pipeline/
├── __init__.py          # Module initialization
├── agent.py             # Main agent entrypoint
├── config.py            # Configuration loading
├── instructions.py      # LLM system instructions
├── observability.py     # Event emission (OBS-00)
└── README.md            # This file

tests/
├── test_voice_config.py          # Config tests
├── test_voice_instructions.py    # Instructions tests
└── test_voice_observability.py   # Observability tests
```

### Next Steps

- [ ] Add EOU-00 mode (VAD + End-of-Utterance detection)
- [ ] Implement RL-00 rate limiting with user-friendly Dutch messages
- [ ] Add function tools for actions (ACT-00)
- [ ] Integrate with Control Plane for session management

### References

- [LiveKit Agents Docs](https://docs.livekit.io/agents/)
- [Groq Integration](https://docs.livekit.io/agents/integrations/groq/)
- [Azure TTS Plugin](https://docs.livekit.io/agents/models/tts/plugins/azure/)
- Specs: `specs/voice/VC-*.md`

