"""
Voice Pipeline Agent implementation.

Implements telephone-native Dutch conversation per VC-00, VC-01, VC-02, VC-03.
Uses Groq (STT + LLM), Azure (TTS), and Silero (VAD).

All behavior is observable via structured events (OBS-00).
"""
import asyncio
import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    AgentSession,
    Agent,
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.plugins import groq, azure, silero

from logging_setup import get_logger, Component, setup_logging
from .config import get_config
from .context import build_dispatch_context
from .instructions import get_instructions, get_greeting_text, get_greeting_audio_path
from .observability import VoicePipelineObserver
from .google_cloud_tts import GoogleCloudTTS
from .google_cloud_tts_streaming import GoogleCloudStreamingTTS

# Load environment variables from .env_local / .env.local (local dev convenience).
# Note: start scripts also export env vars; this is best-effort and will not override existing.
root = Path(__file__).parent.parent
for name in (".env_local", ".env.local"):
    p = root / name
    if p.exists():
        load_dotenv(p, override=False)

logger = get_logger(Component.VOICE_PIPELINE)

# Prewarmed/shared instances (best-effort)
_VAD = None


async def entrypoint(ctx: JobContext):
    """
    Agent entrypoint for handling LiveKit rooms.
    
    This is called by the LiveKit Agents framework when:
    - An inbound call arrives (via dispatch rule)
    - An outbound call is initiated (via API)
    """
    # Connect and wait for first participant (the caller)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    # Get first remote participant
    participant = await ctx.wait_for_participant()

    dispatch_ctx = build_dispatch_context(
        room_name=ctx.room.name or "unknown",
        job_metadata=getattr(ctx.job, "metadata", None),
        participant_attributes=getattr(participant, "attributes", None),
    )
    session_id = dispatch_ctx.session_id
    session_logger = logger.with_session(session_id)

    # Enrich LiveKit's own job logs with correlation context (docs: JobContext.log_context_fields)
    try:
        ctx.log_context_fields = {
            "room_name": ctx.room.name,
            "session_id": session_id,
            "flow": dispatch_ctx.flow,
        }
    except Exception:
        # Best-effort only; don't crash the pipeline.
        pass

    # Log scenario being used
    scenario_name = dispatch_ctx.flow or os.getenv("AGENT_SCENARIO", "default")
    # Debug only - not shown in production logs
    session_logger.debug(
        "Voice pipeline starting",
        room=ctx.room.name,
        job_id=ctx.job.id,
        flow=dispatch_ctx.flow,
        scenario=scenario_name,
    )

    session_logger.debug(
        "Participant joined",
        participant_identity=participant.identity,
        participant_sid=participant.sid,
    )
    
    # Load configuration
    config = get_config()
    
    # Create observability wrapper
    observer = VoicePipelineObserver(
        session_id=session_id,
        max_duration_seconds=config.max_call_duration_seconds,
    )
    
    # Configure providers - debug only
    session_logger.debug(
        "STT provider configured",
        provider="groq",
        model="whisper-large-v3",
        language="nl",
    )
    stt = groq.STT(
        model="whisper-large-v3",
        language="nl",  # Dutch
        api_key=config.groq_api_key,
    )
    
    session_logger.debug(
        "LLM provider configured",
        provider="groq",
        model=config.groq_model_llm,
        temperature=0.1,
    )
    llm_instance = groq.LLM(
        model=config.groq_model_llm,
        # Lower temperature for more deterministic, less "creative" responses
        temperature=0.1,
        api_key=config.groq_api_key,
    )
    
    # LLM warmup - prevent cold start latency on first real call
    async def warmup_llm():
        """Make a tiny dummy request to warm up the LLM connection."""
        import time
        t_start = time.perf_counter()
        try:
            chat_ctx = llm.ChatContext()
            chat_ctx.append(role="user", text="Hi")
            async with llm_instance.chat(chat_ctx=chat_ctx) as stream:
                async for _ in stream:
                    break  # We only need first token to confirm connection
            latency_ms = int((time.perf_counter() - t_start) * 1000)
            session_logger.info(
                "LLM warmup completed",
                session_id=session_id,
                latency_ms=latency_ms,
            )
        except Exception as e:
            session_logger.warning(
                "LLM warmup failed (non-fatal)",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
            )
    
    # Run warmup in background (don't block agent startup)
    asyncio.create_task(warmup_llm())
    
    # TTS provider selection
    if config.tts_provider == "google":
        # Google Cloud Text-to-Speech
        # Choose between streaming (gRPC, lower latency) or REST API
        if config.google_tts_use_streaming:
            # Streaming TTS (requires service account authentication via GOOGLE_APPLICATION_CREDENTIALS)
            session_logger.debug(
                "TTS provider configured",
                provider="google_cloud_tts_streaming",
                voice=config.google_tts_voice,
                streaming=True,
            )
            tts = GoogleCloudStreamingTTS(
                voice=config.google_tts_voice,
                observer=observer,
            )
        else:
            # REST API (requires API key)
            if not config.google_tts_api_key:
                session_logger.error(
                    "Google TTS provider requested but GOOGLE_TTS_API_KEY is not set",
                )
                raise ValueError(
                    "Google TTS provider requires GOOGLE_TTS_API_KEY environment variable"
                )
            session_logger.debug(
                "TTS provider configured",
                provider="google_cloud_tts_rest",
                voice=config.google_tts_voice,
                streaming=False,
            )
            tts = GoogleCloudTTS(
                api_key=config.google_tts_api_key,
                voice=config.google_tts_voice,
                observer=observer,
            )
    else:
        # Default: Azure TTS
        session_logger.debug(
            "TTS provider configured",
            provider="azure",
            voice=config.azure_speech_voice,
            region=config.azure_speech_region,
        )
        tts = azure.TTS(
            speech_key=config.azure_speech_key,
            speech_region=config.azure_speech_region,
            voice=config.azure_speech_voice,
        )
    
    session_logger.debug("Configuring VAD", provider="silero")
    vad = _VAD or silero.VAD.load()
    
    # Create agent with scenario-based instructions - debug only
    session_logger.debug("Creating agent", scenario=scenario_name)
    agent = Agent(
        instructions=get_instructions(flow=dispatch_ctx.flow),
    )
    
    # Create agent session - debug only
    session_logger.debug("Creating agent session")
    session = AgentSession(
        stt=stt,
        llm=llm_instance,
        tts=tts,
        vad=vad,
        # Per VC-03: allow interruptions (barge-in)
        allow_interruptions=True,
        # Per VC-00: keep responses short
        # (this is enforced via instructions, not a hard limit)
    )
    
    # Attach observability hooks
    observer.attach_to_session(session)
    
    # Store observer reference for TTS logging (to pass LLM response text)
    # This is a workaround since LiveKit Agents doesn't expose LLM response directly
    if config.tts_provider == "google":
        # Set observer reference on TTS instance if possible
        # Note: This requires modifying GoogleCloudTTS to accept observer
        pass  # TODO: Implement if needed
    
    # Start the session - debug only
    session_logger.debug("Starting agent session")
    await session.start(room=ctx.room, agent=agent)
    
    # Greet the user (per VC-00: natural phone conversation)
    # Use scenario-based greeting (fixed text, currently via TTS, later can be WAV)
    greeting_text = get_greeting_text(flow=dispatch_ctx.flow)
    greeting_audio = get_greeting_audio_path(flow=dispatch_ctx.flow)
    
    try:
        if greeting_audio:
            # TODO: Play WAV file (future enhancement)
            # For now, fallback to TTS
            session_logger.debug(
                "Greeting audio file found, but WAV playback not yet implemented",
                audio_path=str(greeting_audio),
            )
            # Greeting: do not allow barge-in for the very first phrase
            await session.say(greeting_text, allow_interruptions=False)
        else:
            # Use TTS for fixed greeting text
            # Greeting: do not allow barge-in for the very first phrase
            await session.say(greeting_text, allow_interruptions=False)
    except Exception as e:
        # Best-effort: call may already be disconnected/cancelled.
        session_logger.warning("Greeting not played", error=str(e), error_type=type(e).__name__)
    finally:
        # VC-02: user silence after a prompt should trigger reprompt + graceful close.
        # In telephony, TTS events may not always fire; arm explicitly after greeting.
        observer.arm_user_silence_timer()
        
        # Arm call duration timer (starts after greeting)
        observer.arm_call_duration_timer()
    
    # Debug only - not shown in production logs
    session_logger.debug("Agent session started successfully")


def prewarm(_process):
    """
    Prewarm heavy resources to reduce time-to-first-audio on inbound calls.

    LiveKit Agents runs this once per worker process.
    """
    global _VAD
    try:
        _VAD = silero.VAD.load()
    except Exception:
        _VAD = None


if __name__ == "__main__":
    # Initialize logging
    setup_logging(level="INFO", use_json=True)
    
    # Run the agent worker
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            prewarm_fnc=prewarm,
            # For telephony dispatch rules that specify an agentName, this must match.
            # See LiveKit telephony docs: Agents telephony integration -> Agent dispatch.
            agent_name=os.getenv("LIVEKIT_AGENT_NAME", ""),
            # Agent will be dispatched via LiveKit dispatch rules
        )
    )

