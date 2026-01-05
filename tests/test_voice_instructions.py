"""
Tests for Voice Pipeline instructions.

Verifies:
- Default instructions conform to VC-00
- Custom instructions can be appended
- Instructions are in Dutch
"""
import pytest

from voice_pipeline.instructions import get_instructions, AGENT_INSTRUCTIONS


def test_default_instructions_not_empty():
    """Test that default instructions exist."""
    instructions = get_instructions()
    assert len(instructions) > 0
    assert instructions == AGENT_INSTRUCTIONS


def test_instructions_in_dutch():
    """Test that instructions contain Dutch language indicators."""
    instructions = get_instructions()
    
    # Check for Dutch keywords per VC-00
    assert "Nederlands" in instructions or "nl-NL" in instructions
    assert "kort" in instructions or "duidelijk" in instructions
    # Should not identify as AI/bot
    assert "AI" not in instructions or "niet als een AI" in instructions


def test_instructions_emphasize_brevity():
    """Test that instructions emphasize short responses per VC-00."""
    instructions = get_instructions()
    
    # Should mention keeping responses short
    assert "kort" in instructions.lower() or "2-3 zinnen" in instructions


def test_instructions_human_tone():
    """Test that instructions emphasize human, natural tone per VC-00."""
    instructions = get_instructions()
    
    # Should mention human/natural conversation
    assert "mens" in instructions.lower() or "natuurlijk" in instructions.lower()


def test_custom_instructions_appended():
    """Test that custom instructions are appended."""
    custom = "Je bent een doktersassistent."
    instructions = get_instructions(custom_instructions=custom)
    
    assert AGENT_INSTRUCTIONS in instructions
    assert custom in instructions
    assert instructions.index(AGENT_INSTRUCTIONS) < instructions.index(custom)


def test_custom_instructions_none():
    """Test that None custom instructions work."""
    instructions = get_instructions(custom_instructions=None)
    assert instructions == AGENT_INSTRUCTIONS


def test_instructions_delay_acknowledgement():
    """Test that instructions mention delay acknowledgement per VC-02."""
    instructions = get_instructions()
    
    # Should mention acknowledging delays
    assert "Momentje" in instructions or "duurt" in instructions.lower()

