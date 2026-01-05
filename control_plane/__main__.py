"""
Entry point for Control Plane webhook server.
Run with: python -m control_plane
"""
from .webhook_server import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

