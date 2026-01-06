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
from .instructions import get_instructions
from .observability import VoicePipelineObserver

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

    session_logger.info(
        "Voice pipeline starting",
        room=ctx.room.name,
        job_id=ctx.job.id,
        flow=dispatch_ctx.flow,
    )

    session_logger.info(
        "Participant joined",
        participant_identity=participant.identity,
        participant_sid=participant.sid,
    )
    
    # Load configuration
    config = get_config()
    
    # Create observability wrapper
    observer = VoicePipelineObserver(session_id=session_id)
    
    # Configure providers
    session_logger.debug("Configuring STT provider", provider="groq")
    stt = groq.STT(
        model="whisper-large-v3",
        language="nl",  # Dutch
        api_key=config.groq_api_key,
    )
    
    session_logger.debug("Configuring LLM provider", provider="groq", model=config.groq_model_llm)
    llm_instance = groq.LLM(
        model=config.groq_model_llm,
        temperature=0.7,
        api_key=config.groq_api_key,
    )
    
    session_logger.debug(
        "Configuring TTS provider",
        provider="azure",
        voice=config.azure_speech_voice,
    )
    tts = azure.TTS(
        speech_key=config.azure_speech_key,
        speech_region=config.azure_speech_region,
        voice=config.azure_speech_voice,
    )
    
    session_logger.debug("Configuring VAD", provider="silero")
    vad = _VAD or silero.VAD.load()
    
    # Create agent with instructions
    session_logger.info("Creating agent")
    agent = Agent(
        instructions=get_instructions(),
    )
    
    # Create agent session
    session_logger.info("Creating agent session")
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
    
    # Start the session
    session_logger.info("Starting agent session")
    await session.start(room=ctx.room, agent=agent)
    
    # Greet the user (per VC-00: natural phone conversation)
    try:
        await session.say("Hallo, waarmee kan ik je helpen?", allow_interruptions=True)
    except Exception as e:
        # Best-effort: call may already be disconnected/cancelled.
        session_logger.warning("Greeting not played", error=str(e), error_type=type(e).__name__)
    finally:
        # VC-02: user silence after a prompt should trigger reprompt + graceful close.
        # In telephony, TTS events may not always fire; arm explicitly after greeting.
        observer.arm_user_silence_timer()
    
    session_logger.info("Agent session started successfully")


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

