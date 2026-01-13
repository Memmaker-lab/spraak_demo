#!/bin/bash
# Test Voice Pipeline agent in console mode met MacBook microfoon & headphone

cd "$(dirname "$0")"

echo "🎤 Starting Voice Pipeline in console mode..."
echo ""
echo "Tips:"
echo "  - Praat Nederlands tegen je Mac"
echo "  - De agent reageert via je headphone (1MORE HQ51)"
echo "  - Druk Ctrl+C om te stoppen"
echo ""
echo "Listening..."
echo ""

python -m voice_pipeline.agent console \
  --input-device "MacBook Air microfoon" \
  #--output-device "MacBook Air luidsprekers" \
  --output-device "1MORE HQ51"

