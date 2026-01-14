#!/usr/bin/env python3
import os
from pathlib import Path
from dotenv import load_dotenv
from google.cloud import texttospeech

# Load .env_local
env_path = Path(__file__).parent / ".env_local"
load_dotenv(env_path)

def test_connection():
    # Check if credentials are set
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    print(f"📋 Credentials path: {creds_path}")
    
    if not creds_path:
        print("❌ GOOGLE_APPLICATION_CREDENTIALS not found in environment")
        return False
    
    if not Path(creds_path).exists():
        print(f"❌ Credentials file not found at: {creds_path}")
        return False
    
    print("✅ Credentials file exists")
    
    try:
        client = texttospeech.TextToSpeechClient()
        print("✅ Google Cloud TTS client succesvol aangemaakt!")
        
        # List voices to verify API access
        voices = client.list_voices(language_code="nl-NL")
        print(f"✅ API toegang werkt! Gevonden: {len(voices.voices)} Nederlandse stemmen")
        
        # Check if Chirp3-HD voices are available
        chirp_voices = [v.name for v in voices.voices if "Chirp3-HD" in v.name]
        print(f"✅ Chirp3-HD stemmen beschikbaar: {len(chirp_voices)}")
        for voice in chirp_voices[:5]:  # Show first 5
            print(f"   - {voice}")
        
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_connection()
    if success:
        print("\n🎉 Alles werkt! Klaar voor streaming implementation.")
    else:
        print("\n⚠️  Er ging iets mis. Check de error message hierboven.")