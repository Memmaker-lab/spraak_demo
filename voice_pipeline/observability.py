"""
Voice Pipeline observability implementation.

Emits structured events per OBS-00, VC-01, VC-02, VC-03.
Tracks turn lifecycle, barge-in, silence handling, and provider interactions.
"""
import time
from typing import Optional, TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
    from livekit.agents import llm, stt, tts, vad
    from livekit.agents.pipeline import AgentSession

from logging_setup import get_logger, Component
from control_plane.events import EventEmitter, Severity


logger = get_logger(Component.VOICE_PIPELINE)


class VoicePipelineObserver:
    """
    Observability wrapper for Voice Pipeline.
    
    Emits OBS-00 events for:
    - Turn lifecycle (VC-01)
    - Barge-in detection (VC-03)
    - Silence handling (VC-02)
    - Provider requests/responses (STT, LLM, TTS)
    - VAD state changes
    """
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.emitter = EventEmitter(Component.VOICE_PIPELINE)
        self.logger = get_logger(Component.VOICE_PIPELINE, session_id=session_id)
        
        # Track current turn
        self.current_turn_id: Optional[str] = None
        self.user_last_audio_ts: Optional[float] = None
        self.tts_playing = False
    
    def attach_to_session(self, session: "AgentSession"):
        """Attach event listeners to an AgentSession."""
        self.logger.debug("Attaching observability hooks to agent session")
        
        # VAD events
        session.on("vad_state_changed", self._on_vad_state_changed)
        
        # User speech events
        session.on("user_started_speaking", self._on_user_started_speaking)
        session.on("user_stopped_speaking", self._on_user_stopped_speaking)
        
        # Transcription events
        session.on("user_speech_committed", self._on_user_speech_committed)
        
        # Agent response events
        session.on("agent_started_speaking", self._on_agent_started_speaking)
        session.on("agent_stopped_speaking", self._on_agent_stopped_speaking)
        
        # Turn events (if available in AgentSession)
        # Note: AgentSession may not expose all these events directly
        # We'll emit them based on the lifecycle we observe
        
        self.logger.info("Observability hooks attached")
    
    def _on_vad_state_changed(self, event):
        """VAD state changed (speaking/silence)."""
        state = event.get("state", "unknown")
        
        self.logger.debug("VAD state changed", state=state)
        
        # Emit OBS-00 event
        self.emitter.emit(
            "vad.state_changed",
            session_id=self.session_id,
            severity=Severity.DEBUG,
            state=state,
        )
    
    def _on_user_started_speaking(self, event):
        """User started speaking."""
        self.logger.debug("User started speaking")
        
        # Check for barge-in (VC-03)
        if self.tts_playing:
            barge_in_ts = time.time()
            self.logger.info("Barge-in detected", tts_was_playing=True)
            
            # Emit barge-in event
            self.emitter.emit(
                "barge_in.detected",
                session_id=self.session_id,
                severity=Severity.INFO,
                correlation_id=self.current_turn_id or self.session_id,
            )
    
    def _on_user_stopped_speaking(self, event):
        """User stopped speaking."""
        self.user_last_audio_ts = time.time()
        self.logger.debug("User stopped speaking", timestamp=self.user_last_audio_ts)
    
    def _on_user_speech_committed(self, event):
        """
        User speech committed (final transcription).
        This triggers a new turn.
        """
        transcript = event.get("text", "")
        self.logger.debug("User speech committed", transcript_length=len(transcript))
        
        # Generate turn ID
        turn_id = f"turn_{int(time.time() * 1000)}"
        self.current_turn_id = turn_id
        
        # Emit turn.started (VC-01)
        self.emitter.emit(
            "turn.started",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=turn_id,
            transcript_length=len(transcript),
        )
        
        # Log latency from user_last_audio to turn start
        if self.user_last_audio_ts:
            latency_ms = int((time.time() - self.user_last_audio_ts) * 1000)
            self.logger.debug(
                "Turn started",
                turn_id=turn_id,
                latency_from_user_audio_ms=latency_ms,
            )
    
    def _on_agent_started_speaking(self, event):
        """Agent (TTS) started speaking."""
        self.tts_playing = True
        self.logger.debug("Agent started speaking")
        
        # Emit tts.started
        self.emitter.emit(
            "tts.started",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=self.current_turn_id or self.session_id,
        )
        
        # Log latency from user_last_audio to TTS start (VC-01 responsiveness)
        if self.user_last_audio_ts:
            latency_ms = int((time.time() - self.user_last_audio_ts) * 1000)
            self.logger.info(
                "TTS started",
                latency_from_user_audio_ms=latency_ms,
                turn_id=self.current_turn_id,
            )
    
    def _on_agent_stopped_speaking(self, event):
        """Agent (TTS) stopped speaking."""
        self.tts_playing = False
        cause = event.get("reason", "completed")
        
        self.logger.debug("Agent stopped speaking", cause=cause)
        
        # Emit tts.stopped
        self.emitter.emit(
            "tts.stopped",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=self.current_turn_id or self.session_id,
            cause=cause,
        )

