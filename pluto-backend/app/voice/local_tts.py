"""Local offline TTS using gTTS - completely free Google Text-to-Speech"""
import io
import tempfile
from pathlib import Path
from gtts import gTTS
from app.core.logging import get_logger

logger = get_logger(__name__)


class LocalTTSClient:
    """Free text-to-speech using Google TTS"""
    
    def __init__(self):
        logger.info("local_tts_initialized", engine="gTTS")
    
    async def text_to_speech(self, text: str) -> bytes:
        """
        Convert text to speech and return audio bytes
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Audio data as bytes (MP3 format)
        """
        try:
            if not text or not text.strip():
                logger.warning("tts_empty_text")
                return b""
            
            logger.info("local_tts_request", text_length=len(text))
            
            # Create gTTS object with female voice (using 'en' for English)
            # gTTS uses Google's natural-sounding voices
            tts = gTTS(text=text, lang='en', slow=False)
            
            # Save to bytes buffer
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            audio_data = audio_buffer.read()
            
            logger.info("local_tts_success", audio_size=len(audio_data))
            
            return audio_data
                    
        except Exception as e:
            logger.error("local_tts_error", error=str(e))
            return b""


# Singleton instance
local_tts_client = LocalTTSClient()
