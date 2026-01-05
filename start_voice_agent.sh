#!/bin/bash
# Start the Voice Pipeline agent with environment variables from .env_local

# Load environment variables (skip comments and empty lines)
set -a
source <(grep -v '^#' .env_local | grep -v '^$' | grep '=' )
set +a

# Start the agent in dev mode
python -m voice_pipeline.agent dev

