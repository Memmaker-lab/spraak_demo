#!/bin/bash
# Test Voice Pipeline agent via console (MacBook mic + speakers)

echo "🎙️  Starting Voice Pipeline Agent in Console Mode"
echo "=================================================="
echo ""
echo "Using:"
echo "  Input:  MacBook Air microfoon (device 3)"
echo "  Output: MacBook Air luidsprekers (device 4)"
echo ""
echo "The agent will greet you in Dutch."
echo "Speak in Dutch to test the conversation!"
echo ""
echo "Press Ctrl+C to stop."
echo ""

cd "$(dirname "$0")"
python -m voice_pipeline.agent console --input-device 3 --output-device 4

