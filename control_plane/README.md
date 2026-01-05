# Control Plane

Control Plane implementation per CP-00 through CP-04.

## Overview

The Control Plane handles:
- Session lifecycle management (CP-01)
- Inbound/outbound call orchestration via LiveKit SIP (CP-02)
- Structured event emission per OBS-00
- Error handling per CP-04
- No audio processing (strict separation per SP-00)

## Configuration

Set in `.env_local`:
- `LIVEKIT_URL` - LiveKit server URL
- `LIVEKIT_API_KEY` - API key
- `LIVEKIT_API_SECRET` - API secret
- `CALLER_ID` - Caller ID for outbound calls (default: +3197010206472)

## Running the Webhook Server

The webhook server receives LiveKit webhook events for inbound calls:

```bash
python -m control_plane
```

Or using uvicorn directly:
```bash
uvicorn control_plane.webhook_server:app --host 0.0.0.0 --port 8000
```

## Webhook Configuration

Configure the webhook URL in LiveKit Cloud dashboard:
- URL: `https://your-server/webhook`
- Events: `room_started`, `participant_joined`, `participant_left`, `track_published`, `room_finished`

## Usage

### Session Management

```python
from control_plane.session import session_manager

# Create session for inbound call
session = session_manager.create_session(
    direction="inbound",
    caller_number="+31612345678",
)

# Get session
session = session_manager.get_session(session_id)

# List sessions
sessions = session_manager.list_sessions(state=SessionState.CONNECTED)
```

### Event Emission

```python
from control_plane.events import control_plane_emitter

# Emit call started
control_plane_emitter.call_started(
    session_id="...",
    direction="inbound",
    livekit_room="room-name",
)

# Emit call ended
control_plane_emitter.call_ended(
    session_id="...",
    reason="participant_left",
)
```

### Error Handling

```python
from control_plane.errors import ProviderErrorHandler

try:
    # Make call...
except Exception as e:
    category = ProviderErrorHandler.handle_error(
        session_id="...",
        error=e,
        direction="inbound",
        provider_name="livekit",
    )
    user_message = ProviderErrorHandler.get_user_message(category)
```

## Architecture

- `config.py` - Configuration management
- `session.py` - Session lifecycle (CP-01)
- `events.py` - OBS-00 event emission
- `webhook_handler.py` - LiveKit webhook processing
- `webhook_server.py` - FastAPI webhook server
- `errors.py` - Provider error handling (CP-04)

## Next Steps

- [ ] Outbound call implementation (when outbound trunk is ready)
- [ ] Control API (CP-03) - REST API for website/app
- [ ] Webhook signature verification (proper JWT validation)
- [ ] Tests per CP-04 ENFORCED requirements

