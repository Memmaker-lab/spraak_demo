"""
Google Cloud Text-to-Speech with Bidirectional Streaming.

Uses gRPC streaming API for lower latency compared to REST API.
Requires service account authentication (GOOGLE_APPLICATION_CREDENTIALS).

Key benefits:
- Lower time-to-first-audio (100-200ms vs 300-800ms)
- Streams audio as it's synthesized
- Compatible with Chirp 3: HD voices only
"""
import asyncio
import os
import struct
import time
from typing import Optional

from google.cloud import texttospeech_v1 as texttospeech
from livekit.agents import tts as tts_module
from livekit.agents._exceptions import APIError
from livekit.agents.types import APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS
from livekit.agents.utils import log_exceptions, shortuuid

from logging_setup import get_logger, Component

logger = get_logger(Component.VOICE_PIPELINE)


class GoogleCloudStreamingTTS(tts_module.TTS):
    """
    Google Cloud Text-to-Speech with bidirectional streaming support.
    
    Uses gRPC streaming for lower latency. Audio chunks are streamed as they're
    synthesized, reducing time-to-first-audio significantly.
    
    Requirements:
    - GOOGLE_APPLICATION_CREDENTIALS environment variable set
    - Chirp 3: HD voices only (streaming not supported for other voices)
    """

    def __init__(self, *, voice: str = "nl-NL-Chirp3-HD-Aoede", observer=None):
        # Get sample rate from environment variable (default: 16000)
        sample_rate = int(os.getenv("GOOGLE_TTS_SAMPLE_RATE", "16000"))
        
        super().__init__(
            capabilities=tts_module.TTSCapabilities(streaming=False),  # Chunked synthesis (not continuous streaming)
            sample_rate=sample_rate,
            num_channels=1,
        )
        self._voice = voice
        self._observer = observer
        self._sample_rate = sample_rate
        
        # Validate voice is Chirp3-HD (required for streaming)
        if "Chirp3-HD" not in voice:
            logger.warning(
                "Non-Chirp3-HD voice for streaming TTS",
                voice=voice,
                recommendation="Use Chirp3-HD voices for streaming support"
            )
        
        # Create async client (authenticated via GOOGLE_APPLICATION_CREDENTIALS)
        try:
            self._client = texttospeech.TextToSpeechAsyncClient()
            logger.info("Google Cloud Streaming TTS client initialized", voice=voice)
        except Exception as e:
            logger.error(
                "Failed to initialize Google Cloud TTS client",
                error=str(e),
                error_type=type(e).__name__
            )
            raise

    @property
    def model(self) -> str:
        return "google-cloud-tts-streaming"

    @property
    def provider(self) -> str:
        return "Google Cloud TTS (Streaming)"

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> tts_module.ChunkedStream:
        return _GoogleCloudStreamingChunkedStream(
            tts=self, 
            input_text=text, 
            conn_options=conn_options
        )


class _GoogleCloudStreamingChunkedStream(tts_module.ChunkedStream):
    def __init__(
        self, 
        *, 
        tts: GoogleCloudStreamingTTS, 
        input_text: str, 
        conn_options: APIConnectOptions
    ):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts = tts

    @log_exceptions(logger=logger)
    async def _run(self, output_emitter: tts_module.AudioEmitter) -> None:
        request_id = shortuuid()
        
        # Initialize emitter
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=self._tts._sample_rate,
            num_channels=1,
            mime_type="audio/pcm",
        )
        
        text = self._input_text
        
        # Set LLM response text in observer (TTS text is the LLM response)
        if self._tts._observer:
            self._tts._observer.set_llm_response_text(text)
        
        # Log TTS call start
        session_id = getattr(self._tts._observer, 'session_id', 'unknown') if self._tts._observer else 'unknown'
        
        logger.info(
            "TTS streaming call started",
            session_id=session_id,
            text=text,
            text_length=len(text),
        )
        
        try:
            t_start = time.perf_counter()
            t_first_chunk = None
            total_audio_bytes = 0
            chunk_count = 0
            
            # Create streaming config
            streaming_config = texttospeech.StreamingSynthesizeConfig(
                voice=texttospeech.VoiceSelectionParams(
                    name=self._tts._voice,
                    language_code="nl-NL",
                )
            )
            
            # Create config request (must be first in stream)
            config_request = texttospeech.StreamingSynthesizeRequest(
                streaming_config=streaming_config
            )
            
            # Request generator: send config, then text
            async def request_generator():
                yield config_request
                yield texttospeech.StreamingSynthesizeRequest(
                    input=texttospeech.StreamingSynthesisInput(text=text)
                )
            
            # Stream audio responses (async)
            stream = await self._tts._client.streaming_synthesize(request_generator())
            
            async for response in stream:
                if response.audio_content:
                    chunk_count += 1
                    chunk_size = len(response.audio_content)
                    total_audio_bytes += chunk_size
                    
                    # Track time to first audio chunk
                    if t_first_chunk is None:
                        t_first_chunk = time.perf_counter()
                        time_to_first_audio_ms = int((t_first_chunk - t_start) * 1000)
                        logger.info(
                            "TTS first chunk received",
                            session_id=session_id,
                            time_to_first_audio_ms=time_to_first_audio_ms,
                            chunk_size_bytes=chunk_size,
                        )
                    
                    # Apply fade-in to first chunk to prevent clicks
                    if chunk_count == 1 and chunk_size >= 4:
                        audio_data = self._apply_fade_in(response.audio_content)
                    else:
                        audio_data = response.audio_content
                    
                    # Push audio chunk immediately
                    output_emitter.push(audio_data)
                    
                    logger.debug(
                        "TTS chunk pushed",
                        chunk_number=chunk_count,
                        chunk_size_bytes=chunk_size,
                    )
            
            t_end = time.perf_counter()
            total_latency_ms = int((t_end - t_start) * 1000)
            
            logger.info(
                "TTS streaming call completed",
                session_id=session_id,
                text_length=len(text),
                total_latency_ms=total_latency_ms,
                time_to_first_audio_ms=int((t_first_chunk - t_start) * 1000) if t_first_chunk else None,
                chunks_received=chunk_count,
                total_audio_bytes=total_audio_bytes,
            )
            
        except Exception as e:
            logger.error(
                "Google Cloud TTS streaming exception",
                session_id=session_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True
            )
            raise APIError(f"Google Cloud TTS streaming exception: {e}") from e

    def _apply_fade_in(self, pcm_data: bytes) -> bytes:
        """
        Apply exponential fade-in to prevent audio clicks at start.
        
        Args:
            pcm_data: Raw PCM audio data (16-bit signed, little-endian)
        
        Returns:
            PCM data with fade-in applied
        """
        num_samples = len(pcm_data) // 2
        if num_samples == 0:
            return pcm_data
        
        # Unpack to samples
        samples = list(struct.unpack(f'<{num_samples}h', pcm_data))
        
        # Apply fade-in over first 50ms (800 samples at 16kHz)
        fade_in_samples = min(800, num_samples)
        if fade_in_samples > 0:
            for i in range(fade_in_samples):
                # Exponential fade (x^2 curve for smooth start)
                fade_factor = (i / fade_in_samples) ** 2
                samples[i] = int(samples[i] * fade_factor)
        
        # Pack back to bytes
        return struct.pack(f'<{len(samples)}h', *samples)
