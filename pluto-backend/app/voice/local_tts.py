"""Local offline TTS (gTTS - free Google Text-to-Speech).

gTTS is OPTIONAL: it is imported lazily so PLUTO runs fine without it. When it
is installed and network to Google Translate is available, responses are
synthesised offline-of-PLUTO (still uses Google's public endpoint) and sent as
MP3 bytes with engine tag "local_tts". Otherwise the frontend uses its browser
speech synthesis.
"""
from __future__ import annotations

import io
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


def _gtts_available() -> bool:
    try:
        import gtts  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


class LocalTTSClient:
    """Free text-to-speech using gTTS (lazy dependency)."""

    def __init__(self) -> None:
        self._available = _gtts_available()
        logger.info("local_tts_initialized", engine="gTTS", available=self._available)

    def can_use(self) -> bool:
        return self._available

    async def text_to_speech(self, text: str) -> bytes:
        """Return MP3 bytes, or b"" when gTTS is unavailable / fails."""
        if not text or not text.strip():
            return b""
        if not self._available:
            logger.warning("local_tts_not_available")
            return b""
        try:
            from gtts import gTTS  # lazy import
            logger.info("local_tts_request", text_length=len(text))
            tts = gTTS(text=text, lang="en", slow=False)
            buffer = io.BytesIO()
            tts.write_to_fp(buffer)
            buffer.seek(0)
            audio = buffer.read()
            logger.info("local_tts_success", audio_size=len(audio))
            return audio
        except Exception as e:  # noqa: BLE001
            logger.error("local_tts_error", error=str(e))
            return b""


# Singleton instance
local_tts_client = LocalTTSClient()
