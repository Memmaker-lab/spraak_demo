#!/usr/bin/env python3
"""
Test script to compare latency between REST and Streaming Google Cloud TTS.

Usage:
    python test_tts_latency.py

Requirements:
    - GOOGLE_APPLICATION_CREDENTIALS set for streaming
    - GOOGLE_TTS_API_KEY set for REST API
"""
import asyncio
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment
env_path = Path(__file__).parent / ".env_local"
load_dotenv(env_path)

# Test texts of varying lengths
TEST_TEXTS = {
    "short": "Hallo, hoe gaat het?",
    "medium": "Goedemorgen! Ik help je graag met je vraag. Wat kan ik voor je doen vandaag?",
    "long": "Welkom bij onze klantenservice. We zijn bereikbaar van maandag tot vrijdag tussen negen uur 's ochtends en vijf uur 's middags. Heeft u vragen over uw bestelling, levering, of producten? Ik help u graag verder met alle informatie die u nodig heeft.",
}


async def test_rest_tts():
    """Test REST API TTS latency."""
    from voice_pipeline.google_cloud_tts import GoogleCloudTTS
    
    api_key = os.getenv("GOOGLE_TTS_API_KEY")
    if not api_key:
        print("⚠️  GOOGLE_TTS_API_KEY not set, skipping REST API test")
        return None
    
    voice = os.getenv("GOOGLE_TTS_VOICE", "nl-NL-Chirp3-HD-Aoede")
    tts = GoogleCloudTTS(api_key=api_key, voice=voice)
    
    results = {}
    
    for name, text in TEST_TEXTS.items():
        print(f"\n📝 Testing REST API with {name} text ({len(text)} chars)...")
        
        t_start = time.perf_counter()
        stream = tts.synthesize(text)
        
        # Collect all audio chunks
        chunks = []
        t_first_chunk = None
        
        async for audio in stream:
            # First time we get audio
            if t_first_chunk is None:
                t_first_chunk = time.perf_counter()
            # SynthesizedAudio has frame attribute
            chunks.append(audio.frame.data)
        
        t_end = time.perf_counter()
        
        time_to_first_audio = int((t_first_chunk - t_start) * 1000) if t_first_chunk else None
        total_latency = int((t_end - t_start) * 1000)
        total_audio_bytes = sum(len(c) for c in chunks)
        
        results[name] = {
            "time_to_first_audio_ms": time_to_first_audio,
            "total_latency_ms": total_latency,
            "audio_bytes": total_audio_bytes,
            "chunks": len(chunks),
        }
        
        print(f"   ⏱️  Time to first audio: {time_to_first_audio}ms")
        print(f"   ⏱️  Total latency: {total_latency}ms")
        print(f"   📦 Audio bytes: {total_audio_bytes}")
        print(f"   📦 Chunks: {len(chunks)}")
    
    # Clean up
    await tts.aclose()
    
    return results


async def test_streaming_tts():
    """Test streaming TTS latency."""
    from voice_pipeline.google_cloud_tts_streaming import GoogleCloudStreamingTTS
    
    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds:
        print("⚠️  GOOGLE_APPLICATION_CREDENTIALS not set, skipping streaming test")
        return None
    
    if not Path(creds).exists():
        print(f"⚠️  Credentials file not found at: {creds}")
        return None
    
    voice = os.getenv("GOOGLE_TTS_VOICE", "nl-NL-Chirp3-HD-Aoede")
    
    try:
        tts = GoogleCloudStreamingTTS(voice=voice)
    except Exception as e:
        print(f"⚠️  Failed to initialize streaming TTS: {e}")
        return None
    
    results = {}
    
    for name, text in TEST_TEXTS.items():
        print(f"\n📝 Testing Streaming with {name} text ({len(text)} chars)...")
        
        t_start = time.perf_counter()
        stream = tts.synthesize(text)
        
        # Collect all audio chunks
        chunks = []
        t_first_chunk = None
        
        async for audio in stream:
            # First time we get audio
            if t_first_chunk is None:
                t_first_chunk = time.perf_counter()
            # SynthesizedAudio has frame attribute
            chunks.append(audio.frame.data)
        
        t_end = time.perf_counter()
        
        time_to_first_audio = int((t_first_chunk - t_start) * 1000) if t_first_chunk else None
        total_latency = int((t_end - t_start) * 1000)
        total_audio_bytes = sum(len(c) for c in chunks)
        
        results[name] = {
            "time_to_first_audio_ms": time_to_first_audio,
            "total_latency_ms": total_latency,
            "audio_bytes": total_audio_bytes,
            "chunks": len(chunks),
        }
        
        print(f"   ⏱️  Time to first audio: {time_to_first_audio}ms")
        print(f"   ⏱️  Total latency: {total_latency}ms")
        print(f"   📦 Audio bytes: {total_audio_bytes}")
        print(f"   📦 Chunks: {len(chunks)}")
    
    return results


def print_comparison(rest_results, streaming_results):
    """Print comparison table."""
    if not rest_results or not streaming_results:
        print("\n⚠️  Cannot compare - missing results from one or both implementations")
        return
    
    print("\n" + "="*80)
    print("📊 LATENCY COMPARISON")
    print("="*80)
    
    for name in TEST_TEXTS.keys():
        rest = rest_results.get(name, {})
        stream = streaming_results.get(name, {})
        
        if not rest or not stream:
            continue
        
        print(f"\n{name.upper()} text ({len(TEST_TEXTS[name])} chars):")
        print("-" * 80)
        
        # Time to first audio
        rest_ttfa = rest.get("time_to_first_audio_ms", 0)
        stream_ttfa = stream.get("time_to_first_audio_ms", 0)
        improvement_ttfa = ((rest_ttfa - stream_ttfa) / rest_ttfa * 100) if rest_ttfa > 0 else 0
        
        print(f"Time to First Audio:")
        print(f"  REST:      {rest_ttfa:4d}ms")
        print(f"  Streaming: {stream_ttfa:4d}ms")
        print(f"  → {improvement_ttfa:+.1f}% {'🚀' if improvement_ttfa > 0 else '⚠️'}")
        
        # Total latency
        rest_total = rest.get("total_latency_ms", 0)
        stream_total = stream.get("total_latency_ms", 0)
        improvement_total = ((rest_total - stream_total) / rest_total * 100) if rest_total > 0 else 0
        
        print(f"\nTotal Latency:")
        print(f"  REST:      {rest_total:4d}ms")
        print(f"  Streaming: {stream_total:4d}ms")
        print(f"  → {improvement_total:+.1f}% {'🚀' if improvement_total > 0 else '⚠️'}")
    
    print("\n" + "="*80)


async def main():
    print("🧪 Google Cloud TTS Latency Comparison Test")
    print("="*80)
    
    # Test REST API
    print("\n🔵 Testing REST API TTS...")
    rest_results = await test_rest_tts()
    
    # Test Streaming
    print("\n🟢 Testing Streaming TTS...")
    streaming_results = await test_streaming_tts()
    
    # Compare
    print_comparison(rest_results, streaming_results)
    
    print("\n✅ Test completed!")


if __name__ == "__main__":
    asyncio.run(main())
