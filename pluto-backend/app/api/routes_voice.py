"""Voice synthesis & recognition routes."""
from typing import Optional

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.voice.local_tts import local_tts_client
from app.voice.stt import stt_client

logger = get_logger(__name__)


def _locale_audio_mime() -> str:
    """Best guess of the audio MIME our offline TTS emitted (WAV or MP3)."""
    import shutil

    if shutil.which("espeak-ng") or shutil.which("espeak"):
        return "audio/wav"
    return "audio/mpeg"

router = APIRouter(prefix="/api/voice", tags=["voice"])


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voice_id: Optional[str] = None


@router.get("/stt-status")
async def stt_status():
    """Which server-side speech-to-text engines are available."""
    return stt_client.engine_status()


@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...), language: Optional[str] = None
):
    """Transcribe a recorded audio clip (browser fallback STT).

    Returns 503 with an actionable hint when no engine is installed - the
    frontend then keeps using the browser's Web Speech API instead.
    """
    if stt_client.mock_mode:
        status = stt_client.engine_status()
        raise HTTPException(status_code=503, detail=str(status.get("hint", "")))
    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio upload")
        text, engine = await stt_client.transcribe(audio_bytes, language)
        if not text:
            return {"text": "", "engine": engine, "heard_speech": False}
        logger.info("stt_transcribed", engine=engine, chars=len(text))
        return {"text": text, "engine": engine, "heard_speech": True}
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("stt_route_error", error=str(e))
        raise HTTPException(status_code=500, detail="Transcription failed")


@router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """Convert text to speech using a *fully local* engine.

    PLUTO never relies on an external AI/API for speech. Engine preference is
    offline-first: espeak-ng or pyttsx3 (no network), then gTTS (network,
    last resort). When no engine produced audio we return 502 so the
    frontend falls back to the browser's own speechSynthesis.
    """
    try:
        audio_data = await local_tts_client.text_to_speech(text=request.text)
        if audio_data:
            return Response(
                content=audio_data,
                media_type=_locale_audio_mime(),
                headers={"Content-Disposition": "inline; filename=speech.audio"},
            )
        # No local engine usable -> let the browser speak instead.
        raise HTTPException(status_code=502, detail="No local TTS engine available")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("tts_error", error=str(e))
        raise HTTPException(status_code=500, detail="Speech synthesis failed")


@router.get("/voices")
async def get_voices():
    """Report the local TTS voices/engines available (PLUTO never uses external APIs)."""
    engines = []
    if local_tts_client.espeak:
        engines.append({"id": "espeak", "name": "espeak-ng (offline)"})
    if local_tts_client.pyttsx3:
        engines.append({"id": "pyttsx3", "name": "pyttsx3 (offline)"})
    if local_tts_client.gtts:
        engines.append({"id": "gtts", "name": "gTTS (network fallback)"})
    return {
        "voices": [],
        "engines": engines,
        "preferred": local_tts_client._preferred,
        "engine": "local",
    }
