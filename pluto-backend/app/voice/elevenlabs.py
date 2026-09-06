"""ElevenLabs Text-to-Speech client with a mock/fallback mode.

In mock mode (no API key) TTS still returns a short valid WAV so endpoint
contracts hold, but the orchestrator marks the response as browser-TTS so the
frontend speaks via the browser's built-in speechSynthesis (always works).
"""
import io
import struct
import wave
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _silent_wav(duration_s: float = 0.35, rate: int = 16000) -> bytes:
    """Build a tiny valid WAV silently so mock TTS still returns audio bytes."""
    frames = int(rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


class ElevenLabsClient:
    """Client for ElevenLabs TTS."""

    def __init__(self) -> None:
        self.api_key = settings.elevenlabs_api_key
        self.voice_id = settings.elevenlabs_voice_id
        self.model_id = settings.elevenlabs_model_id
        self.base_url = settings.elevenlabs_base_url.rstrip("/")
        self.mock_mode = settings.pluto_tts_mock_mode
        self.client: Optional[httpx.AsyncClient] = None
        if not self.mock_mode:
            self.client = httpx.AsyncClient(
                headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
                timeout=60.0,
            )

    @property
    def engine(self) -> str:
        return "browser" if self.mock_mode else "elevenlabs"

    async def text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> bytes:
        """Convert text to speech. Returns audio bytes."""
        if self.mock_mode or not self.client:
            logger.info("elevenlabs_mock_tts", text_length=len(text))
            return _silent_wav()

        vid = voice_id or self.voice_id
        mid = model_id or self.model_id
        payload = {
            "text": text,
            "model_id": mid,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        }
        try:
            logger.info("elevenlabs_tts_request", text_length=len(text), voice=vid)
            response = await self.client.post(
                f"{self.base_url}/text-to-speech/{vid}", json=payload
            )
            response.raise_for_status()
            audio_data = response.content
            logger.info("elevenlabs_tts_success", audio_size=len(audio_data))
            return audio_data
        except httpx.HTTPError as e:
            logger.error("elevenlabs_tts_error", error=str(e))
            # Gracefully degrade to browser TTS on error.
            return _silent_wav()

    async def synthesize(self, text: str) -> tuple[bytes | None, str]:
        """Return (audio_bytes or None, engine_name). None means use browser TTS."""
        if self.mock_mode or not self.client:
            return None, "browser"
        try:
            audio = await self.text_to_speech(text)
            return audio, "elevenlabs"
        except Exception:
            return None, "browser"

    async def get_voices(self) -> list:
        if self.mock_mode or not self.client:
            return []
        try:
            response = await self.client.get(f"{self.base_url}/voices")
            response.raise_for_status()
            return response.json()["voices"]
        except Exception as e:
            logger.error("elevenlabs_voices_error", error=str(e))
            return []

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()


# Singleton instance
elevenlabs_client = ElevenLabsClient()
