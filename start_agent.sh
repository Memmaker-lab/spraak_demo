#!/bin/bash
# Start Voice Pipeline agent voor telefonie (production mode)
# De agent wacht op LiveKit dispatches (inbound/outbound calls)

cd "$(dirname "$0")"

# Load environment variables from .env_local or .env.local (if present)
set -a
if [ -f ".env_local" ]; then
  # Use a more reliable method to load .env file, handling quotes correctly
  while IFS= read -r line || [ -n "$line" ]; do
    # Skip comments and empty lines
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line// }" ]] && continue
    # Export variables, handling quoted values
    if [[ "$line" =~ ^[[:space:]]*([^=]+)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]// /}"
      value="${BASH_REMATCH[2]}"
      # Remove quotes if present
      value="${value#\"}"
      value="${value%\"}"
      value="${value#\'}"
      value="${value%\'}"
      export "$key=$value"
    fi
  done < .env_local
elif [ -f ".env.local" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "${line// }" ]] && continue
    if [[ "$line" =~ ^[[:space:]]*([^=]+)=(.*)$ ]]; then
      key="${BASH_REMATCH[1]// /}"
      value="${BASH_REMATCH[2]}"
      value="${value#\"}"
      value="${value%\"}"
      value="${value#\'}"
      value="${value%\'}"
      export "$key=$value"
    fi
  done < .env.local
fi
set +a

# Set scenario (can be overridden by job metadata or .env_local)
# Priority: job metadata flow > AGENT_SCENARIO env var > default
# Only set if not already set in .env_local
if [ -z "$AGENT_SCENARIO" ]; then
  export AGENT_SCENARIO="kraan_defect"
fi

echo "📞 Starting Voice Pipeline agent for telephony..."
echo "   Using scenario: $AGENT_SCENARIO"
echo ""
echo "Agent will wait for:"
echo "  - Inbound SIP calls (via LiveKit dispatch rule)"
echo "  - Outbound calls (via Control Plane API)"
echo ""
echo "Status: Listening for LiveKit dispatches..."
echo ""

# Workaround for multiprocessing spawn issues on macOS with pydantic v2
# This environment variable disables the fork safety check which can cause
# issues when spawning processes
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

python -m voice_pipeline.agent dev

