"""Voice synthesis routes."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.voice.elevenlabs import elevenlabs_client

logger = get_logger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    voice_id: Optional[str] = None


@router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """Convert text to speech (ElevenLabs when configured)."""
    try:
        audio_data = await elevenlabs_client.text_to_speech(
            text=request.text,
            voice_id=request.voice_id,
        )
        if not audio_data:
            raise HTTPException(status_code=502, detail="TTS produced no audio")

        # Mock mode returns a silent WAV; real mode returns MP3 from ElevenLabs.
        return Response(
            content=audio_data,
            media_type=elevenlabs_client.audio_mime,
            headers={"Content-Disposition": "inline; filename=speech.audio"},
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error("tts_error", error=str(e))
        raise HTTPException(status_code=500, detail="Speech synthesis failed")


@router.get("/voices")
async def get_voices():
    """Get available voices."""
    try:
        voices = await elevenlabs_client.get_voices()
        return {"voices": voices, "engine": elevenlabs_client.engine}
    except Exception as e:  # noqa: BLE001
        logger.error("voices_error", error=str(e))
        return {"voices": [], "engine": "browser"}
