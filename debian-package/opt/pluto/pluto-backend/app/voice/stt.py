"""Speech-to-text with graceful degradation.

PLUTO's primary STT is the browser's Web Speech API (accurate, free). When
that is unavailable or errors out, the frontend records a clip with
MediaRecorder and POSTs it to ``/api/voice/transcribe``. This module serves
those requests using the best engine installed locally:

    1. faster-whisper  (fully local, offline)   - pip install faster-whisper
    2. SpeechRecognition + Google Web Speech    - pip install SpeechRecognition
       (needs internet; ffmpeg converts webm/ogg to WAV first)

If neither is installed the endpoint reports ``available: false`` with an
install hint instead of pretending to transcribe - PLUTO never fabricates a
transcript.
"""
from __future__ import annotations

import asyncio
import io
import shutil
import subprocess
import wave
from typing import Dict, List, Optional, Tuple

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# MediaRecorder payloads we may receive from browsers.
_WEBM_MAGIC = b"\x1a\x45\xdf\xa3"  # EBML header (webm/matroska)
_OGG_MAGIC = b"OggS"


def _sniff_format(data: bytes) -> str:
    if data[:4] == _WEBM_MAGIC:
        return "webm"
    if data[:4] == _OGG_MAGIC:
        return "ogg"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE":
        return "wav"
    if data[:3] == b"ID3" or data[:2] == b"\xff\xfb":
        return "mp3"
    return "unknown"


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _convert_to_wav(data: bytes, source_format: str) -> Optional[bytes]:
    """Convert compressed browser audio to 16 kHz mono WAV via ffmpeg."""
    if not _ffmpeg_available():
        return None
    try:
        proc = subprocess.run(
            [
                "ffmpeg", "-hide_banner", "-loglevel", "error",
                "-f", source_format if source_format != "unknown" else "webm",
                "-i", "pipe:0",
                "-ac", "1", "-ar", "16000", "-f", "wav", "pipe:1",
            ],
            input=data,
            capture_output=True,
            timeout=30,
        )
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout
        logger.error("stt_ffmpeg_error", stderr=proc.stderr.decode()[:200])
        return None
    except Exception as e:  # noqa: BLE001
        logger.error("stt_ffmpeg_failed", error=str(e))
        return None


class STTClient:
    """Speech-to-text client with multiple optional backends."""

    def __init__(self) -> None:
        self.language = settings.pluto_stt_language
        self._whisper_model = None
        self._whisper_failed = False

    # -- engine discovery ---------------------------------------------------
    @staticmethod
    def _faster_whisper_available() -> bool:
        try:
            import faster_whisper  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _speechrecognition_available() -> bool:
        try:
            import speech_recognition  # noqa: F401
            return True
        except Exception:  # noqa: BLE001
            return False

    def engine_status(self) -> Dict[str, object]:
        """Which engines are usable right now (for /api/voice/stt-status)."""
        engines: List[Dict[str, object]] = []
        if self._faster_whisper_available():
            engines.append({"engine": "faster-whisper", "local": True})
        if self._speechrecognition_available():
            engines.append({"engine": "google-web-speech", "local": False})
        return {
            "available": len(engines) > 0,
            "engines": engines,
            "ffmpeg": _ffmpeg_available(),
            "hint": (
                "Server-side STT is available."
                if engines
                else "No server STT engine installed. pip install faster-whisper "
                "(offline) or SpeechRecognition (online), plus ffmpeg for audio "
                "conversion. The browser Web Speech API still works without these."
            ),
        }

    @property
    def mock_mode(self) -> bool:
        return not (self._faster_whisper_available() or self._speechrecognition_available())

    # -- transcription --------------------------------------------------------
    async def transcribe(self, audio_bytes: bytes, lang: Optional[str] = None) -> Tuple[str, str]:
        """Return (text, engine). text == "" means nothing could be transcribed."""
        if not audio_bytes:
            return "", "none"
        language = lang or self.language

        fmt = _sniff_format(audio_bytes)
        wav_bytes: Optional[bytes] = audio_bytes if fmt == "wav" else _convert_to_wav(audio_bytes, fmt)

        if wav_bytes:
            # Local whisper: fully offline, best quality.
            text = await self._transcribe_whisper(wav_bytes, language)
            if text:
                return text, "faster-whisper"
            # Google Web Speech through SpeechRecognition (needs internet).
            text = await self._transcribe_google(wav_bytes, language)
            if text:
                return text, "google-web-speech"

        logger.warning(
            "stt_unavailable",
            format=fmt,
            ffmpeg=_ffmpeg_available(),
            faster_whisper=self._faster_whisper_available(),
            speech_recognition=self._speechrecognition_available(),
        )
        return "", "none"

    # -- engines ---------------------------------------------------------------
    async def _transcribe_whisper(self, wav_bytes: bytes, language: str) -> str:
        if not self._faster_whisper_available() or self._whisper_failed:
            return ""
        try:
            def _run() -> str:
                if self._whisper_model is None:
                    from faster_whisper import WhisperModel

                    # "small" balances speed/accuracy; falls back to CPU int8.
                    self._whisper_model = WhisperModel("small", device="auto", compute_type="auto")
                segments, _info = self._whisper_model.transcribe(
                    io.BytesIO(wav_bytes), language=None if language == "auto" else language[:2]
                )
                return " ".join(s.text.strip() for s in segments).strip()

            return await asyncio.to_thread(_run)
        except Exception as e:  # noqa: BLE001
            logger.error("stt_whisper_error", error=str(e)[:300])
            self._whisper_failed = True  # don't retry a broken model all day
            return ""

    async def _transcribe_google(self, wav_bytes: bytes, language: str) -> str:
        if not self._speechrecognition_available():
            return ""
        try:
            def _run() -> str:
                import speech_recognition as sr

                # Trim to a proper WAV header (ffmpeg output is already fine,
                # but be defensive about containers SpeechRecognition rejects).
                with io.BytesIO(wav_bytes) as raw:
                    with wave.open(raw, "rb") as w:
                        frames = w.getnframes()
                        audio = sr.AudioData(w.readframes(frames), w.getframerate(), w.getsampwidth())
                rec = sr.Recognizer()
                try:
                    return rec.recognize_google(audio, language=language)
                except sr.UnknownValueError:
                    return ""  # real silence / unintelligible speech
                except sr.RequestError as e:
                    logger.error("stt_google_request_error", error=str(e)[:200])
                    return ""

            return await asyncio.to_thread(_run)
        except Exception as e:  # noqa: BLE001
            logger.error("stt_google_error", error=str(e)[:300])
            return ""

    async def close(self) -> None:  # pragma: no cover - nothing persistent
        return None


def feature_available() -> bool:
    """Whether a server-side STT engine is available."""
    return not stt_client.mock_mode


stt_client = STTClient()
