#!/bin/bash
# Start the Voice Pipeline agent with environment variables from .env_local

# Load environment variables (skip comments and empty lines)
set -a
if [ -f ".env_local" ]; then
  source <(grep -v '^#' .env_local | grep -v '^$' | grep '=' )
elif [ -f ".env.local" ]; then
  source <(grep -v '^#' .env.local | grep -v '^$' | grep '=' )
fi
set +a

# Start the agent in dev mode
python -m voice_pipeline.agent dev

