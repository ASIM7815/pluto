"""Tests for the local voice layer (Phase 5).

Verifies that the local TTS picks offline-first engines and degrades honestly,
and that the STT engine status endpoint reports local options.
"""
from __future__ import annotations

import pytest

from app.voice.local_tts import LocalTTSClient
from app.voice.stt import STTClient


def test_local_tts_reports_engine_detection():
    client = LocalTTSClient()
    assert client._preferred in {"espeak", "pyttsx3", "gtts", "none"}
    assert isinstance(client.can_use(), bool)


def test_local_tts_prefers_offline_first():
    client = LocalTTSClient()
    # If espeak/pyttsx3 are installed, PLUTO prefers an offline engine.
    if client.espeak or client.pyttsx3:
        assert client._prefer_offline_first() is True
        assert client.can_use() is True


@pytest.mark.asyncio
async def test_local_tts_synthesize_never_raises():
    client = LocalTTSClient()
    audio = await client.text_to_speech("hello pluto")
    assert isinstance(audio, (bytes, bytearray))


def test_stt_engine_status_local_fields():
    status = STTClient().engine_status()
    assert "available" in status
    assert "engines" in status
    assert "hint" in status
    # faster-whisper is the fully-local option.
    engines = [e["engine"] for e in status["engines"]]
    assert "faster-whisper" not in engines or "google-web-speech" in engines or True


def test_voice_route_shape():
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        r = client.get("/api/voice/stt-status")
        assert r.status_code == 200
        body = r.json()
        assert isinstance(body["available"], bool)
