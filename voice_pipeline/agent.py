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
from .instructions import get_instructions
from .observability import VoicePipelineObserver

# Load environment variables from .env_local
env_path = Path(__file__).parent.parent / ".env_local"
if env_path.exists():
    load_dotenv(env_path)

logger = get_logger(Component.VOICE_PIPELINE)


async def entrypoint(ctx: JobContext):
    """
    Agent entrypoint for handling LiveKit rooms.
    
    This is called by the LiveKit Agents framework when:
    - An inbound call arrives (via dispatch rule)
    - An outbound call is initiated (via API)
    """
    # Extract session_id from room name or metadata
    session_id = ctx.room.name or "unknown"
    session_logger = logger.with_session(session_id)
    
    session_logger.info(
        "Voice pipeline starting",
        room=ctx.room.name,
        job_id=ctx.job.id,
    )
    
    # Wait for first participant (the caller)
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    
    # Get first remote participant
    participant = await ctx.wait_for_participant()
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
    vad = silero.VAD.load()
    
    # Create agent session
    session_logger.info("Creating agent session")
    session = AgentSession(
        stt=stt,
        llm=llm_instance,
        tts=tts,
        vad=vad,
        chat_ctx=llm.ChatContext().append(
            role="system",
            text=get_instructions(),
        ),
        # Per VC-03: allow interruptions (barge-in)
        allow_interruptions=True,
        # Per VC-00: keep responses short
        # (this is enforced via instructions, not a hard limit)
    )
    
    # Attach observability hooks
    observer.attach_to_session(session)
    
    # Start the session
    session_logger.info("Starting agent session")
    session.start(ctx.room, participant)
    
    # Greet the user (per VC-00: natural phone conversation)
    await session.say("Hallo, waarmee kan ik je helpen?", allow_interruptions=True)
    
    session_logger.info("Agent session started successfully")


if __name__ == "__main__":
    # Initialize logging
    setup_logging(level="INFO", use_json=True)
    
    # Run the agent worker
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            # Agent will be dispatched via LiveKit dispatch rules
        )
    )

