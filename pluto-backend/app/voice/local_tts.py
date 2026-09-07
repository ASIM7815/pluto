"""Local, fully-offline TTS for PLUTO (no external AI/API).

Engine preference (first available wins):
1. ``espeak-ng``   - system binary, fully offline, emits WAV. (Linux)
2. ``pyttsx3``     - offline Python TTS (uses installed voices). (cross-platform)
3. ``gTTS``        - free Google TTS, *requires* network (last resort fallback).

If none is available the frontend uses the browser's ``speechSynthesis`` (also
offline on most platforms). PLUTO never pretends a fallback was synthesised.
"""

from __future__ import annotations

import asyncio
import io
import os
import shutil
import subprocess
import tempfile
from typing import Optional

from app.core.logging import get_logger

logger = get_logger(__name__)


def _espeak_available() -> bool:
    return shutil.which("espeak-ng") is not None or shutil.which("espeak") is not None


def _pyttsx3_available() -> bool:
    try:
        import pyttsx3  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


def _gtts_available() -> bool:
    try:
        import gtts  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


class LocalTTSClient:
    """Text-to-speech using the best available *local* engine."""

    def __init__(self) -> None:
        self.espeak = _espeak_available()
        self.pyttsx3 = _pyttsx3_available()
        self.gtts = _gtts_available()
        self._preferred = self._pick_preferred()
        logger.info(
            "local_tts_initialized",
            espeak=self.espeak, pyttsx3=self.pyttsx3, gtts=self.gtts,
            preferred=self._preferred,
        )

    def _pick_preferred(self) -> str:
        if self.espeak:
            return "espeak"
        if self.pyttsx3:
            return "pyttsx3"
        if self.gtts:
            return "gtts"
        return "none"

    def _prefer_offline_first(self) -> bool:
        """True when a truly offline engine exists (no network needed)."""
        return self.espeak or self.pyttsx3

    def can_use(self) -> bool:
        return self._preferred != "none"

    async def text_to_speech(self, text: str) -> bytes:
        """Return audio bytes (WAV/MP3) or ``b""`` when nothing can be done.

        The engine actually used is chosen offline-first: espeak-ng / pyttsx3
        produce audio without any network; gTTS is only the last resort.
        """
        if not text or not text.strip():
            return b""
        if self.espeak:
            audio = await self._espeak_synthesize(text)
            if audio:
                return audio
        if self.pyttsx3:
            audio = await self._pyttsx3_synthesize(text)
            if audio:
                return audio
        if self.gtts:
            audio = await self._gtts_synthesize(text)
            if audio:
                return audio
        logger.warning("local_tts_unavailable")
        return b""

    async def _espeak_synthesize(self, text: str) -> bytes:
        binary = "espeak-ng" if shutil.which("espeak-ng") else "espeak"
        try:
            def _run() -> bytes:
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    out = tmp.name
                try:
                    proc = subprocess.run(
                        [binary, "-v", "en", "-s", "150", "-w", out, text],
                        capture_output=True, timeout=30,
                    )
                    if proc.returncode != 0 or not os.path.isfile(out):
                        return b""
                    with open(out, "rb") as fh:
                        return fh.read()
                finally:
                    try:
                        os.unlink(out)
                    except OSError:
                        pass

            audio = await asyncio.to_thread(_run)
            if audio:
                logger.info("local_tts_success", engine="espeak", audio_size=len(audio))
            return audio
        except Exception as e:  # noqa: BLE001
            logger.error("local_tts_espeak_error", error=str(e))
            return b""

    async def _pyttsx3_synthesize(self, text: str) -> bytes:
        try:
            def _run() -> bytes:
                import pyttsx3

                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    out = tmp.name
                try:
                    engine = pyttsx3.init()
                    engine.save_to_file(text, out)
                    engine.runAndWait()
                    with open(out, "rb") as fh:
                        return fh.read()
                finally:
                    try:
                        os.unlink(out)
                    except OSError:
                        pass

            audio = await asyncio.to_thread(_run)
            if audio:
                logger.info("local_tts_success", engine="pyttsx3", audio_size=len(audio))
            return audio
        except Exception as e:  # noqa: BLE001
            logger.error("local_tts_pyttsx3_error", error=str(e))
            return b""

    async def _gtts_synthesize(self, text: str) -> bytes:
        try:
            from gtts import gTTS

            def _run() -> bytes:
                tts = gTTS(text=text, lang="en", slow=False)
                buffer = io.BytesIO()
                tts.write_to_fp(buffer)
                buffer.seek(0)
                return buffer.read()

            audio = await asyncio.to_thread(_run)
            if audio:
                logger.info("local_tts_success", engine="gtts", audio_size=len(audio))
            return audio
        except Exception as e:  # noqa: BLE001
            logger.error("local_tts_gtts_error", error=str(e))
            return b""


# Singleton instance
local_tts_client = LocalTTSClient()
