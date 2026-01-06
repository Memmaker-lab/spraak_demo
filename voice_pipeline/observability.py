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

        # State tracking (documented events)
        self._agent_state: Optional[str] = None
        self._user_state: Optional[str] = None

        # Playback tracking
        self.tts_playing: bool = False
        self._barge_in_detected_ts: Optional[float] = None

        # Silence timers
        self._processing_timer: Optional[asyncio.Task] = None
        self._user_silence_timer: Optional[asyncio.Task] = None
        self._delay_ack_sent_for_turn: bool = False

        self._session: Optional["AgentSession"] = None

    def attach_to_session(self, session: "AgentSession"):
        self._session = session
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

        self.logger.info("Observability hooks attached")

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
        self.emitter.emit(
            "llm.request",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=turn_id,
        )

    def _emit_llm_response(self) -> None:
        turn_id = self.current_turn_id or self._new_turn()
        self.emitter.emit(
            "llm.response",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=turn_id,
        )

    def _emit_stt_final(self, *, transcript_length: int, language: Optional[str]) -> None:
        turn_id = self.current_turn_id or self._new_turn()
        if self._stt_final_emitted_for_turn:
            return
        self._stt_final_emitted_for_turn = True
        self.emitter.emit(
            "stt.final",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=turn_id,
            transcript_length=transcript_length,
            language=language,
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
        self._emit_stt_final(transcript_length=len(transcript), language=None)
        self._emit_turn_started(transcript_length=len(transcript))
        self._start_processing_timer()

    def _on_agent_started_speaking(self, event: dict[str, Any]):
        self.tts_playing = True
        self._emit_llm_response()
        self._cancel_processing_timer()
        self.emitter.emit(
            "tts.started",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=self.current_turn_id or self.session_id,
        )

    def _on_agent_stopped_speaking(self, event: dict[str, Any]):
        self.tts_playing = False
        cause = event.get("reason", "completed")
        extra: dict[str, Any] = {"cause": cause}
        if cause == "barge_in" and self._barge_in_detected_ts is not None:
            extra["time_to_tts_stop_ms"] = int((self._now() - self._barge_in_detected_ts) * 1000)
            self._barge_in_detected_ts = None
        self.emitter.emit(
            "tts.stopped",
            session_id=self.session_id,
            severity=Severity.INFO,
            correlation_id=self.current_turn_id or self.session_id,
            **extra,
        )
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
                self._start_processing_timer()

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
        text, lang = _parse_transcription_event(event, args, kwargs)
        text = (text or "").strip()
        self._record_user_activity()
        self._emit_stt_final(transcript_length=len(text), language=lang)

    def _on_close(self, event: Any) -> None:
        self._cancel_processing_timer()
        self._cancel_user_silence_timer()

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
            await self._sleep(self._silence.processing_delay_ack_ms / 1000.0)
            if self._delay_ack_sent_for_turn:
                return
            # Only acknowledge if we're still waiting to speak
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
                except Exception:
                    pass

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
        started_at = self._now()
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
                if self._is_user_silent_since(started_at):
                    await self._close_due_to_user_silence(correlation_id=started_turn)
                return

            await self._sleep(reprompt_ms / 1000.0)
            if self._is_user_silent_since(started_at):
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
                    except Exception:
                        pass

            remaining_ms = close_ms - reprompt_ms
            if remaining_ms <= 0:
                return
            await self._sleep(remaining_ms / 1000.0)
            if self._is_user_silent_since(started_at):
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
) -> tuple[Optional[str], Optional[str]]:
    # Prefer kwargs if present
    kw_text = kwargs.get("text") or kwargs.get("transcript") or kwargs.get("user_transcript")
    text: Optional[str] = kw_text if isinstance(kw_text, str) else None
    lang: Optional[str] = kwargs.get("language") if isinstance(kwargs.get("language"), str) else None

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
    if text is None and event is not None:
        text = _extract_text(event) or text
    if lang is None and event is not None:
        lang = _extract_language(event) or lang

    return text, lang

