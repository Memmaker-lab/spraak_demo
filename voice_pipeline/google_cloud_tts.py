"""
Google Cloud Text-to-Speech via REST API.

Uses API key authentication (not service account JSON) for simplicity.
Output: LINEAR16 PCM 16kHz 16-bit mono, compatible with LiveKit Agents.
"""
import asyncio
import base64
import os
import re
import struct
import time
from typing import List, Optional, Tuple

import aiohttp
from livekit.agents import tts as tts_module
from livekit.agents._exceptions import APIError
from livekit.agents.types import APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS
from livekit.agents.utils import log_exceptions, shortuuid

from logging_setup import get_logger, Component

logger = get_logger(Component.VOICE_PIPELINE)


def split_text_into_chunks(text: str, max_chunks: int = 3) -> List[str]:
    """
    Split text into chunks on sentence boundaries for parallel TTS.
    
    Args:
        text: Input text to split
        max_chunks: Maximum number of chunks to create
    
    Returns:
        List of text chunks, each ending on a sentence boundary when possible
    """
    if not text or max_chunks <= 1:
        return [text] if text else []
    
    # Split on sentence endings (. ! ?) followed by whitespace
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    
    # Filter out empty sentences
    sentences = [s.strip() for s in sentences if s.strip()]
    
    if len(sentences) <= 1:
        return [text]
    
    if len(sentences) <= max_chunks:
        return sentences
    
    # Distribute sentences across chunks evenly
    chunk_size = len(sentences) // max_chunks
    remainder = len(sentences) % max_chunks
    
    chunks = []
    idx = 0
    for i in range(max_chunks):
        # Add one extra sentence to early chunks if there's a remainder
        size = chunk_size + (1 if i < remainder else 0)
        if idx < len(sentences):
            chunk = ' '.join(sentences[idx:idx + size])
            if chunk:
                chunks.append(chunk)
            idx += size
    
    return chunks


def combine_audio_chunks(chunks: List[bytes], sample_rate: int = 16000) -> bytes:
    """
    Combine multiple PCM audio chunks into one continuous stream.
    
    Applies crossfade between chunks to prevent audio clicks.
    
    Args:
        chunks: List of PCM audio data (16-bit signed, little-endian)
        sample_rate: Audio sample rate in Hz
    
    Returns:
        Combined PCM audio data
    """
    if not chunks:
        return b''
    
    if len(chunks) == 1:
        return chunks[0]
    
    # Crossfade duration in samples (10ms)
    crossfade_samples = int(sample_rate * 0.010)
    
    combined_samples = []
    
    for i, chunk in enumerate(chunks):
        if len(chunk) < 2:
            continue
            
        num_samples = len(chunk) // 2
        samples = list(struct.unpack(f'<{num_samples}h', chunk))
        
        if i == 0:
            # First chunk: apply fade-out at end
            if len(samples) > crossfade_samples:
                for j in range(crossfade_samples):
                    fade_factor = 1.0 - (j / crossfade_samples)
                    idx = len(samples) - crossfade_samples + j
                    samples[idx] = int(samples[idx] * fade_factor)
            combined_samples.extend(samples)
        else:
            # Subsequent chunks: apply fade-in at start and overlap with previous
            if len(samples) > crossfade_samples and len(combined_samples) > crossfade_samples:
                # Apply fade-in
                for j in range(crossfade_samples):
                    fade_factor = j / crossfade_samples
                    samples[j] = int(samples[j] * fade_factor)
                
                # Overlap with previous chunk's fade-out
                overlap_start = len(combined_samples) - crossfade_samples
                for j in range(crossfade_samples):
                    combined_samples[overlap_start + j] += samples[j]
                    # Clip to prevent overflow
                    combined_samples[overlap_start + j] = max(-32768, min(32767, combined_samples[overlap_start + j]))
                
                # Add remaining samples
                combined_samples.extend(samples[crossfade_samples:])
            else:
                combined_samples.extend(samples)
    
    # Pack back to bytes
    return struct.pack(f'<{len(combined_samples)}h', *combined_samples)


def normalize_phone_sequences(text: str) -> str:
    """
    Normalize phone number sequences for better TTS pronunciation.
    
    Example: "+31 970 102 0647" -> "plus eenendertig negen zeven nul een nul twee nul zes vier zeven"
    """
    # Pattern for phone numbers (international format, spaces/dashes allowed)
    phone_pattern = r'(\+?\d{1,3}[\s\-]?)(\d{1,4}[\s\-]?)(\d{1,4}[\s\-]?)(\d{1,4}[\s\-]?)(\d{1,4}[\s\-]?)(\d{1,4}[\s\-]?)(\d{1,4}[\s\-]?)(\d{1,4}[\s\-]?)'
    
    def replace_phone(match):
        full = match.group(0).replace(' ', '').replace('-', '')
        if not full or len(full) < 6:
            return match.group(0)  # Too short, probably not a phone number
        
        # Simple: spell out digits
        result = []
        if full.startswith('+'):
            result.append('plus')
            full = full[1:]
        
        # Map digits to Dutch words
        digit_map = {
            '0': 'nul', '1': 'een', '2': 'twee', '3': 'drie',
            '4': 'vier', '5': 'vijf', '6': 'zes', '7': 'zeven',
            '8': 'acht', '9': 'negen'
        }
        
        for digit in full:
            if digit in digit_map:
                result.append(digit_map[digit])
        
        return ' '.join(result) if result else match.group(0)
    
    return re.sub(phone_pattern, replace_phone, text)


def normalize_numbers_to_words(text: str) -> str:
    """
    Normalize standalone numbers to Dutch words for better TTS pronunciation.
    
    Example: "123" -> "honderd drieëntwintig"
    """
    # Simple approach: convert standalone numbers (1-999) to words
    # For now, we'll do a basic conversion for common cases
    # A full implementation would handle all numbers, but this is a start
    
    number_pattern = r'\b(\d{1,3})\b'
    
    def number_to_dutch(num_str: str) -> str:
        num = int(num_str)
        if num == 0:
            return 'nul'
        if num < 20:
            words = ['nul', 'een', 'twee', 'drie', 'vier', 'vijf', 'zes', 'zeven', 'acht', 'negen',
                     'tien', 'elf', 'twaalf', 'dertien', 'veertien', 'vijftien', 'zestien', 'zeventien',
                     'achttien', 'negentien']
            return words[num]
        if num < 100:
            tens = num // 10
            ones = num % 10
            tens_words = ['', '', 'twintig', 'dertig', 'veertig', 'vijftig', 'zestig', 'zeventig', 'tachtig', 'negentig']
            if ones == 0:
                return tens_words[tens]
            ones_words = ['', 'een', 'twee', 'drie', 'vier', 'vijf', 'zes', 'zeven', 'acht', 'negen']
            return f"{ones_words[ones]}en{tens_words[tens]}"
        if num < 1000:
            hundreds = num // 100
            remainder = num % 100
            hundreds_word = ['', 'honderd', 'tweehonderd', 'driehonderd', 'vierhonderd', 'vijfhonderd',
                            'zeshonderd', 'zevenhonderd', 'achthonderd', 'negenhonderd'][hundreds]
            if remainder == 0:
                return hundreds_word
            return f"{hundreds_word} {number_to_dutch(str(remainder))}"
        # For larger numbers, return as-is (could be extended)
        return num_str
    
    def replace_number(match):
        return number_to_dutch(match.group(1))
    
    return re.sub(number_pattern, replace_number, text)


class GoogleCloudTTS(tts_module.TTS):
    """Google Cloud Text-to-Speech -> raw PCM 16-bit mono for LiveKit Agents.
    
    Sample rate is configurable via GOOGLE_TTS_SAMPLE_RATE environment variable.
    Default: 16000 Hz. For phone quality, use 8000 Hz.
    """

    def __init__(self, *, api_key: str, voice: str = "nl-NL-Chirp3-HD-Algenib", observer=None):
        # Get sample rate from environment variable (default: 16000, 8000 for phone)
        sample_rate = int(os.getenv("GOOGLE_TTS_SAMPLE_RATE", "16000"))
        
        super().__init__(
            capabilities=tts_module.TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=1,
        )
        self._api_key = api_key
        self._voice = voice
        self._observer = observer  # For setting LLM response text
        self._sample_rate = sample_rate  # Store for use in API calls

        # Parallel TTS configuration
        self._parallel_enabled = os.getenv("GOOGLE_TTS_PARALLEL_ENABLED", "false").lower() == "true"
        self._parallel_max_chunks = int(os.getenv("GOOGLE_TTS_PARALLEL_MAX_CHUNKS", "3"))
        self._parallel_min_text_length = int(os.getenv("GOOGLE_TTS_PARALLEL_MIN_TEXT_LENGTH", "100"))

        # Connection pooling
        self._http_session: Optional[aiohttp.ClientSession] = None
        self._connector: Optional[aiohttp.TCPConnector] = None

        if not self._api_key:
            raise ValueError(
                "Google Cloud TTS requires a valid API key in GOOGLE_TTS_API_KEY"
            )

    @property
    def model(self) -> str:
        return "google-cloud-tts"

    @property
    def provider(self) -> str:
        return "Google Cloud TTS"

    def synthesize(
        self, text: str, *, conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS
    ) -> tts_module.ChunkedStream:
        return _GoogleCloudChunkedStream(tts=self, input_text=text, conn_options=conn_options)

    def _get_or_create_session(self) -> aiohttp.ClientSession:
        """
        Get or create shared HTTP session with connection pooling.
        
        Reuses TCP connections between requests to reduce latency.
        """
        if self._http_session is None or self._http_session.closed:
            # Get configuration from environment variables (optional tuning)
            pool_size = int(os.getenv("GOOGLE_TTS_CONNECTION_POOL_SIZE", "10"))
            connect_timeout = float(os.getenv("GOOGLE_TTS_CONNECTION_TIMEOUT", "3.0"))
            total_timeout = float(os.getenv("GOOGLE_TTS_CONNECTION_TOTAL_TIMEOUT", "10.0"))

            # Create connector with connection pooling
            self._connector = aiohttp.TCPConnector(
                limit=pool_size,  # Max total connections
                limit_per_host=pool_size,  # Max per host (same as total for single host)
                ttl_dns_cache=300,  # DNS cache TTL (5 minutes)
                force_close=False,  # Keep connections alive for reuse
            )

            # Configure timeouts
            timeout = aiohttp.ClientTimeout(
                total=total_timeout,  # Total request timeout
                connect=connect_timeout,  # Connection timeout
            )

            # Create session with connection pooling
            self._http_session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout,
            )

            logger.info(
                "TTS connection pool created",
                pool_size=pool_size,
                connect_timeout_ms=int(connect_timeout * 1000),
                total_timeout_ms=int(total_timeout * 1000),
            )
        else:
            logger.debug("TTS connection pool reused")

        return self._http_session

    async def aclose(self) -> None:
        """
        Best-effort cleanup of HTTP session and connector.
        Safe to call multiple times.
        """
        if self._http_session is not None:
            try:
                await self._http_session.close()
                logger.info("TTS connection pool closed")
            except Exception as e:
                logger.warning(
                    "Error closing TTS HTTP session",
                    error=str(e),
                    error_type=type(e).__name__,
                )
            finally:
                self._http_session = None
                self._connector = None

    def _create_tts_payload(self, text: str) -> dict:
        """
        Create TTS API payload for given text.
        
        Args:
            text: Text to synthesize
        
        Returns:
            Payload dictionary for Google TTS API
        """
        return {
            "input": {"text": text},
            "voice": {
                "languageCode": "nl-NL",
                "name": self._voice or "nl-NL-Chirp3-HD-Algenib",
            },
            "audioConfig": {
                "audioEncoding": "LINEAR16",
                "sampleRateHertz": self._sample_rate,
            },
        }

    async def synthesize_chunk(self, text: str, chunk_index: int = 0) -> Tuple[int, bytes]:
        """
        Synthesize a single chunk of text.
        
        Args:
            text: Text to synthesize
            chunk_index: Index of this chunk (for ordering)
        
        Returns:
            Tuple of (chunk_index, pcm_audio_data)
        """
        url = "https://texttospeech.googleapis.com/v1/text:synthesize"
        params = {"key": self._api_key}
        payload = self._create_tts_payload(text)
        
        session = self._get_or_create_session()
        
        t_start = time.perf_counter()
        async with session.post(url, params=params, json=payload) as response:
            if response.status != 200:
                error_text = await response.text()
                logger.error(
                    "TTS chunk synthesis error",
                    chunk_index=chunk_index,
                    status_code=response.status,
                    error_text=error_text[:200],
                )
                raise APIError(f"Google Cloud TTS API error: {response.status}")
            
            data = await response.json()
            audio_b64 = data.get("audioContent")
            if not audio_b64:
                raise APIError("Google Cloud TTS: no audioContent in response")
            
            pcm_data = base64.b64decode(audio_b64)
            t_end = time.perf_counter()
            
            logger.debug(
                "TTS chunk completed",
                chunk_index=chunk_index,
                text_length=len(text),
                latency_ms=int((t_end - t_start) * 1000),
            )
            
            return (chunk_index, pcm_data)

    async def synthesize_parallel(self, text: str, session_id: str = "unknown") -> bytes:
        """
        Synthesize text by splitting into chunks and processing in parallel.
        
        Args:
            text: Text to synthesize
            session_id: Session ID for logging
        
        Returns:
            Combined PCM audio data
        """
        # Split text into chunks
        chunks = split_text_into_chunks(text, max_chunks=self._parallel_max_chunks)
        
        if len(chunks) <= 1:
            # Not enough chunks for parallel, use single synthesis
            logger.debug("TTS parallel skipped - single chunk", text_length=len(text))
            result = await self.synthesize_chunk(text, 0)
            return result[1]
        
        logger.info(
            "TTS parallel started",
            session_id=session_id,
            num_chunks=len(chunks),
            chunk_lengths=[len(c) for c in chunks],
        )
        
        t_start = time.perf_counter()
        
        # Create tasks for parallel synthesis
        tasks = [
            self.synthesize_chunk(chunk, i)
            for i, chunk in enumerate(chunks)
        ]
        
        # Execute all tasks in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results, filter out errors
        successful_chunks: List[Tuple[int, bytes]] = []
        errors = []
        
        for result in results:
            if isinstance(result, Exception):
                errors.append(result)
                logger.warning(
                    "TTS chunk failed",
                    error=str(result),
                    error_type=type(result).__name__,
                )
            else:
                successful_chunks.append(result)
        
        if not successful_chunks:
            # All chunks failed, raise the first error
            raise errors[0] if errors else APIError("All TTS chunks failed")
        
        # Sort by chunk index to ensure correct order
        successful_chunks.sort(key=lambda x: x[0])
        
        # Extract audio data in order
        audio_chunks = [chunk[1] for chunk in successful_chunks]
        
        # Combine audio chunks
        combined_audio = combine_audio_chunks(audio_chunks, self._sample_rate)
        
        t_end = time.perf_counter()
        
        logger.info(
            "TTS parallel completed",
            session_id=session_id,
            num_chunks=len(chunks),
            successful_chunks=len(successful_chunks),
            failed_chunks=len(errors),
            total_latency_ms=int((t_end - t_start) * 1000),
        )
        
        return combined_audio


class _GoogleCloudChunkedStream(tts_module.ChunkedStream):
    def __init__(self, *, tts: GoogleCloudTTS, input_text: str, conn_options: APIConnectOptions):
        super().__init__(tts=tts, input_text=input_text, conn_options=conn_options)
        self._tts = tts

    @log_exceptions(logger=logger)
    async def _run(self, output_emitter: tts_module.AudioEmitter) -> None:
        request_id = shortuuid()

        # Initialize emitter; we push one audio block once Google responds
        output_emitter.initialize(
            request_id=request_id,
            sample_rate=self._tts._sample_rate,
            num_channels=1,
            mime_type="audio/pcm",
        )

        # Text normalization (same logic as in the example)
        original_text = self._input_text

        #t0 = time.perf_counter()
        #text = normalize_phone_sequences(original_text)
        #t1 = time.perf_counter()
        #if text != original_text:
        #    logger.info(
        #        "TTS normalize_phone_sequences applied",
        #        original_snippet=original_text[:140],
        #        normalized_snippet=text[:140],
        #    )
        #logger.debug(
        #    "TTS normalize_phone_sequences timing",
        #    duration_ms=(t1 - t0) * 1000,
        #)

        #t2 = time.perf_counter()
        #text2 = normalize_numbers_to_words(text)
        t3 = time.perf_counter()
        #if text2 != text:
        #    logger.info(
        #        "TTS normalize_numbers_to_words applied",
        #        original_snippet=text[:140],
        #        normalized_snippet=text2[:140],
        #    )
        #logger.debug(
        #    "TTS normalize_numbers_to_words timing",
        #    duration_ms=(t3 - t2) * 1000,
        #)
        #text = text2

        text = original_text

        # Set LLM response text in observer (TTS text is the LLM response)
        if self._tts._observer:
            self._tts._observer.set_llm_response_text(text)
        
        # Log TTS call start with text
        session_id = getattr(self._tts._observer, 'session_id', 'unknown') if self._tts._observer else 'unknown'
        
        # Check if parallel TTS should be used
        use_parallel = (
            self._tts._parallel_enabled
            and len(text) >= self._tts._parallel_min_text_length
        )
        
        logger.info(
            "TTS call started",
            session_id=session_id,
            text=text,
            text_length=len(text),
            parallel=use_parallel,
        )

        try:
            t_api_start = time.perf_counter()
            
            if use_parallel:
                # Use parallel synthesis for long text
                pcm_data = await self._tts.synthesize_parallel(text, session_id)
                t_api_end = time.perf_counter()
                api_latency_ms = int((t_api_end - t_api_start) * 1000)
                logger.info(
                    "TTS call completed (parallel)",
                    session_id=session_id,
                    text_length=len(text),
                    latency_ms=api_latency_ms,
                )
            else:
                # Use sequential synthesis (existing logic)
                url = "https://texttospeech.googleapis.com/v1/text:synthesize"
                params = {"key": self._tts._api_key}
                payload = self._tts._create_tts_payload(text)
                session = self._tts._get_or_create_session()
                
                async with session.post(url, params=params, json=payload) as response:
                    t_api_end = time.perf_counter()
                    if response.status != 200:
                        error_text = await response.text()
                        logger.error(
                            "Google Cloud TTS error",
                            status_code=response.status,
                            error_text=error_text,
                        )
                        raise APIError(
                            f"Google Cloud TTS API error: {response.status} - {error_text}"
                        )

                    data = await response.json()
                    audio_b64 = data.get("audioContent")
                    if not audio_b64:
                        logger.error("Google Cloud TTS: no audioContent field in response")
                        raise APIError("Google Cloud TTS: no audioContent in response")

                    pcm_data = base64.b64decode(audio_b64)
                    api_latency_ms = int((t_api_end - t_api_start) * 1000)
                    logger.info(
                        "TTS call completed",
                        session_id=session_id,
                        text_length=len(text),
                        latency_ms=api_latency_ms,
                    )

            # Process audio to prevent clicks/pops at start and end
            # LINEAR16 is little-endian 16-bit signed integers
            num_samples = len(pcm_data) // 2
            if num_samples > 0:
                # Unpack 16-bit signed integers (little-endian)
                pcm_samples = list(struct.unpack(f'<{num_samples}h', pcm_data))
                
                # Step 1: Remove DC offset (constant bias that causes clicks)
                # Calculate average of first 100 samples for better DC estimation
                dc_calculation_samples = min(100, num_samples)
                if dc_calculation_samples > 0:
                    dc_offset = sum(pcm_samples[:dc_calculation_samples]) // dc_calculation_samples
                    if abs(dc_offset) > 5:  # Only remove if significant
                        # Clip samples to 16-bit signed integer range after DC removal
                        # to prevent overflow when packing back to bytes
                        pcm_samples = [
                            max(-32768, min(32767, s - dc_offset))
                            for s in pcm_samples
                        ]
                
                # Step 2: Apply exponential fade-in to prevent audio "click" at start
                # Fade-in over 100ms (1600 samples at 16kHz) - longer for smoother start
                fade_in_samples = min(1600, num_samples)  # 100ms at 16kHz
                if fade_in_samples > 0:
                    for i in range(fade_in_samples):
                        fade_factor = (i / fade_in_samples) ** 2
                        pcm_samples[i] = int(pcm_samples[i] * fade_factor)
                
                # Step 3: Apply fade-out to prevent audio "click" at end
                fade_out_samples = min(800, num_samples)
                if fade_out_samples > 0 and num_samples > fade_out_samples:
                    for i in range(fade_out_samples):
                        fade_factor = i / fade_out_samples
                        idx = num_samples - 1 - i
                        pcm_samples[idx] = int(pcm_samples[idx] * fade_factor)
                
                # Repack back to bytes
                pcm_data = struct.pack(f'<{len(pcm_samples)}h', *pcm_samples)

            # Push the audio in one go; LiveKit handles further chunking
            output_emitter.push(pcm_data)

        except APIError:
            # Already logged above; propagate to let LiveKit handle retries / errors
            raise
        except Exception as e:
            logger.error("Google Cloud TTS exception", error=str(e), error_type=type(e).__name__, exc_info=True)
            # Generic failure path; raise APIError so LiveKit treats it as a provider error
            raise APIError(f"Google Cloud TTS exception: {e}") from e

