# Voice Pipeline Testing

## Lokaal Testen (Console Mode)

Test de Voice Pipeline agent lokaal met je Mac's microfoon en speakers.

### Quick Start

```bash
./test_voice.sh
```

Dit start de agent in console mode en je kunt direct praten!

### Wat gebeurt er?

1. **Agent start** met je MacBook microfoon en speakers
2. **Praat Nederlands** - de agent luistert
3. **Agent reageert** - via je Mac speakers
4. **Barge-in werkt** - onderbreek de agent tijdens het spreken

### Verwachte Flow

```
JOU: "Hoi, hoe gaat het?"
  → [Agent denkt...]
  → Agent: "Hallo! Het gaat goed met mij, bedankt voor het vragen. 
             Waarmee kan ik je helpen?"

JOU: "Vertel een grap"
  → [Agent denkt...]
  → Agent: "Natuurlijk! Waarom ging de tomaat naar de sportschool?
             Om ketchup te doen!"
```

### Logs Uitschakelen (Stiller)

Als je alleen de conversatie wilt horen zonder logs:

```bash
python -m voice_pipeline.agent console \
  --input-device "MacBook Air microfoon" \
  --output-device "MacBook Air luidsprekers" \
  2>&1 | grep -E "(user_transcript|agent response)"
```

### Audio Devices Kiezen

Lijst beschikbare devices:

```bash
python -m voice_pipeline.agent console --list-devices
```

Specifieke devices kiezen:

```bash
python -m voice_pipeline.agent console \
  --input-device "Jouw Microfoon" \
  --output-device "Jouw Speakers"
```

### Manuele Start (Lang)

```bash
cd /Users/jeroennijenhuis/playgrounds/spraak_demo
python -m voice_pipeline.agent console \
  --input-device "MacBook Air microfoon" \
  --output-device "MacBook Air luidsprekers"
```

## Production Testing (LiveKit)

Voor productie testing met echte telefoon calls:

### 1. Start de agent worker

```bash
python -m voice_pipeline.agent dev
```

De agent wacht nu op dispatch van LiveKit.

### 2. Configureer LiveKit Dispatch

**LiveKit Cloud → Agents → Dispatch Rules**
- Trigger: On inbound call
- Action: Dispatch agent

### 3. Bel je LiveKit nummer

Bel naar: **+31 97 010 206472**

De agent:
- Neemt op binnen 2-3 seconden
- Zegt: "Hallo, waarmee kan ik je helpen?"
- Luistert naar je Nederlandse spraak
- Reageert via LLM
- Ondersteunt barge-in
- Voert silence handling uit (VC-02): “Momentje…” bij lange verwerking, en reprompt/close bij user-silence

## Control Plane hangup (aanrader voor echte telefoon calls)

Bij echte SIP calls wil je bij “ik hang op” ook echt de call beëindigen voor **alle deelnemers**.
Daarvoor gebruikt de Control Plane de LiveKit `delete_room` API.

### Start Control Plane

```bash
python -m control_plane
```

### Zet Control Plane URL voor de Voice Pipeline

```bash
export CONTROL_PLANE_URL=http://127.0.0.1:8000
```

Nu zal de Voice Pipeline bij de VC-02 close path een request doen naar:

```text
POST /control/call/hangup  { "session_id": "call-..." }
```

## Silence handling (VC-02) tunen

Je kunt de timers aanpassen via environment variables (milliseconden):

```bash
VP_PROCESSING_DELAY_ACK_MS=900
VP_USER_SILENCE_REPROMPT_MS=7000
VP_USER_SILENCE_CLOSE_MS=14000
```

## Troubleshooting

### "No module named livekit"

```bash
pip install -r requirements.txt
```

### "LIVEKIT_URL not found"

De `.env_local` wordt automatisch geladen. Check dat het bestand bestaat:

```bash
ls -la .env_local
```

### Microfoon werkt niet

Check audio permissions:
- System Settings → Privacy & Security → Microphone
- Zorg dat Terminal/Python toegang heeft

### Agent hoort me niet

1. Check volume van je microfoon
2. Test met:
   ```bash
   python -m voice_pipeline.agent console --list-devices
   ```
3. Kies juiste input device

### Agent spreekt niet

1. Check volume van je speakers
2. Kies juiste output device
3. Test Azure TTS key in `.env_local`

## Observability

Alle events worden gelogd als JSON. Belangrijke events:

```json
{"event_type": "turn.started", "session_id": "..."}
{"event_type": "stt.final", "session_id": "..."}
{"event_type": "llm.request", "session_id": "..."}
{"event_type": "llm.response", "session_id": "..."}
{"event_type": "tts.started", "session_id": "..."}
{"event_type": "barge_in.detected", "session_id": "..."}
{"event_type": "ux.delay_acknowledged", "session_id": "..."}
{"event_type": "call.ended", "session_id": "..."}
```

Filter logs voor alleen transcripts:

```bash
./test_voice.sh 2>&1 | grep "user_transcript"
```

## Customization

### Andere stem gebruiken

Edit `.env_local`:

```bash
AZURE_SPEECH_VOICE=nl-NL-ColetteNeural  # Vrouwelijke stem 2
AZURE_SPEECH_VOICE=nl-NL-MaartenNeural  # Mannelijke stem
```

Beschikbare stemmen: https://learn.microsoft.com/azure/cognitive-services/speech-service/language-support

### Andere instructies

Edit `voice_pipeline/instructions.py`:

```python
AGENT_INSTRUCTIONS = """
Je bent een vriendelijke doktersassistent...
"""
```

### Ander LLM model

Edit `.env_local`:

```bash
GROQ_MODEL_LLM=llama-3.3-70b-versatile  # Groter model
```

Beschikbare models: https://console.groq.com/docs/models

## Next Steps

- [x] Lokaal testen werkt
- [ ] Productie deployment
- [ ] Function tools voor actions
- [ ] EOU mode voor betere turn-taking

