# Control API Testing Guide

Test de Control API zonder web UI te bouwen. Meerdere opties beschikbaar.

## CORS Configuration (voor Web Apps)

De API ondersteunt CORS voor cross-origin requests vanuit web apps. Configureer via environment variables:

### Development (alle origins toegestaan)
```bash
# In .env_local of environment
CORS_ALLOW_ALL=true
```

### Production (specifieke origins)
```bash
# In .env_local of environment
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://mijnapp.nl
```

**Defaults:**
- Als `CORS_ALLOW_ALL` niet is ingesteld: alleen `http://localhost:3000` en `http://localhost:5173` zijn toegestaan
- Als `CORS_ALLOW_ALL=true`: alle origins zijn toegestaan (alleen voor development!)

**Voorbeeld voor React/Vue/Next.js app:**
```bash
# .env_local
CORS_ORIGINS=http://localhost:3000,http://localhost:5173,https://mijnapp.nl
```

## Optie 1: FastAPI Swagger UI (Aanbevolen)

FastAPI genereert automatisch interactieve API documentatie:

1. **Start de Control Plane server:**
   ```bash
   python -m control_plane
   ```

2. **Open in browser:**
   - Swagger UI: `http://127.0.0.1:8000/docs`
   - ReDoc: `http://127.0.0.1:8000/redoc`

3. **Test endpoints interactief:**
   - Klik op een endpoint (bijv. `GET /control/sessions`)
   - Klik "Try it out"
   - Vul parameters in (optioneel)
   - Klik "Execute"
   - Zie response + status code

**Voordelen:**
- Geen extra tools nodig
- Zie alle endpoints + parameters
- Direct testbaar vanuit browser
- Zie request/response voorbeelden

## Optie 2: curl Commands

### Health Check
```bash
curl -i http://127.0.0.1:8000/health
```

### List Sessions
```bash
# Alle sessions
curl http://127.0.0.1:8000/control/sessions

# Filter op state
curl "http://127.0.0.1:8000/control/sessions?state=connected"

# Filter op direction
curl "http://127.0.0.1:8000/control/sessions?direction=inbound"

# Combinatie
curl "http://127.0.0.1:8000/control/sessions?state=connected&direction=inbound"
```

### Get Session Details
```bash
# Vervang {session_id} met een echte session_id uit de list
curl http://127.0.0.1:8000/control/sessions/{session_id}
```

### Query Events
```bash
# Alle events voor een session
curl "http://127.0.0.1:8000/control/sessions/{session_id}/events"

# Filter op event_type
curl "http://127.0.0.1:8000/control/sessions/{session_id}/events?event_type=call.started"

# Filter op component
curl "http://127.0.0.1:8000/control/sessions/{session_id}/events?component=voice_pipeline"

# Filter op tijd (sinds timestamp)
curl "http://127.0.0.1:8000/control/sessions/{session_id}/events?since=2026-01-06T10:00:00%2B00:00"

# Limit aantal events
curl "http://127.0.0.1:8000/control/sessions/{session_id}/events?limit=10"

# Combinatie
curl "http://127.0.0.1:8000/control/sessions/{session_id}/events?event_type=stt.final&component=voice_pipeline&limit=5"
```

### Hangup Call (Write API)
```bash
curl -X POST http://127.0.0.1:8000/control/call/hangup \
  -H "Content-Type: application/json" \
  -d '{"session_id": "call-_+31651969697_abc123"}'
```

### Pretty Print JSON (met jq)
```bash
# Installeer jq: brew install jq (macOS) of apt-get install jq (Linux)
curl -s http://127.0.0.1:8000/control/sessions | jq
```

## Optie 3: Python Test Script

Maak een simpel script om de API te testen:

```python
#!/usr/bin/env python3
"""Test Control API endpoints."""
import requests
import json
from datetime import datetime, timezone

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """Test health endpoint."""
    resp = requests.get(f"{BASE_URL}/health")
    print(f"Health: {resp.status_code} - {resp.json()}")
    return resp.status_code == 200

def test_list_sessions():
    """Test list sessions."""
    resp = requests.get(f"{BASE_URL}/control/sessions")
    print(f"\nList Sessions: {resp.status_code}")
    sessions = resp.json()
    print(f"Found {len(sessions)} sessions")
    for s in sessions[:3]:  # Show first 3
        print(f"  - {s['session_id']} ({s['state']}, {s['direction']})")
    return sessions

def test_get_session(session_id: str):
    """Test get session details."""
    resp = requests.get(f"{BASE_URL}/control/sessions/{session_id}")
    print(f"\nGet Session: {resp.status_code}")
    if resp.status_code == 200:
        session = resp.json()
        print(json.dumps(session, indent=2))
    return resp.json() if resp.status_code == 200 else None

def test_get_events(session_id: str):
    """Test query events."""
    resp = requests.get(f"{BASE_URL}/control/sessions/{session_id}/events")
    print(f"\nGet Events: {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        print(f"Found {data['count']} events")
        for event in data['events'][:5]:  # Show first 5
            print(f"  - {event['ts']} [{event['component']}] {event['event_type']}")
    return resp.json() if resp.status_code == 200 else None

def test_hangup(session_id: str):
    """Test hangup call."""
    resp = requests.post(
        f"{BASE_URL}/control/call/hangup",
        json={"session_id": session_id}
    )
    print(f"\nHangup: {resp.status_code} - {resp.json()}")
    return resp.status_code == 200

if __name__ == "__main__":
    print("Testing Control API...")
    
    # Health check
    if not test_health():
        print("Server not running!")
        exit(1)
    
    # List sessions
    sessions = test_list_sessions()
    
    # Get first session details
    if sessions:
        first_session = sessions[0]
        test_get_session(first_session['session_id'])
        test_get_events(first_session['session_id'])
        
        # Uncomment to test hangup:
        # test_hangup(first_session['session_id'])
```

**Gebruik:**
```bash
# Installeer requests: pip install requests
python control_plane/test_api.py
```

## Optie 4: httpie (Gebruiksvriendelijker dan curl)

```bash
# Installeer: brew install httpie (macOS) of pip install httpie

# List sessions
http GET http://127.0.0.1:8000/control/sessions

# Get session
http GET http://127.0.0.1:8000/control/sessions/{session_id}

# Query events
http GET http://127.0.0.1:8000/control/sessions/{session_id}/events event_type==call.started

# Hangup
http POST http://127.0.0.1:8000/control/call/hangup session_id="call-123"
```

## Optie 5: Postman / Insomnia (GUI Tools)

1. **Import OpenAPI spec:**
   - FastAPI exposeert OpenAPI schema op: `http://127.0.0.1:8000/openapi.json`
   - Download deze JSON
   - Import in Postman/Insomnia

2. **Of maak handmatig requests:**
   - Base URL: `http://127.0.0.1:8000`
   - Endpoints:
     - `GET /health`
     - `GET /control/sessions`
     - `GET /control/sessions/{session_id}`
     - `GET /control/sessions/{session_id}/events`
     - `POST /control/call/hangup`

## Workflow voor Testing

### 1. Start Services
```bash
# Terminal 1: Control Plane
python -m control_plane

# Terminal 2: Voice Pipeline (optioneel, voor echte calls)
export LIVEKIT_AGENT_NAME="Emp AI"
./start_agent.sh
```

### 2. Maak een Test Call
Bel je LiveKit telefoonnummer om een echte call te maken, of gebruik de test scripts.

### 3. Query de API
```bash
# Zie alle sessions
curl http://127.0.0.1:8000/control/sessions | jq

# Kies een session_id en query events
curl "http://127.0.0.1:8000/control/sessions/{session_id}/events" | jq

# Filter op voice pipeline events
curl "http://127.0.0.1:8000/control/sessions/{session_id}/events?component=voice_pipeline" | jq

# Zie alleen latency events
curl "http://127.0.0.1:8000/control/sessions/{session_id}/events?event_type=llm.response" | jq '.events[] | select(.latency_ms != null)'
```

## Tips

- **Gebruik `jq` voor pretty printing:** `curl ... | jq`
- **Gebruik Swagger UI voor exploratie:** `http://127.0.0.1:8000/docs`
- **Check logs:** Events worden ook naar stdout gelogd (JSON)
- **Session ID vinden:** Gebruik `GET /control/sessions` om beschikbare sessions te zien
- **Events filteren:** Combineer `event_type`, `component`, `since`, `until`, `limit` voor precieze queries

