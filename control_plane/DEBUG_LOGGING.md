# Debug: Geen Logging Zien

## Checklist

### 1. Is de webhook server gestart?

```bash
# Start de server
python -m control_plane

# Of
uvicorn control_plane.webhook_server:app --host 0.0.0.0 --port 8000
```

**Check:** Zie je "Uvicorn running on http://0.0.0.0:8000"?

### 2. Is de server bereikbaar?

```bash
# Test health endpoint
curl http://localhost:8000/health
```

**Verwacht:** `{"status":"ok","component":"control_plane"}`

### 3. Is webhook geconfigureerd in LiveKit?

1. Ga naar [LiveKit Cloud Dashboard](https://cloud.livekit.io)
2. Settings → Webhooks
3. Check of webhook bestaat en **Active** is
4. Check **Recent deliveries** - zie je events?

### 4. Is webhook URL publiek toegankelijk?

**Voor development:**
- Gebruik ngrok: `ngrok http 8000`
- Kopieer de HTTPS URL (bijv. `https://abc123.ngrok.io`)
- Zet deze URL in LiveKit webhook configuratie

**Check:** 
```bash
# Test of ngrok werkt
curl https://your-ngrok-url.ngrok.io/health
```

### 5. Zie je debug events?

Met de nieuwe debug logging zie je nu:
- `webhook.received` - wanneer webhook binnenkomt
- `webhook.processing` - wanneer webhook wordt verwerkt
- `webhook.processed` - wanneer webhook succesvol is verwerkt
- `webhook.error` - bij errors

**Check stdout** van je webhook server - zie je deze events?

### 6. Test handmatig

```bash
# Simuleer webhook event
curl -X POST http://localhost:8000/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test" \
  -d '{
    "event": "room_started",
    "id": "test-123",
    "createdAt": 1704456000,
    "room": {
      "name": "test-room",
      "sid": "RM_test"
    }
  }'
```

**Check:** Zie je JSON events in stdout?

### 7. Check LiveKit webhook configuratie

In LiveKit Cloud Dashboard:
- Settings → Webhooks
- Check of webhook bestaat en **Active/Enabled** is
- Check of de URL correct is (moet eindigen op `/webhook`)
- Als er een "Recent deliveries" of "Delivery history" sectie is, check daar
- **Note:** Delivery history is niet altijd zichtbaar - focus op of webhook bestaat en enabled is

### 8. Check server logs voor errors

Als de server draait, check de terminal output voor:
- `webhook.error` events
- Python exceptions/tracebacks
- Connection errors

## Veelvoorkomende Problemen

### Probleem: Geen events in stdout

**Oplossing:**
- Check of server draait
- Check of webhook URL correct is in LiveKit
- Check of webhook "Active" is in LiveKit dashboard

### Probleem: webhook.error events

**Oplossing:**
- Check webhook signature verification (momenteel placeholder)
- Check of Authorization header aanwezig is
- Check webhook payload format

### Probleem: Events worden niet verwerkt

**Oplossing:**
- Check event type in webhook handler
- Check of `_handle_room_started` etc. worden aangeroepen
- Check session creation logic

## Debug Mode

Start de server met extra logging:

```bash
# Met Python logging
PYTHONUNBUFFERED=1 python -m control_plane

# Of redirect naar file
python -m control_plane 2>&1 | tee webhook.log
```

## Volgende Stappen

Als je nog steeds geen logging ziet:

1. **Check of webhooks worden ontvangen:**
   - Kijk in LiveKit dashboard → Recent deliveries
   - Zie je events daar?

2. **Check server output:**
   - Start server in terminal
   - Bel je nummer
   - Zie je ANY output?

3. **Test met curl:**
   - Gebruik de handmatige test hierboven
   - Werkt die?

4. **Check webhook URL:**
   - Is het de juiste URL?
   - Is het HTTPS (vereist voor LiveKit)?
   - Is het publiek toegankelijk?

