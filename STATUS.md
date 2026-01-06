# STATUS.md — Current Running Setup (spraak_demo)

> This file is meant to be copy/pasted into new chats when context is low.
> **No secrets** belong in this file. Keep it current.

## Project
- **Repo**: `Memmaker-lab/spraak_demo`
- **LiveKit**:
  - `LIVEKIT_URL`: (see `.env_local`, do not paste secrets)
  - **Telephony inbound dispatch rule** uses `roomPrefix: "call-"` and `agentName: "Emp AI"`

## What is running (local)

### Control Plane (webhooks + control API)
- **Server**: FastAPI via `python -m control_plane`
- **Port**: `8000`
- **Health**: `GET /health` → `200 {"status":"ok","component":"control_plane"}`
- **LiveKit webhook endpoint**: `POST /webhook`
- **Control API**:
  - `POST /control/call/hangup` body: `{"session_id":"call-..."}`

### Voice Pipeline (LiveKit Agents)
- **Worker**: `python -m voice_pipeline.agent dev`
- **Important**: must match SIP dispatch rule agent name:
  - `export LIVEKIT_AGENT_NAME="Emp AI"`

## ngrok (webhooks)
- **Tunnel**: `ngrok http 8000`
- **Expected**:
  - `https://<ngrok>.ngrok-free.dev/health` → 200
  - Webhook URL in LiveKit Cloud must be:
    - `https://<ngrok>.ngrok-free.dev/webhook`
- **Inspector**: `http://127.0.0.1:4040`

## Quick commands (copy/paste)

### Start Control Plane
```bash
python -m control_plane
```

### Start ngrok
```bash
ngrok http 8000
```

### Start Voice Agent for telephony
```bash
export LIVEKIT_AGENT_NAME="Emp AI"
python -m voice_pipeline.agent dev
```

### Test local health
```bash
curl -i http://127.0.0.1:8000/health
```

### Test ngrok health
```bash
curl -i https://<ngrok>.ngrok-free.dev/health
```

### Test webhook endpoint (expects Authorization)
```bash
curl -i https://<ngrok>.ngrok-free.dev/webhook \
  -X POST -H 'Content-Type: application/json' -H 'Authorization: Bearer test' \
  -d '{}'
```

## Known gotchas
- If telephony dispatch rule specifies `agentName`, the worker **must** set `LIVEKIT_AGENT_NAME` to the same value.
- ngrok `502` usually means upstream (local server/port) is not reachable, or you requested a route that doesn't exist (e.g. `GET /`).


