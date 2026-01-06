# RUNBOOK.md — Local dev / ops (spraak_demo)

> No secrets in this file. Use `.env_local` for credentials (gitignored).

## Services and ports

- **Control Plane**: `python -m control_plane` → `http://127.0.0.1:8000`
  - `GET /health`
  - `POST /webhook` (LiveKit webhooks)
  - `POST /control/call/hangup` (CP-03 write control)

- **ngrok**: `ngrok http 8000`
  - Inspector: `http://127.0.0.1:4040`

- **Voice Pipeline (telephony worker)**: `python -m voice_pipeline.agent dev`
  - Must match dispatch rule agent name when explicit dispatch is used:
    - `LIVEKIT_AGENT_NAME="Emp AI"`

- **Voice Pipeline (local mic/speaker)**: `./test_voice.sh`

## Start order (recommended)

### 1) Start Control Plane

```bash
python -m control_plane
```

Verify:

```bash
curl -i http://127.0.0.1:8000/health
```

### 2) Start ngrok

```bash
ngrok http 8000
```

Verify:

```bash
curl -i https://<ngrok>.ngrok-free.dev/health
```

### 3) Configure LiveKit webhook URL

Set the webhook URL in LiveKit Cloud to:

```text
https://<ngrok>.ngrok-free.dev/webhook
```

### 4) Start the Voice Pipeline worker (telephony)

```bash
export LIVEKIT_AGENT_NAME="Emp AI"
python -m voice_pipeline.agent dev
```

## Environment variables (non-secret list)

### Voice Pipeline
- `LIVEKIT_AGENT_NAME` — must match SIP dispatch rule `agentName` (telephony)
- `CONTROL_PLANE_URL` — e.g. `http://127.0.0.1:8000` (for hangup requests)
- `VP_PROCESSING_DELAY_ACK_MS` (default 900)
- `VP_USER_SILENCE_REPROMPT_MS` (default 7000)
- `VP_USER_SILENCE_CLOSE_MS` (default 14000)

### Control Plane
- runs from `.env_local` for LiveKit credentials

## Quick checks

### Is port 8000 listening?

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

### Does ngrok reach the server?

```bash
curl -i https://<ngrok>.ngrok-free.dev/health
```

### Did LiveKit send webhooks?

Open the ngrok inspector:

```text
http://127.0.0.1:4040
```

## Telephony call hangup

### Manual hangup via Control Plane

```bash
curl -i http://127.0.0.1:8000/control/call/hangup \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"call-..."}'
```


