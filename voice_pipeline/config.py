"""
Voice Pipeline configuration.

Loads provider configuration from environment variables.
"""
import os
from dataclasses import dataclass
from typing import Optional


def _parse_int_env(key: str, default: int) -> int:
    """
    Parse integer environment variable, stripping comments and whitespace.
    
    Handles cases like:
    - "300  # comment" -> 300
    - "300" -> 300
    - None -> default
    """
    value = os.environ.get(key)
    if not value:
        return default
    
    # Strip comments (everything after #)
    if "#" in value:
        value = value.split("#")[0]
    
    # Strip whitespace
    value = value.strip()
    
    if not value:
        return default
    
    try:
        return int(value)
    except ValueError:
        return default


@dataclass
class VoiceConfig:
    """Voice pipeline configuration."""
    
    # LiveKit
    livekit_url: str
    livekit_api_key: str
    livekit_api_secret: str
    
    # Groq (STT + LLM)
    groq_api_key: str
    groq_model_llm: str
    
    # TTS provider selection
    tts_provider: str  # "azure" | "google" | others in future

    # Azure TTS
    azure_speech_key: str
    azure_speech_region: str
    azure_speech_voice: str
    azure_speech_output_format: Optional[str] = None

    # Google Cloud TTS (REST API with API key authentication)
    # Uses custom implementation in google_cloud_tts.py
    google_tts_api_key: Optional[str] = None
    google_tts_voice: str = "nl-NL-Chirp3-HD-Algenib"  # Supports Gemini voices via REST API
    google_tts_gender: str = "male"  # Not used by REST API, kept for compatibility
    
    # Call duration limits
    max_call_duration_seconds: int = 300  # Maximum call duration in seconds (default: 5 minutes)
    
    @classmethod
    def from_env(cls) -> "VoiceConfig":
        """Load configuration from environment variables."""
        return cls(
            livekit_url=os.environ["LIVEKIT_URL"],
            livekit_api_key=os.environ["LIVEKIT_API_KEY"],
            livekit_api_secret=os.environ["LIVEKIT_API_SECRET"],
            groq_api_key=os.environ["GROQ_API_KEY"],
            groq_model_llm=os.environ.get("GROQ_MODEL_LLM", "qwen/qwen3-32b"),
            tts_provider=os.environ.get("TTS_PROVIDER", "azure").lower(),
            azure_speech_key=os.environ["AZURE_SPEECH_KEY"],
            azure_speech_region=os.environ["AZURE_SPEECH_REGION"],
            azure_speech_voice=os.environ.get("AZURE_SPEECH_VOICE", "nl-NL-FennaNeural"),
            azure_speech_output_format=os.environ.get("AZURE_SPEECH_OUTPUT_FORMAT"),
            google_tts_api_key=os.environ.get("GOOGLE_TTS_API_KEY") or os.environ.get("GOOGLE_API_KEY"),
            google_tts_voice=os.environ.get("GOOGLE_TTS_VOICE", "nl-NL-Chirp3-HD-Algenib"),
            google_tts_gender=os.environ.get("GOOGLE_TTS_GENDER", "male"),
            max_call_duration_seconds=_parse_int_env("MAX_CALL_DURATION_SECONDS", default=60),
        )


def get_config() -> VoiceConfig:
    """Get or create global config instance."""
    global _config
    if _config is None:
        _config = VoiceConfig.from_env()
    return _config


# Global config instance (lazy loaded)
_config: Optional[VoiceConfig] = None

