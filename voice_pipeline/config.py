"""
Voice Pipeline configuration.

Loads provider configuration from environment variables.
"""
import os
from dataclasses import dataclass
from typing import Optional


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
    
    # Azure TTS
    azure_speech_key: str
    azure_speech_region: str
    azure_speech_voice: str
    azure_speech_output_format: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "VoiceConfig":
        """Load configuration from environment variables."""
        return cls(
            livekit_url=os.environ["LIVEKIT_URL"],
            livekit_api_key=os.environ["LIVEKIT_API_KEY"],
            livekit_api_secret=os.environ["LIVEKIT_API_SECRET"],
            groq_api_key=os.environ["GROQ_API_KEY"],
            groq_model_llm=os.environ.get("GROQ_MODEL_LLM", "qwen/qwen3-32b"),
            azure_speech_key=os.environ["AZURE_SPEECH_KEY"],
            azure_speech_region=os.environ["AZURE_SPEECH_REGION"],
            azure_speech_voice=os.environ.get("AZURE_SPEECH_VOICE", "nl-NL-FennaNeural"),
            azure_speech_output_format=os.environ.get("AZURE_SPEECH_OUTPUT_FORMAT"),
        )


def get_config() -> VoiceConfig:
    """Get or create global config instance."""
    global _config
    if _config is None:
        _config = VoiceConfig.from_env()
    return _config


# Global config instance (lazy loaded)
_config: Optional[VoiceConfig] = None

