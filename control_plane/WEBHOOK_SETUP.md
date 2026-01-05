# Webhook Setup Guide - Logging met LiveKit Webhooks

Deze gids beschrijft hoe je webhooks configureert om LiveKit events te loggen via de Control Plane.

## Overzicht

LiveKit stuurt webhook events naar je server wanneer:
- Rooms worden gestart/beëindigd
- Participants joinen/verlaten
- Tracks worden gepubliceerd/unpublished
- En meer...

De Control Plane ontvangt deze events en logt ze als gestructureerde JSON events per OBS-00.

## Stap 1: Webhook Server Starten

### Lokaal (Development)

```bash
# Start de webhook server
python -m control_plane

# Of met uvicorn direct
uvicorn control_plane.webhook_server:app --host 0.0.0.0 --port 8000
```

De server draait nu op `http://localhost:8000` met:
- `/webhook` - LiveKit webhook endpoint
- `/health` - Health check

### Productie (Deployment)

Deploy de FastAPI app naar je hosting provider (bijv. Railway, Render, Fly.io, etc.).

**Belangrijk:** De webhook URL moet publiek toegankelijk zijn (HTTPS).

## Stap 2: Publieke URL Maken (Development)

Voor lokale development, gebruik ngrok of vergelijkbaar:

```bash
# Installeer ngrok (als je het nog niet hebt)
# brew install ngrok  # macOS
# of download van https://ngrok.com

# Start ngrok tunnel
ngrok http 8000
```

Dit geeft je een publieke URL zoals: `https://abc123.ngrok.io`

**Note:** Update de webhook URL in LiveKit wanneer ngrok opnieuw start (gratis versie krijgt nieuwe URL).

## Stap 3: Webhook Configureren in LiveKit Cloud

1. **Login** naar [LiveKit Cloud Dashboard](https://cloud.livekit.io)

2. **Selecteer je project**

3. **Ga naar Settings** (project settings, niet account settings)

4. **Zoek naar "Webhooks" sectie** - dit kan zijn:
   - Direct in Settings pagina
   - Onder "Integrations" of "Notifications"
   - Als tab in Settings

5. **Voeg webhook toe:**
   - Klik op "Add Webhook" of "Create Webhook"
   - **URL**: `https://your-ngrok-url.ngrok.io/webhook` (gebruik je ngrok URL)
   - **Events**: Selecteer de volgende events:
     - ✅ `room_started`
     - ✅ `room_finished`
     - ✅ `participant_joined`
     - ✅ `participant_left`
     - ✅ `track_published`
     - ✅ `track_unpublished`
     - ✅ `participant_connection_aborted` (optioneel)

6. **Save** de webhook configuratie

**Note:** Als je "Recent deliveries" niet ziet, kan dit betekenen:
- Webhooks zijn nog niet geconfigureerd
- De interface is anders in jouw LiveKit versie
- Webhook deliveries worden alleen getoond na eerste events

## Stap 4: Webhook Signature Verificatie (TODO)

**Huidige status:** De webhook handler heeft een placeholder voor signature verificatie.

**Voor productie:** Implementeer proper JWT verificatie:

```python
# In webhook_handler.py, vervang verify_webhook() met:
from livekit.protocol import webhook as lk_webhook
from livekit.protocol.auth import SimpleKeyProvider

def verify_webhook(self, body: bytes, auth_header: str) -> bool:
    try:
        auth_provider = SimpleKeyProvider(
            config.livekit_api_key,
            config.livekit_api_secret,
        )
        event = lk_webhook.ReceiveWebhookEvent(
            body, auth_header, auth_provider
        )
        return event is not None
    except Exception:
        return False
```

## Stap 5: Testen

### Test 1: Health Check

```bash
curl http://localhost:8000/health
```

Verwacht: `{"status":"ok","component":"control_plane"}`

### Test 2: Inbound Call Test

1. Bel je LiveKit phone number
2. Check de logs (stdout) voor gestructureerde JSON events:
   ```json
   {"ts":"2026-01-05T13:30:00Z","session_id":"...","component":"control_plane","event_type":"call.started",...}
   {"ts":"2026-01-05T13:30:01Z","session_id":"...","component":"control_plane","event_type":"livekit.room.created",...}
   {"ts":"2026-01-05T13:30:02Z","session_id":"...","component":"control_plane","event_type":"livekit.participant.joined",...}
   ```

### Test 3: Webhook Event Logging

Events worden automatisch gelogd naar stdout in JSON format per OBS-00.

**Check server output:** Wanneer je belt, zou je in de terminal waar de server draait moeten zien:
- `webhook.received` - webhook ontvangen
- `webhook.processing` - webhook wordt verwerkt  
- `call.started` - call gestart
- `livekit.room.created` - room aangemaakt
- `livekit.participant.joined` - participant joined
- etc.

**Voor productie:** Redirect stdout naar een log file of log aggregator:

```bash
python -m control_plane >> /var/log/control_plane.log 2>&1
```

Of gebruik een process manager zoals systemd, supervisor, of PM2.

## Stap 6: Events die worden Gelogd

De Control Plane logt de volgende events per OBS-00:

### Call Lifecycle
- `call.started` - Wanneer een call begint (inbound/outbound)
- `call.answered` - Wanneer call wordt opgenomen
- `call.ended` - Wanneer call eindigt (met reason)

### Session Lifecycle
- `session.state_changed` - State transitions (created → connected → ended)

### LiveKit Events
- `livekit.room.created` - Room wordt aangemaakt
- `livekit.participant.joined` - Participant join room
- `livekit.participant.left` - Participant verlaat room
- `livekit.track.published` - Track wordt gepubliceerd
- `livekit.track.unpublished` - Track wordt unpublished

### Provider Events (bij errors)
- `provider.event` - Provider errors/limits (per CP-04)

## Stap 7: Log Aggregatie (Optioneel)

Voor productie, overweeg:

1. **File-based logging:**
   ```bash
   python -m control_plane >> logs/control_plane_$(date +%Y%m%d).log 2>&1
   ```

2. **JSONL format** (elk event op één regel):
   - Perfect voor log aggregators (Datadog, Logstash, etc.)
   - Elke regel is een valide JSON object

3. **Log rotation:**
   - Gebruik `logrotate` of vergelijkbaar
   - Houd logs voor audit (per privacy requirements)

## Troubleshooting

### Webhooks worden niet ontvangen

1. **Check webhook URL:**
   - Moet publiek toegankelijk zijn (HTTPS)
   - Moet `/webhook` endpoint zijn

2. **Check server logs:**
   ```bash
   # Check of server draait
   curl http://localhost:8000/health
   ```

3. **Check LiveKit dashboard:**
   - Ga naar Settings → Webhooks
   - Check of webhook "Active" is
   - Check "Recent deliveries" voor errors

4. **Test webhook handmatig:**
   ```bash
   # Simuleer webhook event (zonder signature)
   curl -X POST http://localhost:8000/webhook \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer test" \
     -d '{"event":"room_started","room":{"name":"test-room"}}'
   ```

### Events worden niet gelogd

1. **Check stdout:**
   - Events worden naar stdout geschreven
   - Zorg dat stdout niet wordt gebufferd

2. **Check event format:**
   - Elke event moet JSON zijn
   - Check met `jq` voor formatting:
   ```bash
   python -m control_plane | jq .
   ```

## Volgende Stappen

- [ ] Implementeer proper webhook signature verificatie
- [ ] Setup log aggregatie (bijv. Datadog, CloudWatch)
- [ ] Add monitoring/alerts voor webhook failures
- [ ] Setup log retention policy

