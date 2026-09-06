"""Speech-to-text stub.

In most setups STT runs on the client (Web Speech API in the browser) and the
frontend sends the already-transcribed text. This module exposes an optional
server-side endpoint so the backend *can* transcribe raw audio (e.g. Whisper)
if a model is installed later. In mock mode it returns an empty result.
"""
from typing import Optional

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class STTClient:
    """Speech-to-text client (Whisper-ready)."""

    def __init__(self) -> None:
        # When using a real STT (e.g. faster-whisper), set model path here.
        self.mock_mode = True

    async def transcribe(self, audio_bytes: bytes, lang: Optional[str] = None) -> str:
        # Placeholder: returns empty in mock mode. Real impl would be added here.
        logger.info("stt_transcribe", audio_size=len(audio_bytes))
        return ""

    async def close(self) -> None:  # pragma: no cover - no resources yet
        return None


def feature_available() -> bool:
    """Whether a server-side STT engine is available."""
    return False


stt_client = STTClient()
