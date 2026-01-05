#!/bin/bash
# Start ngrok tunnel voor webhook server
# Gebruik: ./start_ngrok.sh

echo "Starting ngrok tunnel on port 8000..."
ngrok http 8000

