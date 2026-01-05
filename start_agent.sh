#!/bin/bash
# Start Voice Pipeline agent voor telefonie (production mode)
# De agent wacht op LiveKit dispatches (inbound/outbound calls)

cd "$(dirname "$0")"

echo "📞 Starting Voice Pipeline agent for telephony..."
echo ""
echo "Agent will wait for:"
echo "  - Inbound SIP calls (via LiveKit dispatch rule)"
echo "  - Outbound calls (via Control Plane API)"
echo ""
echo "Status: Listening for LiveKit dispatches..."
echo ""

python -m voice_pipeline.agent dev

