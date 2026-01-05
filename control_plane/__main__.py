"""
Entry point for running the Control Plane webhook server.

Usage:
    python -m control_plane

This starts the FastAPI webhook server on http://0.0.0.0:8000
"""
import uvicorn
from logging_setup import setup_logging

if __name__ == "__main__":
    # Initialize logging
    setup_logging(level="INFO", use_json=True)
    
    # Run the webhook server
    uvicorn.run(
        "control_plane.webhook_server:app",
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
