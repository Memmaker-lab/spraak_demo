# Scenario Configurations

This directory contains scenario configurations for different use cases. Each scenario defines:
- **prompt**: System instructions for the LLM
- **greeting_text**: Fixed opening phrase (currently spoken via TTS)
- **greeting_audio**: Optional path to WAV file (for future use)
- **name**: Scenario identifier

## Available Scenarios

- **default**: Generic Dutch phone assistant
- **domijn**: Woningcooperatie Domijn assistant (Luscia)
- **luscia**: Demo scenario for Luscia telephonic AI assistant (general info, appointments, orders, transfers)
- **customer_service**: Customer service representative
- **sales**: Sales representative

## Usage

### Via LiveKit Job Metadata (Production)

Set the `flow` parameter in job metadata:

```json
{
  "flow": "domijn",
  "session_id": "call-123"
}
```

### Via Environment Variable (Local Testing)

```bash
export AGENT_SCENARIO=domijn
./start_agent.sh
```

### Creating New Scenarios

1. Create a new JSON or YAML file: `scenarios/my_scenario.json` or `scenarios/my_scenario.yaml`
2. Follow the structure:

**JSON format:**
```json
{
  "name": "my_scenario",
  "prompt": "Your system prompt here...",
  "greeting_text": "Your fixed greeting here",
  "greeting_audio": null
}
```

**YAML format:**
```yaml
name: my_scenario

prompt: |
  Your system prompt here...
  Can span multiple lines...

greeting_text: "Your fixed greeting here"
greeting_audio: null
```

3. No code changes needed - the system will automatically load it

## Future: WAV Audio Support

To use pre-recorded WAV files instead of TTS:

1. Place WAV file in `voice_pipeline/greetings/`
2. Update scenario JSON:
```json
{
  "greeting_audio": "greetings/my_scenario.wav"
}
```

The system will automatically use the WAV file when available (implementation pending).

