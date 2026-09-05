"""Voice synthesis routes"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from app.voice.elevenlabs import elevenlabs_client
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])


class TTSRequest(BaseModel):
    text: str
    voice_id: str = None


@router.post("/synthesize")
async def synthesize_speech(request: TTSRequest):
    """Convert text to speech"""
    try:
        audio_data = await elevenlabs_client.text_to_speech(
            text=request.text,
            voice_id=request.voice_id
        )
        
        return Response(
            content=audio_data,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline; filename=speech.mp3"
            }
        )
        
    except Exception as e:
        logger.error("tts_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voices")
async def get_voices():
    """Get available voices"""
    try:
        voices = await elevenlabs_client.get_voices()
        return {"voices": voices}
    except Exception as e:
        logger.error("voices_error", error=str(e))
        return {"voices": []}
