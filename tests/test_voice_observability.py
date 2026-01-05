"""
Tests for Voice Pipeline observability.

Verifies:
- Event emission per OBS-00
- Turn lifecycle tracking per VC-01
- Barge-in detection per VC-03
- Session ID correlation
"""
import pytest
from unittest.mock import Mock, MagicMock
from io import StringIO
import json
import sys

from voice_pipeline.observability import VoicePipelineObserver


@pytest.fixture
def capture_events(monkeypatch):
    """Capture emitted events to stdout."""
    buffer = StringIO()
    monkeypatch.setattr(sys, 'stdout', buffer)
    yield buffer
    monkeypatch.setattr(sys, 'stdout', sys.__stdout__)


def test_observer_initialization():
    """Test observer can be initialized with session_id."""
    observer = VoicePipelineObserver(session_id="sess_123")
    
    assert observer.session_id == "sess_123"
    assert observer.current_turn_id is None
    assert observer.tts_playing is False


def test_vad_state_changed_event(capsys):
    """Test VAD state change emits event."""
    observer = VoicePipelineObserver(session_id="sess_123")
    
    event = {"state": "speaking"}
    observer._on_vad_state_changed(event)
    
    # Check event was emitted
    captured = capsys.readouterr()
    assert "vad.state_changed" in captured.out
    assert "sess_123" in captured.out


def test_barge_in_detection(capsys):
    """Test barge-in is detected when user speaks during TTS per VC-03."""
    observer = VoicePipelineObserver(session_id="sess_123")
    observer.tts_playing = True
    observer.current_turn_id = "turn_456"
    
    event = {}
    observer._on_user_started_speaking(event)
    
    # Check barge-in event was emitted
    captured = capsys.readouterr()
    assert "barge_in.detected" in captured.out
    assert "sess_123" in captured.out


def test_no_barge_in_when_tts_not_playing(capsys):
    """Test barge-in is not detected when TTS is not playing."""
    observer = VoicePipelineObserver(session_id="sess_123")
    observer.tts_playing = False
    
    event = {}
    observer._on_user_started_speaking(event)
    
    # Check no barge-in event
    captured = capsys.readouterr()
    assert "barge_in.detected" not in captured.out


def test_turn_started_on_speech_committed(capsys):
    """Test turn.started event is emitted per VC-01."""
    observer = VoicePipelineObserver(session_id="sess_123")
    
    event = {"text": "Hello world"}
    observer._on_user_speech_committed(event)
    
    # Check turn started
    assert observer.current_turn_id is not None
    assert observer.current_turn_id.startswith("turn_")
    
    # Check event was emitted
    captured = capsys.readouterr()
    assert "turn.started" in captured.out
    assert "sess_123" in captured.out


def test_tts_started_event(capsys):
    """Test TTS started event is emitted."""
    observer = VoicePipelineObserver(session_id="sess_123")
    observer.current_turn_id = "turn_789"
    
    event = {}
    observer._on_agent_started_speaking(event)
    
    assert observer.tts_playing is True
    
    # Check event was emitted
    captured = capsys.readouterr()
    assert "tts.started" in captured.out
    assert "sess_123" in captured.out


def test_tts_stopped_event(capsys):
    """Test TTS stopped event is emitted with cause per VC-03."""
    observer = VoicePipelineObserver(session_id="sess_123")
    observer.tts_playing = True
    observer.current_turn_id = "turn_789"
    
    event = {"reason": "barge_in"}
    observer._on_agent_stopped_speaking(event)
    
    assert observer.tts_playing is False
    
    # Check event was emitted with cause
    captured = capsys.readouterr()
    assert "tts.stopped" in captured.out
    assert "barge_in" in captured.out
    assert "sess_123" in captured.out


def test_session_id_correlation():
    """Test that all events include session_id for correlation."""
    observer = VoicePipelineObserver(session_id="sess_abc")
    
    # All events should use the same session_id
    assert observer.session_id == "sess_abc"
    assert observer.emitter is not None


def test_attach_to_session():
    """Test that observer can attach to a mock session."""
    observer = VoicePipelineObserver(session_id="sess_123")
    
    # Create mock session with on() method
    mock_session = Mock()
    mock_session.on = Mock()
    
    observer.attach_to_session(mock_session)
    
    # Verify event listeners were registered
    assert mock_session.on.called
    # Should register multiple event types
    assert mock_session.on.call_count >= 5

