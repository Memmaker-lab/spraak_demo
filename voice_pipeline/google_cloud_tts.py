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
from typing import Optional

import aiohttp
from livekit.agents import tts as tts_module
from livekit.agents._exceptions import APIError
from livekit.agents.types import APIConnectOptions, DEFAULT_API_CONNECT_OPTIONS
from livekit.agents.utils import log_exceptions, shortuuid

from logging_setup import get_logger, Component

logger = get_logger(Component.VOICE_PIPELINE)


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

        url = "https://texttospeech.googleapis.com/v1/text:synthesize"
        params = {"key": self._tts._api_key}

        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": "nl-NL",
                "name": self._tts._voice or "nl-NL-Chirp3-HD-Algenib",
            },
            "audioConfig": {
                "audioEncoding": "LINEAR16",
                "sampleRateHertz": self._tts._sample_rate,
            },
        }

        # Set LLM response text in observer (TTS text is the LLM response)
        if self._tts._observer:
            self._tts._observer.set_llm_response_text(text)
        
        # Log TTS call start with text
        session_id = getattr(self._tts._observer, 'session_id', 'unknown') if self._tts._observer else 'unknown'
        logger.info(
            "TTS call started",
            session_id=session_id,
            text=text,
            text_length=len(text),
        )

        try:
            t_api_start = time.perf_counter()
            
            # Use shared session with connection pooling
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
                    session_id = getattr(self._tts._observer, 'session_id', 'unknown') if self._tts._observer else 'unknown'
                    logger.info(
                        "TTS call completed",
                        session_id=session_id,

                        text=text,
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
                                #logger.debug(
                                #    "Removed DC offset",
                                #    dc_offset=dc_offset,
                                #    samples_analyzed=dc_calculation_samples,
                                #)
                        
                        # Step 2: Apply exponential fade-in to prevent audio "click" at start
                        # Fade-in over 100ms (1600 samples at 16kHz) - longer for smoother start
                        # Exponential curve for more natural sound
                        fade_in_samples = min(1600, num_samples)  # 100ms at 16kHz
                        if fade_in_samples > 0:
                            # Apply exponential fade-in (x^2 curve) for smoother start
                            for i in range(fade_in_samples):
                                # Exponential curve: (i/fade_in_samples)^2
                                # This gives a gentler start than linear
                                fade_factor = (i / fade_in_samples) ** 2
                                pcm_samples[i] = int(pcm_samples[i] * fade_factor)
                            #logger.debug(
                            #    "Applied exponential fade-in to prevent audio click",
                            #    fade_samples=fade_in_samples,
                            #    fade_duration_ms=(fade_in_samples / 16000) * 1000,
                            #)
                        
                        # Step 3: Apply fade-out to prevent audio "click" at end
                        # Fade-out over 50ms (800 samples at 16kHz) - same as fade-in
                        fade_out_samples = min(800, num_samples)
                        if fade_out_samples > 0 and num_samples > fade_out_samples:
                            # Apply linear fade-out to last samples
                            for i in range(fade_out_samples):
                                fade_factor = i / fade_out_samples
                                idx = num_samples - 1 - i
                                pcm_samples[idx] = int(pcm_samples[idx] * fade_factor)
                            #logger.debug(
                            #    "Applied fade-out to prevent audio click",
                            #    fade_samples=fade_out_samples,
                            #    fade_duration_ms=(fade_out_samples / 16000) * 1000,
                            #)
                        
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

