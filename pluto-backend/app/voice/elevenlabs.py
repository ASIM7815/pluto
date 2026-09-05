"""ElevenLabs Voice API Client"""
import httpx
from typing import AsyncGenerator, Optional
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class ElevenLabsClient:
    """Client for ElevenLabs Text-to-Speech API"""
    
    def __init__(self):
        self.api_key = settings.elevenlabs_api_key
        self.voice_id = settings.elevenlabs_voice_id
        self.model_id = settings.elevenlabs_model_id
        self.base_url = "https://api.elevenlabs.io/v1"
        
        self.client = httpx.AsyncClient(
            headers={
                "xi-api-key": self.api_key,
                "Content-Type": "application/json"
            },
            timeout=60.0
        )
    
    async def text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> bytes:
        """
        Convert text to speech
        
        Args:
            text: Text to synthesize
            voice_id: Optional voice ID override
            model_id: Optional model ID override
            
        Returns:
            Audio bytes (MP3 format)
        """
        vid = voice_id or self.voice_id
        mid = model_id or self.model_id
        
        try:
            logger.info("elevenlabs_tts_request", text_length=len(text), voice=vid)
            
            payload = {
                "text": text,
                "model_id": mid,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True
                }
            }
            
            response = await self.client.post(
                f"{self.base_url}/text-to-speech/{vid}",
                json=payload
            )
            response.raise_for_status()
            
            audio_data = response.content
            logger.info("elevenlabs_tts_success", audio_size=len(audio_data))
            
            return audio_data
            
        except httpx.HTTPError as e:
            logger.error("elevenlabs_error", error=str(e))
            raise Exception(f"ElevenLabs API error: {str(e)}")
    
    async def text_to_speech_stream(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream text-to-speech audio (for future streaming support)
        
        Args:
            text: Text to synthesize
            voice_id: Optional voice ID override
            model_id: Optional model ID override
            
        Yields:
            Audio chunk bytes
        """
        vid = voice_id or self.voice_id
        mid = model_id or self.model_id
        
        try:
            payload = {
                "text": text,
                "model_id": mid,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75
                }
            }
            
            async with self.client.stream(
                "POST",
                f"{self.base_url}/text-to-speech/{vid}/stream",
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    yield chunk
                    
        except httpx.HTTPError as e:
            logger.error("elevenlabs_stream_error", error=str(e))
            raise Exception(f"ElevenLabs streaming error: {str(e)}")
    
    async def get_voices(self) -> list:
        """Get available voices"""
        try:
            response = await self.client.get(f"{self.base_url}/voices")
            response.raise_for_status()
            return response.json()["voices"]
        except Exception as e:
            logger.error("elevenlabs_voices_error", error=str(e))
            return []
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Singleton instance
elevenlabs_client = ElevenLabsClient()
