# TROUBLESHOOTING.md — Common issues

## Webhooks

### ngrok shows 502 Bad Gateway
Almost always means ngrok can’t reach your local server.

Checklist:
- Is Control Plane running on 8000?
  - `curl -i http://127.0.0.1:8000/health`
- Is ngrok forwarding to `http://localhost:8000`?
  - check `http://127.0.0.1:4040`
- Are you hitting an existing route?
  - `GET /health` exists
  - `POST /webhook` exists
  - `GET /` does **not** exist

### “No test events arrive”
First confirm the webhook endpoint itself works:

```bash
curl -i https://<ngrok>.ngrok-free.dev/webhook \
  -X POST -H 'Content-Type: application/json' -H 'Authorization: Bearer test' \
  -d '{}'
```

If that returns `200`, then it’s LiveKit-side configuration:
- webhook URL must be `https://<ngrok>.ngrok-free.dev/webhook`
- URL often changes on ngrok free—update LiveKit setting after restart
- ensure you’re editing the correct LiveKit project
- if some events arrive (e.g. `egress_started`) but others don’t, check webhook event selection / filters

### `/webhook` returns 401
That’s expected when you call it yourself without an `Authorization` header.

## Telephony dispatch / agent not triggered

### Dispatch rule uses agentName, but worker doesn’t start
If SIP dispatch rule contains `roomConfig.agents[].agentName` (example: `"Emp AI"`),
your worker must register with the same name:

```bash
export LIVEKIT_AGENT_NAME="Emp AI"
python -m voice_pipeline.agent dev
```

This mismatch is the most common reason “works in one project but not another”.

### Call arrives but agent doesn’t speak
Checklist:
- worker is running and registered
- STT/LLM/TTS keys valid (Groq/Azure)
- check logs for provider errors

## Control Plane hangup

### Voice pipeline says “Ik hang op” but call stays open
- Ensure Control Plane is running
- Ensure `CONTROL_PLANE_URL` is set for the voice worker:

```bash
export CONTROL_PLANE_URL=http://127.0.0.1:8000
```

The CP ends calls by deleting the LiveKit room.


