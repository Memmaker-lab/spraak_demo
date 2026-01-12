"""
Agent instructions and greetings for telephone-native Dutch conversation.

Supports scenario-based configuration:
- Different system prompts per scenario
- Fixed greeting text per scenario (currently via TTS, later WAV support)
- Scenario selection via flow parameter (from job metadata) or AGENT_SCENARIO env var

Per VC-00:
- Dutch (nl-NL) language
- Concise, calm, human tone
- No AI/bot self-identification
- Short responses (≤ 2-3 sentences)

Implementation note:
- Scenarios are stored as YAML (preferred) or JSON.
- We use PyYAML's safe_load, which can parse both YAML and pure JSON.
"""

import json
import os
from pathlib import Path
from typing import Optional, Dict, Any

import yaml


# Legacy constant for backward compatibility
AGENT_INSTRUCTIONS = """
Je bent een vriendelijke en behulpzame telefoonassistent.

Belangrijk:
- Spreek Nederlands (nl-NL)
- Wees kort en duidelijk (maximaal 2-3 zinnen per keer)
- Blijf kalm en professioneel
- Praat als een mens, niet als een AI of bot
- Gebruik eenvoudige, natuurlijke taal zoals in een telefoongesprek

Als iets onduidelijk is, vraag dan om verduidelijking.
Als je iets niet weet, zeg dat eerlijk.
Als verwerking langer duurt, laat dat dan weten met "Momentje" of "Ik denk even mee."

Wees behulpzaam en vriendelijk, maar blijf zakelijk en to-the-point.
""".strip()


def _get_scenarios_dir() -> Path:
    """Get the scenarios directory path."""
    return Path(__file__).parent / "scenarios"


def _load_file(path: Path) -> Dict[str, Any]:
    """
    Load a scenario file using YAML safe_load.

    PyYAML's safe_load can parse both YAML and pure JSON, so we don't need
    separate code paths. This keeps scenarios human-readable (YAML) while
    still supporting existing JSON files.
    """
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Scenario file {path} must contain a mapping at top-level")
        return data


def load_scenario(scenario_name: str) -> Dict[str, Any]:
    """
    Load scenario configuration from YAML or JSON file.
    
    Resolution order:
    1) <name>.yaml
    2) <name>.yml
    3) <name>.json
    4) default.yaml / default.yml / default.json
    5) hardcoded default fallback
    """
    scenarios_dir = _get_scenarios_dir()

    # 1. Try specific scenario in YAML / YML / JSON order
    candidates = [
        scenarios_dir / f"{scenario_name}.yaml",
        scenarios_dir / f"{scenario_name}.yml",
        scenarios_dir / f"{scenario_name}.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return _load_file(candidate)

    # 2. Fallback to default scenario
    default_candidates = [
        scenarios_dir / "default.yaml",
        scenarios_dir / "default.yml",
        scenarios_dir / "default.json",
    ]
    for candidate in default_candidates:
        if candidate.exists():
            return _load_file(candidate)

    # 3. Last resort: return hardcoded default
    return {
        "name": "default",
        "prompt": AGENT_INSTRUCTIONS,
        "greeting_text": "Hallo, waarmee kan ik je helpen?",
        "greeting_audio": None,
    }


def get_scenario(flow: Optional[str] = None) -> Dict[str, Any]:
    """
    Get scenario configuration based on flow parameter or environment variable.
    
    Priority:
    1. flow parameter (from job metadata)
    2. AGENT_SCENARIO environment variable
    3. "default"
    
    Args:
        flow: Flow/scenario name from job metadata (e.g., "domijn", "customer_service")
        
    Returns:
        Dictionary with scenario configuration
    """
    scenario_name = flow or os.getenv("AGENT_SCENARIO", "default")
    return load_scenario(scenario_name)


def get_instructions(flow: Optional[str] = None, custom_instructions: Optional[str] = None) -> str:
    """
    Get agent instructions (system prompt) for the given scenario.
    
    Args:
        flow: Flow/scenario name from job metadata
        custom_instructions: Optional custom instructions to append
        
    Returns:
        Complete instruction string
    """
    scenario = get_scenario(flow)
    prompt = scenario.get("prompt", AGENT_INSTRUCTIONS).strip()
    
    if custom_instructions:
        return f"{prompt}\n\n{custom_instructions}"
    return prompt


def get_greeting_text(flow: Optional[str] = None) -> str:
    """
    Get greeting text for the given scenario.
    
    This is a fixed opening phrase that will be spoken via TTS.
    In the future, this can be replaced by a WAV file (see get_greeting_audio_path).
    
    Args:
        flow: Flow/scenario name from job metadata
        
    Returns:
        Greeting text string
    """
    scenario = get_scenario(flow)
    return scenario.get("greeting_text", "Hallo, waarmee kan ik je helpen?")


def get_greeting_audio_path(flow: Optional[str] = None) -> Optional[Path]:
    """
    Get greeting audio file path (for future WAV playback support).
    
    Currently returns None if no audio file is configured.
    In the future, this can be used to play pre-recorded WAV files instead of TTS.
    
    Args:
        flow: Flow/scenario name from job metadata
        
    Returns:
        Path to WAV file if configured, None otherwise
    """
    scenario = get_scenario(flow)
    audio_rel = scenario.get("greeting_audio")
    
    if not audio_rel:
        return None
    
    # Resolve relative to voice_pipeline directory
    audio_path = Path(__file__).parent / audio_rel
    if audio_path.exists() and audio_path.is_file():
        return audio_path
    
    return None
