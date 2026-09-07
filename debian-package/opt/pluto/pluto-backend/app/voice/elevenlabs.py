"""ElevenLabs Text-to-Speech client.

- Real mode (ELEVENLABS_API_KEY set): requests ElevenLabs' TTS API.
- Mock mode (no key): synthesize() returns (None, "browser") so the frontend
  falls back to the browser's built-in speechSynthesis; PLUTO still "speaks"
  but never pretends real ElevenLabs audio was produced.
"""
from __future__ import annotations

import io
import wave
from typing import List, Optional, Tuple

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _silent_wav(duration_s: float = 0.4, rate: int = 16000) -> bytes:
    """A tiny valid WAV used only by the /synthesize REST mock contract."""
    frames = int(rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * frames)
    return buf.getvalue()


class ElevenLabsClient:
    """Client for the ElevenLabs TTS API."""

    def __init__(self) -> None:
        self.api_key = settings.elevenlabs_api_key
        self.voice_id = settings.elevenlabs_voice_id
        self.model_id = settings.elevenlabs_model_id
        self.base_url = settings.elevenlabs_base_url.rstrip("/")
        self.mock_mode = settings.pluto_tts_mock_mode
        self.client: Optional[httpx.AsyncClient] = None
        if not self.mock_mode:
            if not self.api_key:
                logger.warning("tts_key_missing_falling_back_to_mock")
                self.mock_mode = True
            else:
                self.client = httpx.AsyncClient(
                    headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
                    timeout=60.0,
                )

    @property
    def engine(self) -> str:
        return "browser" if self.mock_mode else "elevenlabs"

    @property
    def audio_mime(self) -> str:
        return "audio/wav" if self.mock_mode else "audio/mpeg"

    async def synthesize(self, text: str) -> Tuple[Optional[bytes], str]:
        """Return (audio_bytes, engine). None audio means "use browser TTS"."""
        if self.mock_mode or not self.client:
            return None, "browser"
        try:
            audio = await self.text_to_speech(text)
            if audio:
                return audio, "elevenlabs"
            return None, "browser"
        except Exception as e:  # noqa: BLE001
            logger.error("elevenlabs_synthesis_error", error=str(e))
            return None, "browser"

    async def text_to_speech(
        self,
        text: str,
        voice_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> bytes:
        """Real TTS request. Raises on failure in real mode.

        In mock mode returns a tiny silent WAV so REST contract stays intact.
        """
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
        logger.info("elevenlabs_tts_request", text_length=len(text), voice=vid)
        response = await self.client.post(f"{self.base_url}/text-to-speech/{vid}", json=payload)
        response.raise_for_status()
        audio_data = response.content
        logger.info("elevenlabs_tts_success", audio_size=len(audio_data))
        return audio_data

    async def get_voices(self) -> List[dict]:
        if self.mock_mode or not self.client:
            return []
        try:
            response = await self.client.get(f"{self.base_url}/voices")
            response.raise_for_status()
            return response.json().get("voices", [])
        except Exception as e:  # noqa: BLE001
            logger.error("elevenlabs_voices_error", error=str(e))
            return []

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()
            self.client = None


# Singleton instance
elevenlabs_client = ElevenLabsClient()
