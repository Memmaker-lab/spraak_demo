"""
Tests for Voice Pipeline configuration.

Verifies:
- Configuration loading from environment
- Required fields validation
- Default values
"""
import os
import pytest

from voice_pipeline.config import VoiceConfig


def test_config_from_env_all_fields(monkeypatch):
    """Test configuration loading with all fields set."""
    monkeypatch.setenv("LIVEKIT_URL", "wss://test.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test_key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test_secret")
    monkeypatch.setenv("GROQ_API_KEY", "test_groq_key")
    monkeypatch.setenv("GROQ_MODEL_LLM", "qwen/qwen3-32b")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "test_azure_key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    monkeypatch.setenv("AZURE_SPEECH_VOICE", "nl-NL-FennaNeural")
    monkeypatch.setenv("AZURE_SPEECH_OUTPUT_FORMAT", "Raw48Khz16BitMonoPcm")
    
    config = VoiceConfig.from_env()
    
    assert config.livekit_url == "wss://test.livekit.cloud"
    assert config.livekit_api_key == "test_key"
    assert config.livekit_api_secret == "test_secret"
    assert config.groq_api_key == "test_groq_key"
    assert config.groq_model_llm == "qwen/qwen3-32b"
    assert config.azure_speech_key == "test_azure_key"
    assert config.azure_speech_region == "westeurope"
    assert config.azure_speech_voice == "nl-NL-FennaNeural"
    assert config.azure_speech_output_format == "Raw48Khz16BitMonoPcm"


def test_config_from_env_defaults(monkeypatch):
    """Test configuration with default values."""
    # Ensure optional vars are not pre-set in the environment
    monkeypatch.delenv("GROQ_MODEL_LLM", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_VOICE", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_OUTPUT_FORMAT", raising=False)

    monkeypatch.setenv("LIVEKIT_URL", "wss://test.livekit.cloud")
    monkeypatch.setenv("LIVEKIT_API_KEY", "test_key")
    monkeypatch.setenv("LIVEKIT_API_SECRET", "test_secret")
    monkeypatch.setenv("GROQ_API_KEY", "test_groq_key")
    monkeypatch.setenv("AZURE_SPEECH_KEY", "test_azure_key")
    monkeypatch.setenv("AZURE_SPEECH_REGION", "westeurope")
    # Don't set GROQ_MODEL_LLM, AZURE_SPEECH_VOICE, AZURE_SPEECH_OUTPUT_FORMAT
    
    config = VoiceConfig.from_env()
    
    # Check defaults
    assert config.groq_model_llm == "qwen/qwen3-32b"
    assert config.azure_speech_voice == "nl-NL-FennaNeural"
    assert config.azure_speech_output_format is None


def test_config_missing_required_field(monkeypatch):
    """Test that missing required fields raise KeyError."""
    # Ensure the required var is not already present in the environment
    monkeypatch.delenv("LIVEKIT_API_KEY", raising=False)
    monkeypatch.delenv("LIVEKIT_API_SECRET", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)

    monkeypatch.setenv("LIVEKIT_URL", "wss://test.livekit.cloud")
    # Missing LIVEKIT_API_KEY
    
    with pytest.raises(KeyError):
        VoiceConfig.from_env()


def test_config_dataclass_immutable():
    """Test that config is a dataclass with expected fields."""
    config = VoiceConfig(
        livekit_url="wss://test.livekit.cloud",
        livekit_api_key="key",
        livekit_api_secret="secret",
        groq_api_key="groq_key",
        groq_model_llm="model",
        azure_speech_key="azure_key",
        azure_speech_region="region",
        azure_speech_voice="voice",
    )
    
    assert config.livekit_url == "wss://test.livekit.cloud"
    assert config.groq_model_llm == "model"
    assert config.azure_speech_voice == "voice"

