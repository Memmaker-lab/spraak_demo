# Logging Infrastructure

## Overview

spraak_demo uses a **dual logging system** designed for both operational debugging and structured observability:

1. **Structured JSON Logging** (`logging_setup.py`) - For general application logs (debug, info, warnings, errors)
2. **OBS-00 Event Emission** (`control_plane/events.py`) - For structured business events per OBS-00 specification

Both systems output JSON to `stdout` for easy integration with log aggregation tools.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Application Code                       │
│  (Control Plane, Voice Pipeline, etc.)                   │
└────────────┬────────────────────────────┬────────────────┘
             │                            │
             │ General Logs               │ Business Events
             ▼                            ▼
  ┌──────────────────────┐    ┌──────────────────────┐
  │  StructuredLogger    │    │   EventEmitter       │
  │  (logging_setup.py)  │    │   (events.py)        │
  └──────────┬───────────┘    └──────────┬───────────┘
             │                            │
             │ JSON logs                  │ OBS-00 events
             ▼                            ▼
  ┌─────────────────────────────────────────────────────┐
  │                     stdout                           │
  │  → File redirect, log aggregator, or terminal        │
  └─────────────────────────────────────────────────────┘
```

## When to Use Which System

### Use StructuredLogger for:
- ✅ Debugging information (e.g., "Processing webhook", "Connecting to service")
- ✅ Operational status (e.g., "Server started on port 8000")
- ✅ Internal errors and warnings
- ✅ Performance metrics
- ✅ Development and troubleshooting

### Use EventEmitter for:
- ✅ Business events per OBS-00 (e.g., `call.started`, `session.state_changed`)
- ✅ Audit trails requiring stability (event types must not change)
- ✅ Events requiring PII handling metadata
- ✅ Cross-system correlation via `session_id`
- ✅ Events consumed by monitoring/analytics systems

## Using StructuredLogger

### Basic Usage

```python
from logging_setup import get_logger, Component

# Create a logger for your component
logger = get_logger(Component.CONTROL_PLANE)

# Log messages
logger.info("Server started", port=8000)
logger.debug("Processing request", request_id="req_123")
logger.warning("Rate limit approaching", limit=100, current=95)
logger.error("Database connection failed", error="Connection timeout")
```

### With Session Correlation

```python
# Create a logger with session ID
session_logger = logger.with_session("sess_abc123")
session_logger.info("User authenticated")
session_logger.debug("Fetching user profile")

# Or pass session_id at creation
logger = get_logger(Component.VOICE_PIPELINE, session_id="sess_abc123")
```

### PII-Aware Logging

When logging personally identifiable information, use the `_pii` methods to explicitly mark PII fields:

```python
# PII is logged in a separate 'pii' field for audit awareness
logger.info_pii("Call initiated", phone="+31612345678")
logger.debug_pii("User lookup", email="user@example.com", name="John Doe")

# Output:
# {
#   "timestamp": "2026-01-05T10:30:00Z",
#   "severity": "info",
#   "component": "control_plane",
#   "message": "Call initiated",
#   "pii": {"phone": "+31612345678"}
# }
```

### Exception Logging

```python
try:
    risky_operation()
except Exception as e:
    logger.error("Operation failed", error=str(e), exc_info=True)
    # exc_info=True includes full stack trace in 'exception' field
```

### Application Startup

Configure logging once at application startup:

```python
from logging_setup import setup_logging

# JSON format (production)
setup_logging(level="INFO", use_json=True)

# Text format (local development)
setup_logging(level="DEBUG", use_json=False)
```

## Using EventEmitter (OBS-00)

For business events, use the `EventEmitter` from `control_plane/events.py`:

```python
from control_plane.events import control_plane_emitter

# Emit structured events
control_plane_emitter.call_started(
    session_id="sess_123",
    direction="inbound",
    livekit_room="room_abc",
)

control_plane_emitter.session_state_changed(
    session_id="sess_123",
    from_state="created",
    to_state="connected",
)
```

See `specs/OBS-00-observability-and-control-contract.md` for full event taxonomy.

## Component Types

Available components (extend as needed):

```python
Component.CONTROL_PLANE       # Control plane orchestration
Component.VOICE_PIPELINE       # Real-time audio processing
Component.WEBHOOK_SERVER       # Webhook handling
Component.SESSION_MANAGER      # Session lifecycle management
Component.ERROR_HANDLER        # Error classification and handling
Component.LIVEKIT_TRANSPORT    # LiveKit integration
Component.STT                  # Speech-to-Text
Component.LLM                  # Language Model
Component.TTS                  # Text-to-Speech
Component.VAD                  # Voice Activity Detection
```

Or use custom strings:

```python
logger = get_logger("my_custom_component")
```

## Log Output Format

All logs are emitted as single-line JSON to `stdout`:

```json
{
  "timestamp": "2026-01-05T10:30:00.123456+00:00",
  "severity": "info",
  "component": "control_plane",
  "session_id": "sess_abc123",
  "message": "Call initiated",
  "caller_hash": "hash_xyz",
  "direction": "inbound"
}
```

Reserved fields:
- `timestamp` - ISO8601 UTC timestamp
- `severity` - Log level (debug, info, warning, error, critical)
- `component` - Component identifier
- `message` - Human-readable message
- `session_id` - Optional session correlation ID
- `pii` - PII fields (if using `_pii` methods)
- `exception` - Stack trace (if `exc_info=True`)

All other fields are custom and component-specific.

## Integration with Voice Pipeline

The Voice Pipeline will use the same `logging_setup` module:

```python
# In voice pipeline modules
from logging_setup import get_logger, Component

logger = get_logger(Component.VOICE_PIPELINE, session_id=session_id)

# STT module
stt_logger = get_logger(Component.STT, session_id=session_id)
stt_logger.debug("Transcribing audio chunk", chunk_size=1024)

# LLM module
llm_logger = get_logger(Component.LLM, session_id=session_id)
llm_logger.info("Sending prompt", token_count=150)

# TTS module
tts_logger = get_logger(Component.TTS, session_id=session_id)
tts_logger.debug("Synthesizing speech", text_length=45)
```

## Environment Configuration

Control log level via environment variable (future):

```bash
export LOG_LEVEL=DEBUG  # DEBUG, INFO, WARNING, ERROR, CRITICAL
export LOG_FORMAT=json  # json or text
```

Or programmatically:

```python
import os
from logging_setup import setup_logging

level = os.getenv("LOG_LEVEL", "INFO")
use_json = os.getenv("LOG_FORMAT", "json") == "json"

setup_logging(level=level, use_json=use_json)
```

## Testing

Tests are in `tests/test_logging_setup.py`. Run with:

```bash
pytest tests/test_logging_setup.py -v
```

## Privacy Considerations

Per `SP-00-system-principles.md`:

- ✅ **PII logging is allowed** for audit/ops purposes
- ✅ Use `logger.info_pii()` / `logger.debug_pii()` to explicitly mark PII
- ✅ PII is logged in a separate `pii` field for awareness
- ❌ Never send PII to external providers unless required
- ❌ Never log raw API keys or secrets (redact or hash)

Example:

```python
# Good: Explicit PII logging for audit
logger.info_pii("Call received", phone="+31612345678")

# Bad: PII mixed with regular fields
logger.info("Call received", phone="+31612345678")  # Should use info_pii
```

## Redirection and Aggregation

### Save logs to file

```bash
python -m control_plane > logs/control_plane.log 2>&1
```

### Aggregate with tools

- **jq**: Parse and filter JSON logs
  ```bash
  python -m control_plane | jq 'select(.severity=="error")'
  ```

- **Logstash/Fluentd**: Forward to centralized logging

- **CloudWatch/Stackdriver**: Stream stdout to cloud logging

## Future Enhancements

- Log rotation and archiving
- Structured sampling for high-volume logs
- Integration with tracing (OpenTelemetry)
- Log redaction for sensitive fields
- Performance metrics collection

