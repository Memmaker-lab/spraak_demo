"""
Tests for Voice Pipeline observability.

Verifies:
- Event emission per OBS-00
- Turn lifecycle tracking per VC-01
- Barge-in detection per VC-03
- Session ID correlation
"""
import asyncio
import pytest
from unittest.mock import Mock

from voice_pipeline.observability import SilenceConfig, VoicePipelineObserver
import voice_pipeline.observability as vp_obs


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
    out = captured.out
    assert "turn.started" in out
    assert "llm.request" in out
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
    out = captured.out
    assert "llm.response" in out
    assert "tts.started" in out
    assert "sess_123" in captured.out


def test_tts_stopped_event(capsys):
    """Test TTS stopped event is emitted with cause per VC-03."""
    observer = VoicePipelineObserver(session_id="sess_123")
    observer.tts_playing = True
    observer.current_turn_id = "turn_789"

    # simulate barge-in timing
    observer._on_user_started_speaking({})
    event = {"reason": "barge_in"}
    observer._on_agent_stopped_speaking(event)
    
    assert observer.tts_playing is False
    
    # Check event was emitted with cause
    captured = capsys.readouterr()
    out = captured.out
    assert "tts.stopped" in out
    assert "barge_in" in out
    assert "time_to_tts_stop_ms" in out
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


def test_user_input_transcribed_emits_stt_final_with_length_from_dict(capsys):
    """OBS-00: stt.final should carry transcript_length and language (no content)."""
    obs = VoicePipelineObserver(session_id="sess_123")
    obs._on_user_input_transcribed({"user_transcript": " Goedemorgen.", "language": "nl"})

    out = capsys.readouterr().out
    assert "stt.final" in out
    assert '"language": "nl"' in out
    # we strip leading whitespace before counting
    assert '"transcript_length": 12' in out


def test_user_input_transcribed_emits_stt_final_with_length_from_args(capsys):
    """LiveKit may call callbacks with positional args (text, language, ...)."""
    obs = VoicePipelineObserver(session_id="sess_123")
    obs._on_user_input_transcribed(None, " Hallo.", "nl")

    out = capsys.readouterr().out
    assert "stt.final" in out
    assert '"language": "nl"' in out
    assert '"transcript_length": 6' in out


@pytest.mark.asyncio
async def test_processing_delay_ack_emits_event_and_speaks(capsys):
    """VC-02: processing delay acknowledgement after threshold."""
    spoken: list[str] = []

    class FakeSession:
        def on(self, *_args, **_kwargs):
            return None

        async def say(self, text: str, **_kwargs):
            spoken.append(text)

        async def aclose(self):
            return None

    async def immediate_sleep(_sec: float):
        return None

    obs = VoicePipelineObserver(
        session_id="sess_123",
        sleep=immediate_sleep,
        silence_cfg=SilenceConfig(
            processing_delay_ack_ms=0,
            user_silence_reprompt_ms=999999,
            user_silence_close_ms=999999,
        ),
    )
    obs.attach_to_session(FakeSession())
    obs._new_turn()
    obs._start_processing_timer()

    # allow the created task to run
    await asyncio.sleep(0)

    out = capsys.readouterr().out
    assert "silence.timer_fired" in out
    assert "ux.delay_acknowledged" in out
    assert spoken and "Momentje" in spoken[0]


@pytest.mark.asyncio
async def test_user_silence_reprompt_then_close_emits_call_ended(capsys, monkeypatch):
    """VC-02: bounded reprompt + graceful close path emits call.ended."""
    spoken: list[str] = []
    closed: list[bool] = []

    class FakeSession:
        def on(self, *_args, **_kwargs):
            return None

        async def say(self, text: str, **_kwargs):
            spoken.append(text)

        async def aclose(self):
            closed.append(True)

    async def immediate_sleep(_sec: float):
        return None

    async def hangup_false(_session_id: str) -> bool:
        return False

    monkeypatch.setattr(vp_obs, "request_hangup", hangup_false)

    obs = VoicePipelineObserver(
        session_id="sess_123",
        sleep=immediate_sleep,
        silence_cfg=SilenceConfig(
            processing_delay_ack_ms=999999,
            user_silence_reprompt_ms=0,
            user_silence_close_ms=1,
        ),
    )
    obs.attach_to_session(FakeSession())

    obs._start_user_silence_timer()
    await asyncio.sleep(0)

    out = capsys.readouterr().out
    assert "call.ended" in out
    assert "user_silence_timeout" in out
    assert any("Ben je er nog" in s for s in spoken)
    assert any("Ik hang op" in s for s in spoken)
    assert closed


@pytest.mark.asyncio
async def test_user_activity_cancels_user_silence_timer(capsys):
    """If user speaks/transcribes, user-silence timer should not reprompt/close."""
    spoken: list[str] = []

    class FakeSession:
        def on(self, *_args, **_kwargs):
            return None

        async def say(self, text: str, **_kwargs):
            spoken.append(text)

        async def aclose(self):
            return None

    async def yield_sleep(_sec: float):
        await asyncio.sleep(0)

    obs = VoicePipelineObserver(
        session_id="sess_123",
        sleep=yield_sleep,
        silence_cfg=SilenceConfig(
            processing_delay_ack_ms=999999,
            user_silence_reprompt_ms=0,
            user_silence_close_ms=1,
        ),
    )
    obs.attach_to_session(FakeSession())
    obs._start_user_silence_timer()

    # Signal user activity immediately (transcript event)
    obs._on_user_input_transcribed({"user_transcript": "Hoi", "language": "nl"})

    # allow tasks to run
    await asyncio.sleep(0)
    out = capsys.readouterr().out
    assert "call.ended" not in out
    assert not any("Ben je er nog" in s for s in spoken)
    assert not any("Ik hang op" in s for s in spoken)


@pytest.mark.asyncio
async def test_close_without_reprompt_when_close_leq_reprompt(capsys, monkeypatch):
    """If CLOSE_MS <= REPROMPT_MS we should close at CLOSE_MS without reprompt."""
    spoken: list[str] = []
    closed: list[bool] = []

    class FakeSession:
        def on(self, *_args, **_kwargs):
            return None

        async def say(self, text: str, **_kwargs):
            spoken.append(text)

        async def aclose(self):
            closed.append(True)

    async def immediate_sleep(_sec: float):
        return None

    async def hangup_false(_session_id: str) -> bool:
        return False

    monkeypatch.setattr(vp_obs, "request_hangup", hangup_false)

    obs = VoicePipelineObserver(
        session_id="sess_123",
        sleep=immediate_sleep,
        silence_cfg=SilenceConfig(
            processing_delay_ack_ms=999999,
            user_silence_reprompt_ms=7000,
            user_silence_close_ms=1000,
        ),
    )
    obs.attach_to_session(FakeSession())
    obs._start_user_silence_timer()
    await asyncio.sleep(0)

    out = capsys.readouterr().out
    assert "call.ended" in out
    assert "user_silence_timeout" in out
    assert not any("Ben je er nog" in s for s in spoken)
    assert any("Ik hang op" in s for s in spoken)
    assert closed


@pytest.mark.asyncio
async def test_arm_user_silence_timer_triggers_reprompt_and_close(capsys, monkeypatch):
    """Arming the user-silence timer directly should still reprompt + close (telephony safety net)."""
    spoken: list[str] = []
    closed: list[bool] = []

    class FakeSession:
        def on(self, *_args, **_kwargs):
            return None

        async def say(self, text: str, **_kwargs):
            spoken.append(text)

        async def aclose(self):
            closed.append(True)

    async def immediate_sleep(_sec: float):
        return None

    async def hangup_false(_session_id: str) -> bool:
        return False

    monkeypatch.setattr(vp_obs, "request_hangup", hangup_false)

    obs = VoicePipelineObserver(
        session_id="sess_123",
        sleep=immediate_sleep,
        silence_cfg=SilenceConfig(
            processing_delay_ack_ms=999999,
            user_silence_reprompt_ms=0,
            user_silence_close_ms=1,
        ),
    )
    obs.attach_to_session(FakeSession())
    obs.arm_user_silence_timer()
    await asyncio.sleep(0)

    out = capsys.readouterr().out
    assert "call.ended" in out
    assert any("Ben je er nog" in s for s in spoken)
    assert any("Ik hang op" in s for s in spoken)
    assert closed

