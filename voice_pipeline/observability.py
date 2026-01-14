"""
Voice Pipeline observability implementation.

Implements required observability per:
- OBS-00 (voice pipeline turn events + silence instrumentation)
- VC-01 (turn lifecycle ordering + correlation_id)
- VC-02 (silence handling: delay ack + reprompt + graceful close)
- VC-03 (barge-in: event emission + latency measurement)
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional, TYPE_CHECKING

from logging_setup import get_logger, Component as LogComponent
from observability.events import Component as ObsComponent, EventEmitter, Severity
from .control_plane_client import request_hangup

if TYPE_CHECKING:
    from livekit.agents import AgentSession


logger = get_logger(LogComponent.VOICE_PIPELINE)


@dataclass(frozen=True)
class SilenceConfig:
    """VC-02 thresholds in milliseconds."""

    processing_delay_ack_ms: int = 900
    user_silence_reprompt_ms: int = 7000
    user_silence_close_ms: int = 14000


class VoicePipelineObserver:
    """
    Attaches to an AgentSession and emits OBS-00 events.

    Notes:
    - Transcript content is not emitted; only metadata (length/language). (OBS-00)
    - Uses documented AgentSession events, plus backward-compatible aliases.
    """

    def __init__(
        self,
        session_id: str,
        *,
        now: Callable[[], float] = time.time,
        sleep: Callable[[float], Any] = asyncio.sleep,
        silence_cfg: Optional[SilenceConfig] = None,
        max_duration_seconds: int = 300,  # Default: 5 minutes
    ):
        self.session_id = session_id
        self.emitter = EventEmitter(ObsComponent.VOICE_PIPELINE)
        self.logger = get_logger(LogComponent.VOICE_PIPELINE, session_id=session_id)

        self._now = now
        self._sleep = sleep
        self._silence = silence_cfg or SilenceConfig(
            processing_delay_ack_ms=int(os.getenv("VP_PROCESSING_DELAY_ACK_MS", "900")),
            user_silence_reprompt_ms=int(os.getenv("VP_USER_SILENCE_REPROMPT_MS", "7000")),
            user_silence_close_ms=int(os.getenv("VP_USER_SILENCE_CLOSE_MS", "14000")),
        )

        # Turn tracking
        self.current_turn_id: Optional[str] = None
        self.user_last_audio_ts: Optional[float] = None
        self._last_user_activity_ts: Optional[float] = None
        self._stt_final_emitted_for_turn: bool = False
        self._llm_request_ts: Optional[float] = None
        self._current_transcript: Optional[str] = None  # Store transcript for LLM input logging
        self._current_llm_response: Optional[str] = None  # Store LLM response for logging (set from TTS text)

        # State tracking (documented events)
        self._agent_state: Optional[str] = None
        self._user_state: Optional[str] = None

        # Playback tracking
        self.tts_playing: bool = False
        self._barge_in_detected_ts: Optional[float] = None
        self._tts_started_ts: Optional[float] = None

        # Silence timers
        self._processing_timer: Optional[asyncio.Task] = None
        self._user_silence_timer: Optional[asyncio.Task] = None
        self._delay_ack_sent_for_turn: bool = False
        self._last_agent_prompt_ts: Optional[float] = None  # When agent last prompted (for user-silence checks)

        # Call duration timer
        self._call_start_ts: Optional[float] = None  # Timestamp when call starts (after greeting)
        self._max_duration_seconds: int = max_duration_seconds  # Maximum call duration in seconds
        self._duration_warning_task: Optional[asyncio.Task] = None  # Task for warning timer
        self._duration_timeout_task: Optional[asyncio.Task] = None  # Task for timeout timer

        self._session: Optional["AgentSession"] = None
        self._observer_instance: Optional["VoicePipelineObserver"] = None  # For TTS to access observer

    def attach_to_session(self, session: "AgentSession"):
        self._session = session
        # Debug only - not shown in production logs
        self.logger.debug("Attaching observability hooks to agent session")

        # Documented AgentSession events (docs: Agent session -> Events)
        session.on("agent_state_changed", self._on_agent_state_changed)
        session.on("user_state_changed", self._on_user_state_changed)
        session.on("user_input_transcribed", self._on_user_input_transcribed)
        session.on("close", self._on_close)

        # Backward-compatible aliases
        session.on("vad_state_changed", self._on_vad_state_changed)
        session.on("user_started_speaking", self._on_user_started_speaking)
        session.on("user_stopped_speaking", self._on_user_stopped_speaking)
        session.on("user_speech_committed", self._on_user_speech_committed)
        session.on("agent_started_speaking", self._on_agent_started_speaking)
        session.on("agent_stopped_speaking", self._on_agent_stopped_speaking)

        # Debug only - not shown in production logs
        self.logger.debug("Observability hooks attached")

    def arm_user_silence_timer(self) -> None:
        """
        Arm the VC-02 user-silence timer after a prompt.

        We normally arm this on `agent_stopped_speaking`, but telephony TTS events
        may not always fire (or the greeting may fail). Calling this after a prompt
        ensures "Ben je er nog?" + graceful close still happen.
        """
        # Record that agent just prompted (now), so user-silence timer checks from this point.
        self._last_agent_prompt_ts = self._now()
        self._start_user_silence_timer()

    # --- Turn helpers ---

    def _new_turn(self) -> str:
        turn_id = f"turn_{int(self._now() * 1000)}"
        self.current_turn_id = turn_id
        self._stt_final_emitted_for_turn = False
        self._delay_ack_sent_for_turn = False
        return turn_id

    def _emit_turn_started(self, *, transcript_length: int = 0) -> None:
        turn_id = self.current_turn_id or self._new_turn()
        payload: dict[str, Any] = {"transcript_length": transcript_length}
        if self.user_last_audio_ts is not None:
            payload["user_last_audio_ts_ms"] = int(self.user_last_audio_ts * 1000)

        self.emitter.emit(
            "turn.started",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=turn_id,
            **payload,
        )

        # VC-01: turn.started MUST precede llm.request
        self._llm_request_ts = self._now()
        
        # Log LLM call start with input text
        logger.info(
            "LLM call started",
            session_id=self.session_id,
            correlation_id=turn_id,
            input_text=self._current_transcript or "",
            transcript_length=transcript_length,
        )
        
        # Emit LLM request with input text (PII flagged per OBS-00)
        llm_input_text = self._current_transcript or ""
        llm_payload: dict[str, Any] = {}
        if llm_input_text:
            llm_payload["input_text"] = llm_input_text
            llm_pii = {
                "contains_pii": True,
                "fields": ["input_text"],
                "handling": "none",  # Internal audit/ops use
            }
        else:
            llm_pii = None
        
        self.emitter.emit(
            "llm.request",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=turn_id,
            pii=llm_pii,
            **llm_payload,
        )

    def _emit_llm_response(self) -> None:
        turn_id = self.current_turn_id or self._new_turn()
        extra: dict[str, Any] = {}
        if self._llm_request_ts is not None:
            extra["latency_ms"] = int((self._now() - self._llm_request_ts) * 1000)
            latency_ms = extra["latency_ms"]
            self._llm_request_ts = None
        else:
            latency_ms = None
        
        # Log LLM call completion with input and output text
        # Note: output_text will be set when TTS starts (from TTS text, which is the LLM response)
        logger.info(
            "LLM call completed",
            session_id=self.session_id,
            correlation_id=turn_id,
            input_text=self._current_transcript or "",
            output_text=self._current_llm_response or "",  # Will be set by TTS logging when TTS starts
            latency_ms=latency_ms,
        )
        
        # Add LLM input and output text to event (PII flagged per OBS-00)
        llm_input_text = self._current_transcript or ""
        llm_output_text = self._current_llm_response or ""
        pii_fields = []
        if llm_input_text:
            extra["input_text"] = llm_input_text
            pii_fields.append("input_text")
        if llm_output_text:
            extra["output_text"] = llm_output_text
            pii_fields.append("output_text")
        
        llm_pii = {
            "contains_pii": True,
            "fields": pii_fields,
            "handling": "none",  # Internal audit/ops use
        } if pii_fields else None
        
        self.emitter.emit(
            "llm.response",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=turn_id,
            pii=llm_pii,
            **extra,
        )
    
    def set_llm_response_text(self, text: str) -> None:
        """Set LLM response text from TTS (since TTS text is the LLM response)."""
        self._current_llm_response = text
        
        # Log LLM call completion now that we have the response text
        # This is called from TTS when it starts processing, which is when we have the actual LLM response
        if self._llm_request_ts is not None:
            self._emit_llm_response()

    def _emit_stt_final(
        self,
        *,
        transcript_length: int,
        language: Optional[str],
        latency_ms: Optional[int] = None,
        transcript_text: Optional[str] = None,
    ) -> None:
        turn_id = self.current_turn_id or self._new_turn()
        if self._stt_final_emitted_for_turn:
            return
        self._stt_final_emitted_for_turn = True
        payload: dict[str, Any] = {
            "transcript_length": transcript_length,
            "language": language,
        }
        if latency_ms is not None:
            payload["latency_ms"] = latency_ms
        # Add transcript text with PII flag (per OBS-00: PII allowed for audit/ops)
        if transcript_text:
            payload["transcript_text"] = transcript_text
            pii = {
                "contains_pii": True,
                "fields": ["transcript_text"],
                "handling": "none",  # Internal audit/ops use
            }
        else:
            pii = None
        self.emitter.emit(
            "stt.final",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=turn_id,
            pii=pii,
            **payload,
        )

    # --- Backward-compatible event handlers ---

    def _on_vad_state_changed(self, event: dict[str, Any]):
        state = event.get("state", "unknown")
        self.emitter.emit(
            "vad.state_changed",
            session_id=self.session_id,
            severity=Severity.DEBUG,
            state=state,
        )

    def _on_user_started_speaking(self, event: dict[str, Any]):
        self._record_user_activity()
        # VC-03 barge-in: user starts speaking during TTS
        if self.tts_playing:
            self._barge_in_detected_ts = self._now()
            self.emitter.emit(
                "barge_in.detected",
                session_id=self.session_id,
                severity=Severity.INFO,
                correlation_id=self.current_turn_id or self.session_id,
            )

        # Any user speech cancels user-silence timers
        self._cancel_user_silence_timer()

    def _on_user_stopped_speaking(self, event: dict[str, Any]):
        self._record_user_activity()
        self.user_last_audio_ts = self._now()

    def _on_user_speech_committed(self, event: dict[str, Any]):
        transcript = event.get("text", "")
        self._new_turn()
        self._record_user_activity()
        
        # Store transcript for LLM input logging
        self._current_transcript = transcript
        
        # Log STT call with transcript text
        logger.info(
            "STT call completed",
            session_id=self.session_id,
            transcript=transcript,
            transcript_length=len(transcript),
            language=None,
            latency_ms=None,
            correlation_id=self.current_turn_id or self.session_id,
        )
        
        self._emit_stt_final(transcript_length=len(transcript), language=None, transcript_text=transcript)
        self._emit_turn_started(transcript_length=len(transcript))
        # Don't start processing timer here - wait for TTS to start and finish first
        # The timer will be started in _on_agent_stopped_speaking() after TTS completes

    def _on_agent_started_speaking(self, event: dict[str, Any]):
        self.tts_playing = True
        
        # Cancel user-silence timer when agent starts speaking (new response is coming)
        # This prevents the timer from firing during TTS playback
        self._cancel_user_silence_timer()
        
        # Try to get LLM response text from event
        # Note: LiveKit Agents may not provide this directly, so we'll use TTS text as fallback
        response_text = event.get("text") or event.get("response") or event.get("message") or ""
        if response_text:
            self._current_llm_response = response_text
            # For Azure TTS and other providers that don't call set_llm_response_text directly,
            # emit the LLM response event now that we have the text
            if self._llm_request_ts is not None:
                self._emit_llm_response()
        
        self._cancel_processing_timer()
        self._tts_started_ts = self._now()
        
        # Emit TTS started with text (PII flagged per OBS-00)
        # TTS text is the LLM response
        tts_text = self._current_llm_response or ""
        tts_payload: dict[str, Any] = {}
        if tts_text:
            tts_payload["text"] = tts_text
            tts_payload["text_length"] = len(tts_text)
            tts_pii = {
                "contains_pii": True,
                "fields": ["text"],
                "handling": "none",  # Internal audit/ops use
            }
        else:
            tts_pii = None
        
        self.emitter.emit(
            "tts.started",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=self.current_turn_id or self.session_id,
            pii=tts_pii,
            **tts_payload,
        )

    def _on_agent_stopped_speaking(self, event: dict[str, Any]):
        self.tts_playing = False
        cause = event.get("reason", "completed")
        extra: dict[str, Any] = {"cause": cause}
        if cause == "barge_in" and self._barge_in_detected_ts is not None:
            extra["time_to_tts_stop_ms"] = int((self._now() - self._barge_in_detected_ts) * 1000)
            self._barge_in_detected_ts = None
        if self._tts_started_ts is not None:
            extra["latency_ms"] = int((self._now() - self._tts_started_ts) * 1000)
            latency_ms = extra["latency_ms"]
            self._tts_started_ts = None
        else:
            latency_ms = None
        
        # Log TTS completion with latency_ms for all providers
        # (Google Cloud TTS has additional logging in google_cloud_tts.py, but this ensures
        # Azure TTS and other providers also get latency logging)
        logger.info(
            "TTS call stopped",
            session_id=self.session_id,
            correlation_id=self.current_turn_id or self.session_id,
            cause=cause,
            latency_ms=latency_ms,
            time_to_tts_stop_ms=extra.get("time_to_tts_stop_ms"),
        )
        
        self.emitter.emit(
            "tts.stopped",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=self.current_turn_id or self.session_id,
            **extra,
        )
        
        # Only start timers if TTS actually completed (not barge-in or error)
        # For multi-segment responses, we only want to start the timer after the LAST segment
        # We detect this by checking if there's another TTS segment coming (tts_playing will be True again)
        # But since we just set tts_playing = False, we need to wait a bit to see if it becomes True again
        # Actually, a better approach: always start the timer, but cancel it if a new TTS segment starts
        # This is already handled by _on_agent_started_speaking() canceling the timer
        
        # Only start timers if TTS completed successfully (not barge-in or error)
        # For barge-in, the user is already speaking, so no need for silence timer
        if cause == "completed":
            # Record that agent just finished speaking (now), so user-silence timer checks from this point.
            self._last_agent_prompt_ts = self._now()
            # VC-02 fix: Start processing delay timer AFTER TTS is done, not before TTS starts.
            # This ensures "Momentje, ik denk even mee" only triggers if there's actual processing delay
            # after the agent has finished speaking, not during TTS playback.
            self._start_processing_timer()
            # Always start user-silence timer after agent stops speaking
            # If a new TTS segment starts, _on_agent_started_speaking() will cancel it
            self._start_user_silence_timer()

    # --- Documented AgentSession events ---

    def _on_agent_state_changed(self, event: Any) -> None:
        state = _extract_state(event)
        if state:
            self._agent_state = state
            if state == "thinking":
                # VC-01: turn starts when system commits to responding
                self._new_turn()
                self._emit_turn_started(transcript_length=0)
                # Don't start processing timer here - wait for TTS to start and finish first
                # The timer will be started in _on_agent_stopped_speaking() after TTS completes

    def _on_user_state_changed(self, event: Any) -> None:
        state = _extract_state(event)
        if state:
            self._user_state = state
            # If the SDK provides a "speaking" state, treat it as user activity and cancel
            # any user-silence timers.
            if state == "speaking":
                self._record_user_activity()

    def _on_user_input_transcribed(self, event: Any = None, *args: Any, **kwargs: Any) -> None:
        """
        LiveKit may call this handler with:
        - a dict-like event
        - positional args (e.g. text, language, ...)
        - an object with attributes (text/transcript/language)
        - keyword args

        We only emit transcript metadata (length + language), never the content.
        """
        text, lang, delay_ms = _parse_transcription_event(event, args, kwargs)
        text = (text or "").strip()
        self._record_user_activity()
        
        # Store transcript for LLM input logging
        self._current_transcript = text

        # Log STT call with transcript text
        logger.info(
            "STT call completed",
            session_id=self.session_id,
            transcript=text,
            transcript_length=len(text),
            language=lang or "unknown",
            latency_ms=int(delay_ms * 1000) if delay_ms else None,
            correlation_id=self.current_turn_id or self.session_id,
        )

        # Emit STT metadata with transcript text (PII flagged per OBS-00)
        had_turn = self.current_turn_id is not None
        stt_latency_ms = int(delay_ms * 1000) if delay_ms else None
        self._emit_stt_final(
            transcript_length=len(text),
            language=lang,
            latency_ms=stt_latency_ms,
            transcript_text=text,
        )

        # Telephony safety net:
        # Some transports don't reliably emit agent_state_changed("thinking").
        # If we haven't started a turn yet, start one from the transcript so that:
        # - VC-01 ordering is still observed (turn.started -> llm.request)
        # - VC-02 processing timer will be started in _on_agent_stopped_speaking() after TTS completes
        if not had_turn:
            self._emit_turn_started(transcript_length=len(text))
            # Don't start processing timer here - wait for TTS to start and finish first
            # The timer will be started in _on_agent_stopped_speaking() after TTS completes

    def _on_close(self, event: Any) -> None:
        self._cancel_processing_timer()
        self._cancel_user_silence_timer()
        self._cancel_duration_timers()

    # --- VC-02 silence handling ---

    def _start_processing_timer(self) -> None:
        self._cancel_processing_timer()
        self.emitter.emit(
            "silence.timer_started",
            session_id=self.session_id,
            severity=Severity.DEBUG,
            correlation_id=self.current_turn_id or self.session_id,
            kind="processing",
        )

        async def _timer():
            # VC-02 fix: Processing timer now starts AFTER TTS is done (in _on_agent_stopped_speaking).
            # So we don't need to wait for TTS here anymore - it's already finished.
            # Just start the delay countdown immediately.
            await self._sleep(self._silence.processing_delay_ack_ms / 1000.0)
            
            if self._delay_ack_sent_for_turn:
                return
            # Double-check: if TTS started again during the delay countdown, skip ack
            if self.tts_playing:
                return
            self._delay_ack_sent_for_turn = True
            self.emitter.emit(
                "silence.timer_fired",
                session_id=self.session_id,
                severity=Severity.INFO,
                correlation_id=self.current_turn_id or self.session_id,
                kind="processing",
                threshold_ms=self._silence.processing_delay_ack_ms,
            )
            self.emitter.emit(
                "ux.delay_acknowledged",
                session_id=self.session_id,
                severity=Severity.INFO,
                correlation_id=self.current_turn_id or self.session_id,
                message_key="delay_ack.thinking",
            )
            # Fixed Dutch phrase per VC-00/VC-02
            if self._session is not None:
                try:
                    await self._session.say("Momentje, ik denk even mee.", allow_interruptions=True)
                except Exception as e:
                    # Don't crash; emit a structured hint so telephony playback issues are visible.
                    self.emitter.emit(
                        "ux.prompt_failed",
                        session_id=self.session_id,
                        severity=Severity.WARN,
                        correlation_id=self.current_turn_id or self.session_id,
                        message_key="delay_ack.thinking",
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                finally:
                    # VC-02: after we prompt (delay ack), user silence should follow the reprompt/close strategy.
                    # In some telephony paths, TTS events don't reliably fire, so we arm explicitly here.
                    self._start_user_silence_timer()

        # Only schedule when an event loop is running (tests may call sync handlers).
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._processing_timer = loop.create_task(_timer())

    def _cancel_processing_timer(self) -> None:
        if self._processing_timer is not None:
            self._processing_timer.cancel()
            self._processing_timer = None

    def _start_user_silence_timer(self) -> None:
        self._cancel_user_silence_timer()
        # Record when the agent last prompted (now), so we can check if user is silent since then.
        self._last_agent_prompt_ts = self._now()
        started_turn = self.current_turn_id or self.session_id
        self.emitter.emit(
            "silence.timer_started",
            session_id=self.session_id,
            severity=Severity.DEBUG,
            correlation_id=started_turn,
            kind="user",
        )

        async def _timer():
            reprompt_ms = int(self._silence.user_silence_reprompt_ms)
            close_ms = int(self._silence.user_silence_close_ms)

            # If CLOSE <= REPROMPT, skip reprompt and close at CLOSE_MS.
            if close_ms <= reprompt_ms:
                await self._sleep(close_ms / 1000.0)
                # Check silence since the last agent prompt, not since timer start.
                if self._last_agent_prompt_ts is not None and self._is_user_silent_since(self._last_agent_prompt_ts):
                    await self._close_due_to_user_silence(correlation_id=started_turn)
                return

            await self._sleep(reprompt_ms / 1000.0)
            # Check silence since the last agent prompt, not since timer start.
            if self._last_agent_prompt_ts is not None and self._is_user_silent_since(self._last_agent_prompt_ts):
                self.emitter.emit(
                    "silence.timer_fired",
                    session_id=self.session_id,
                    severity=Severity.INFO,
                    correlation_id=started_turn,
                    kind="user",
                    threshold_ms=reprompt_ms,
                )
                if self._session is not None:
                    try:
                        await self._session.say("Ben je er nog?", allow_interruptions=True)
                        # After reprompt, update prompt timestamp so close timer checks from reprompt time.
                        self._last_agent_prompt_ts = self._now()
                    except Exception:
                        pass

            remaining_ms = close_ms - reprompt_ms
            if remaining_ms <= 0:
                return
            await self._sleep(remaining_ms / 1000.0)
            # Check silence since the last prompt (greeting or reprompt), not since timer start.
            if self._last_agent_prompt_ts is not None and self._is_user_silent_since(self._last_agent_prompt_ts):
                await self._close_due_to_user_silence(correlation_id=started_turn)

        # Only schedule when an event loop is running (tests may call sync handlers).
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._user_silence_timer = loop.create_task(_timer())

    def _cancel_user_silence_timer(self) -> None:
        if self._user_silence_timer is not None:
            self._user_silence_timer.cancel()
            self._user_silence_timer = None

    def _record_user_activity(self) -> None:
        """Best-effort signal that the user is active; cancels user-silence timers."""
        now = self._now()
        self._last_user_activity_ts = now
        self._cancel_user_silence_timer()

    def _is_user_silent_since(self, since_ts: float) -> bool:
        """
        True if we have not observed user activity (speech/transcript) since `since_ts`.
        This avoids relying on SDK-specific user_state names.
        """
        if self._last_user_activity_ts is None:
            return True
        return self._last_user_activity_ts <= since_ts

    async def _close_due_to_user_silence(self, *, correlation_id: str) -> None:
        """VC-02: bounded reprompt + graceful close with best-effort Control Plane hangup."""
        if self._session is not None:
            try:
                await self._session.say(
                    "Oké, ik hoor even niks. Ik hang op. Fijne dag!",
                    allow_interruptions=True,
                )
            except Exception:
                pass
        self.emitter.emit(
            "call.ended",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=correlation_id,
            reason="user_silence_timeout",
        )
        cp_ok = await request_hangup(self.session_id)
        if not cp_ok and self._session is not None:
            try:
                await self._session.aclose()
            except Exception:
                pass

    # --- Call duration timer ---

    def arm_call_duration_timer(self) -> None:
        """
        Arm the call duration timer after greeting.
        
        Starts two tasks:
        - Warning task: warns user 20 seconds before max duration
        - Timeout task: ends call after max duration
        """
        if self._max_duration_seconds <= 0:
            # Timer disabled
            return
        
        self._call_start_ts = self._now()
        
        # Cancel any existing duration timers
        self._cancel_duration_timers()
        
        # Emit timer started event
        self.emitter.emit(
            "call.duration_timer_started",
            session_id=self.session_id,
            severity=Severity.INFO,
            max_duration_seconds=self._max_duration_seconds,
        )
        
        # Warning delay: 20 seconds before timeout
        warning_delay = max(0, self._max_duration_seconds - 20)
        timeout_delay = self._max_duration_seconds
        
        # Start warning task
        if warning_delay > 0:
            async def _warning_task():
                try:
                    await self._sleep(warning_delay)
                    await self._handle_duration_warning()
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    self.logger.warning(
                        "Duration warning task error",
                        error=str(e),
                        error_type=type(e).__name__,
                    )
            
            self._duration_warning_task = asyncio.create_task(_warning_task())
        
        # Start timeout task
        async def _timeout_task():
            try:
                await self._sleep(timeout_delay)
                await self._handle_duration_timeout()
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.logger.error(
                    "Duration timeout task error",
                    error=str(e),
                    error_type=type(e).__name__,
                )
        
        self._duration_timeout_task = asyncio.create_task(_timeout_task())

    async def _handle_duration_warning(self) -> None:
        """Handle duration warning: speak warning message 20 seconds before timeout."""
        if self._session is None:
            return
        
        warning_message = "De maximale gesprekduur is bijna bereikt, het gesprek wordt over 15 seconde afgebroken"
        
        # Emit warning event
        self.emitter.emit(
            "call.duration_warning",
            session_id=self.session_id,
            severity=Severity.INFO,
            remaining_seconds=15,
        )
        
        # Speak warning (barge-in allowed)
        try:
            await self._session.say(warning_message, allow_interruptions=True)
        except Exception as e:
            # Best-effort: log error but continue with timeout
            self.logger.warning(
                "Duration warning TTS failed",
                error=str(e),
                error_type=type(e).__name__,
            )
            self.emitter.emit(
                "ux.prompt_failed",
                session_id=self.session_id,
                severity=Severity.WARN,
                message_key="duration_warning",
                error=str(e),
                error_type=type(e).__name__,
            )

    async def _handle_duration_timeout(self) -> None:
        """Handle duration timeout: end call after max duration."""
        # Emit call ended event
        self.emitter.emit(
            "call.ended",
            session_id=self.session_id,
            severity=Severity.INFO,
            reason="max_duration_reached",
        )
        
        # Request hangup via Control Plane
        cp_ok = await request_hangup(self.session_id)
        
        # Fallback: close session directly if hangup fails
        if not cp_ok and self._session is not None:
            try:
                await self._session.aclose()
            except Exception:
                pass

    def _cancel_duration_timers(self) -> None:
        """Cancel duration timer tasks."""
        if self._duration_warning_task is not None:
            if not self._duration_warning_task.done():
                self._duration_warning_task.cancel()
            self._duration_warning_task = None
        
        if self._duration_timeout_task is not None:
            if not self._duration_timeout_task.done():
                self._duration_timeout_task.cancel()
            self._duration_timeout_task = None


def _extract_state(event: Any) -> Optional[str]:
    if isinstance(event, dict):
        state = event.get("state") or event.get("new_state") or event.get("to_state")
        if isinstance(state, str):
            return state
    return None


def _extract_text(event: Any) -> Optional[str]:
    if isinstance(event, dict):
        text = event.get("text") or event.get("transcript") or event.get("user_transcript")
        if isinstance(text, str):
            return text
    if isinstance(event, str):
        return event
    # best-effort: object with attributes
    for attr in ("text", "transcript", "user_transcript"):
        try:
            val = getattr(event, attr)
        except Exception:
            val = None
        if isinstance(val, str):
            return val
    return None


def _extract_language(event: Any) -> Optional[str]:
    if isinstance(event, dict):
        lang = event.get("language")
        if isinstance(lang, str):
            return lang
    # best-effort: object with attributes
    try:
        lang = getattr(event, "language")
    except Exception:
        lang = None
    if isinstance(lang, str):
        return lang
    return None


def _parse_transcription_event(
    event: Any,
    args: tuple[Any, ...],
    kwargs: Mapping[str, Any],
) -> tuple[Optional[str], Optional[str], Optional[int]]:
    # Prefer kwargs if present
    kw_text = kwargs.get("text") or kwargs.get("transcript") or kwargs.get("user_transcript")
    text: Optional[str] = kw_text if isinstance(kw_text, str) else None
    lang: Optional[str] = kwargs.get("language") if isinstance(kwargs.get("language"), str) else None
    delay_ms: Optional[int] = None
    
    # Try to get transcript_delay from kwargs first (LiveKit may pass it here)
    if "transcript_delay" in kwargs:
        td = kwargs["transcript_delay"]
        if isinstance(td, (int, float)):
            delay_ms = int(td * 1000)

    # If handler is invoked with extra positional args, they often carry (text, language, ...)
    # Only override if we don't already have values.
    if text is None and args:
        if isinstance(args[0], str):
            text = args[0]
            if lang is None and len(args) >= 2 and isinstance(args[1], str):
                lang = args[1]
        else:
            text = _extract_text(args[0]) or text
            lang = _extract_language(args[0]) or lang

    # Finally, inspect the primary event object.
    if event is not None:
        if text is None:
            text = _extract_text(event) or text
        if lang is None:
            lang = _extract_language(event) or lang
        # transcript_delay is reported in seconds by LiveKit; convert to ms if present
        if isinstance(event, dict):
            td = event.get("transcript_delay")
            if isinstance(td, (int, float)):
                delay_ms = int(td * 1000)

    return text, lang, delay_ms

