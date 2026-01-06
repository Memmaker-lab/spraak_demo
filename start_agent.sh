#!/bin/bash
# Start Voice Pipeline agent voor telefonie (production mode)
# De agent wacht op LiveKit dispatches (inbound/outbound calls)

cd "$(dirname "$0")"

# Load environment variables from .env_local or .env.local (if present)
set -a
if [ -f ".env_local" ]; then
  source <(grep -v '^#' .env_local | grep -v '^$' | grep '=')
elif [ -f ".env.local" ]; then
  source <(grep -v '^#' .env.local | grep -v '^$' | grep '=')
fi
set +a

echo "📞 Starting Voice Pipeline agent for telephony..."
echo ""
echo "Agent will wait for:"
echo "  - Inbound SIP calls (via LiveKit dispatch rule)"
echo "  - Outbound calls (via Control Plane API)"
echo ""
echo "Status: Listening for LiveKit dispatches..."
echo ""

python -m voice_pipeline.agent dev

