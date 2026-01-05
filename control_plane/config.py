"""
Configuration management for Control Plane.
Loads from environment variables with sensible defaults.
"""
import os
from typing import Optional
from pathlib import Path


class Config:
    """Control Plane configuration."""
    
    # LiveKit configuration
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    
    # Telephony configuration
    caller_id: str
    
    # Webhook configuration (for receiving LiveKit events)
    webhook_secret: Optional[str] = None  # Same as API secret typically
    
    def __init__(self):
        """Load configuration from environment variables."""
        # Try .env_local first, then regular env
        env_file = Path(__file__).parent.parent / ".env_local"
        if env_file.exists():
            # Simple env file parser (no external deps)
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        # Remove quotes if present
                        value = value.strip().strip('"').strip("'")
                        os.environ[key.strip()] = value
        
        # LiveKit credentials
        self.livekit_url = os.getenv("LIVEKIT_URL", "")
        self.livekit_api_key = os.getenv("LIVEKIT_API_KEY", "")
        self.livekit_api_secret = os.getenv("LIVEKIT_API_SECRET", "")
        
        # Telephony
        self.caller_id = os.getenv("CALLER_ID", "+3197010206472")
        
        # Webhook secret (use API secret if not specified)
        self.webhook_secret = os.getenv("WEBHOOK_SECRET") or self.livekit_api_secret
        
        # Validate required fields
        if not self.livekit_url:
            raise ValueError("LIVEKIT_URL is required")
        if not self.livekit_api_key:
            raise ValueError("LIVEKIT_API_KEY is required")
        if not self.livekit_api_secret:
            raise ValueError("LIVEKIT_API_SECRET is required")


# Global config instance
config = Config()

