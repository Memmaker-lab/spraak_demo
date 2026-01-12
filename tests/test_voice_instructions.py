"""
Tests for Voice Pipeline instructions and scenarios.
"""
import os
import pytest
from pathlib import Path

from voice_pipeline.instructions import (
    get_instructions,
    get_greeting_text,
    get_greeting_audio_path,
    get_scenario,
    load_scenario,
    AGENT_INSTRUCTIONS,
)


def test_default_scenario_exists():
    """Test that default scenario can be loaded."""
    scenario = load_scenario("default")
    assert scenario["name"] == "default"
    assert "prompt" in scenario
    assert "greeting_text" in scenario
    assert len(scenario["greeting_text"]) > 0


def test_get_scenario_with_default():
    """Test that get_scenario returns default when no flow specified."""
    scenario = get_scenario()
    assert scenario["name"] == "default"
    assert "prompt" in scenario
    assert "greeting_text" in scenario


def test_get_scenario_with_flow():
    """Test that get_scenario uses flow parameter."""
    scenario = get_scenario(flow="domijn")
    assert scenario["name"] == "domijn"
    assert "prompt" in scenario
    assert "greeting_text" in scenario


def test_get_scenario_with_env_var(monkeypatch):
    """Test that get_scenario uses AGENT_SCENARIO env var."""
    monkeypatch.setenv("AGENT_SCENARIO", "domijn")
    scenario = get_scenario()
    assert scenario["name"] == "domijn"


def test_get_instructions_default():
    """Test that get_instructions returns prompt from default scenario."""
    instructions = get_instructions()
    assert len(instructions) > 0
    # Should contain key phrases from default prompt
    assert "Nederlands" in instructions or "nl-NL" in instructions


def test_get_instructions_with_flow():
    """Test that get_instructions uses flow parameter."""
    instructions_default = get_instructions(flow="default")
    instructions_domijn = get_instructions(flow="domijn")
    
    # Should be different prompts
    assert instructions_default != instructions_domijn
    # Both should be non-empty
    assert len(instructions_default) > 0
    assert len(instructions_domijn) > 0


def test_get_instructions_with_custom():
    """Test that custom instructions are appended."""
    custom = "Extra instructie voor test."
    instructions = get_instructions(custom_instructions=custom)
    assert AGENT_INSTRUCTIONS in instructions or "Nederlands" in instructions
    assert custom in instructions


def test_get_greeting_text_default():
    """Test that get_greeting_text returns default greeting."""
    greeting = get_greeting_text()
    assert len(greeting) > 0
    assert isinstance(greeting, str)


def test_get_greeting_text_with_flow():
    """Test that get_greeting_text uses flow parameter."""
    greeting_default = get_greeting_text(flow="default")
    greeting_domijn = get_greeting_text(flow="domijn")
    
    # Should be different greetings
    assert greeting_default != greeting_domijn
    # Both should be non-empty
    assert len(greeting_default) > 0
    assert len(greeting_domijn) > 0


def test_get_greeting_audio_path_none():
    """Test that get_greeting_audio_path returns None when not configured."""
    audio_path = get_greeting_audio_path()
    assert audio_path is None


def test_load_scenario_fallback_to_default():
    """Test that loading non-existent scenario falls back to default."""
    scenario = load_scenario("nonexistent_scenario_12345")
    # Should fall back to default
    assert scenario["name"] == "default"
    assert "prompt" in scenario
    assert "greeting_text" in scenario


def test_luscia_scenario():
    """Test that luscia scenario can be loaded."""
    scenario = load_scenario("luscia")
    assert scenario["name"] == "luscia"
    assert "prompt" in scenario
    assert "greeting_text" in scenario
    assert len(scenario["greeting_text"]) > 0
    # Check that it contains key phrases from luscia prompt
    prompt = scenario["prompt"]
    assert "Luscia" in prompt
    assert "demo" in prompt.lower()
    assert "afspraken" in prompt or "doorverbinden" in prompt


def test_get_scenario_luscia_with_env_var(monkeypatch):
    """Test that get_scenario uses AGENT_SCENARIO env var for luscia."""
    monkeypatch.setenv("AGENT_SCENARIO", "luscia")
    scenario = get_scenario()
    assert scenario["name"] == "luscia"


def test_get_instructions_luscia():
    """Test that get_instructions returns prompt from luscia scenario."""
    instructions = get_instructions(flow="luscia")
    assert len(instructions) > 0
    assert "Luscia" in instructions
    assert "demo" in instructions.lower()


def test_get_greeting_text_luscia():
    """Test that get_greeting_text returns greeting from luscia scenario."""
    greeting = get_greeting_text(flow="luscia")
    assert len(greeting) > 0
    assert "Luscia" in greeting
    assert isinstance(greeting, str)


def test_scenario_structure():
    """Test that scenario JSON and YAML files have correct structure."""
    scenarios_dir = Path(__file__).parent.parent / "voice_pipeline" / "scenarios"
    
    # Test both JSON and YAML files
    for pattern in ("*.json", "*.yaml", "*.yml"):
        for scenario_file in scenarios_dir.glob(pattern):
            scenario = load_scenario(scenario_file.stem)
            # Required fields
            assert "name" in scenario
            assert "prompt" in scenario
            assert "greeting_text" in scenario
            # Optional fields
            if "greeting_audio" in scenario:
                assert scenario["greeting_audio"] is None or isinstance(scenario["greeting_audio"], str)
