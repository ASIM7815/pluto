"""Tests for the Level-1 fixes: real-browser detection, URL normalization,
server-side STT plumbing, communicative replies and interrupt handling."""
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.llm.gpt_oss import GPTOSSClient
from app.tools.browser import (
    _NAV_ERROR_MARKERS,
    BrowserManager,
    detect_system_browser,
    normalize_url,
)
from app.voice.stt import STTClient, _sniff_format


# ---------------------------------------------------------------------------
# Browser resolution & URL handling
# ---------------------------------------------------------------------------
class TestNormalizeUrl:
    def test_bare_site_names(self):
        assert normalize_url("youtube") == "https://www.youtube.com"
        assert normalize_url("YouTube") == "https://www.youtube.com"
        assert normalize_url("github") == "https://github.com"

    def test_domains(self):
        assert normalize_url("youtube.com") == "https://www.youtube.com"
        assert normalize_url("www.youtube.com") == "https://www.youtube.com"
        assert normalize_url("example.org") == "https://example.org"

    def test_full_urls_untouched(self):
        assert (
            normalize_url("https://github.com/ASIM7815/pluto")
            == "https://github.com/ASIM7815/pluto"
        )
        assert normalize_url("http://localhost:3000") == "http://localhost:3000"

    def test_free_text_becomes_search(self):
        url = normalize_url("my cool search query")
        assert url.startswith("https://www.google.com/search?q=")
        assert "my+cool" in url

    def test_empty_is_safe(self):
        assert normalize_url("") == "https://www.google.com"
        assert normalize_url('  "youtube" ') == "https://www.youtube.com"


class TestBrowserDetection:
    def test_detection_returns_none_or_valid_tuple(self):
        result = detect_system_browser()
        if result is not None:
            path, name = result
            assert path.startswith("/") or "/" not in name
            assert name  # display name always present

    def test_manager_reports_which_browser_it_would_use(self):
        mgr = BrowserManager()
        kwargs = mgr._resolve_launch_target()
        if "executable_path" in kwargs:
            assert kwargs["executable_path"]  # concrete path, never empty
        assert mgr.browser_name != "not started"

    def test_executable_override_wins(self, monkeypatch):
        monkeypatch.setenv("PLUTO_BROWSER_EXECUTABLE", "/usr/bin/my-chrome")
        mgr = BrowserManager()
        kwargs = mgr._resolve_launch_target()
        assert kwargs.get("executable_path") == "/usr/bin/my-chrome"

    def test_error_page_markers_present(self):
        joined = " ".join(_NAV_ERROR_MARKERS).lower()
        assert "net::err" in joined
        assert "this site can" in joined  # typographic + ASCII variants exist


# ---------------------------------------------------------------------------
# Server-side STT
# ---------------------------------------------------------------------------
class TestStt:
    def test_engine_status_shape(self):
        status = STTClient().engine_status()
        assert {"available", "engines", "ffmpeg", "hint"} <= set(status.keys())
        assert isinstance(status["available"], bool)
        assert isinstance(status["engines"], list)

    def test_sniff_format(self):
        assert _sniff_format(b"\x1a\x45\xdf\xa3....") == "webm"
        assert _sniff_format(b"OggS....") == "ogg"
        assert _sniff_format(b"RIFF\x00\x00\x00\x00WAVE") == "wav"
        assert _sniff_format(b"garbage") == "unknown"

    @pytest.mark.asyncio
    async def test_transcribe_empty_is_honest(self):
        text, engine = await STTClient().transcribe(b"")
        assert text == ""


# ---------------------------------------------------------------------------
# Communicative responses
# ---------------------------------------------------------------------------
class TestCommunicativeReplies:
    def test_known_upgrades(self):
        assert "BOSS" in GPTOSSClient._communicative("I've opened YouTube.")
        assert "BOSS" in GPTOSSClient._communicative("Playing the second video.")

    def test_generic_statements_get_followup(self):
        out = GPTOSSClient._communicative("Opened the folder.")
        assert out.startswith("Opened the folder.")
        assert "BOSS" in out

    def test_blank_never_empty(self):
        assert GPTOSSClient._communicative("") != ""


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------
class TestApi:
    def test_health(self):
        from app.main import app

        with TestClient(app) as client:
            r = client.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "healthy"

    def test_stt_status_endpoint(self):
        from app.main import app

        with TestClient(app) as client:
            r = client.get("/api/voice/stt-status")
            assert r.status_code == 200
            body = r.json()
            assert isinstance(body["available"], bool)
            assert "engines" in body

    def test_transcribe_rejects_empty_upload(self):
        from app.main import app

        with TestClient(app) as client:
            r = client.post(
                "/api/voice/transcribe",
                files={"file": ("speech.webm", b"", "audio/webm")},
            )
            assert r.status_code == 400

    def test_interrupt_phrases_defined(self):
        from app.api.routes_chat import INTERRUPT_PHRASES, SILENCE_KEYWORDS

        assert "stop" in INTERRUPT_PHRASES
        assert "cancel" in INTERRUPT_PHRASES
        # "stop the music" must NOT be classified as an interrupt (substring
        # check would break it) - hence exact-match semantics.
        assert "stop the music" not in INTERRUPT_PHRASES
        assert any("silence" in k for k in SILENCE_KEYWORDS)

    def test_response_style_config(self):
        assert settings.pluto_response_style in ("concise", "friendly", "detailed")


# ---------------------------------------------------------------------------
# BrowserManager with a mocked Playwright (validates the persistent-profile
# launch path, page reuse and error-page detection without a real browser).
# ---------------------------------------------------------------------------
class _FakePage:
    def __init__(self) -> None:
        self.url = "about:blank"
        self._title = "Some Page"
        self._body = "welcome"

    async def goto(self, url, **kwargs):
        self.url = url
        return None

    async def title(self):
        return self._title

    async def evaluate(self, _expr):
        return self._body


class _FakeContext:
    def __init__(self) -> None:
        self.page = _FakePage()
        self.pages = [self.page]
        self.closed = False

    async def new_page(self):
        return self.page

    async def close(self):
        self.closed = True


class _FakeChromium:
    def __init__(self, context: _FakeContext) -> None:
        self._context = context
        self.calls: list = []

    async def launch_persistent_context(self, user_data_dir, **kwargs):
        self.calls.append(("persistent", user_data_dir, kwargs))
        return self._context

    async def launch(self, **kwargs):
        self.calls.append(("classic", kwargs))
        return self._context


class _FakePW:
    def __init__(self, chromium: _FakeChromium) -> None:
        self.chromium = chromium

    async def start(self):
        return self

    async def stop(self):
        return None


@pytest.mark.asyncio
async def test_persistent_launch_uses_profile_and_reuses_page(monkeypatch):
    import app.tools.browser as bm

    context = _FakeContext()
    chromium = _FakeChromium(context)
    manager = bm.BrowserManager()

    monkeypatch.setattr(bm, "_PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr(bm, "async_playwright", lambda: _FakePW(chromium))
    monkeypatch.setattr(bm.settings, "pluto_browser_persistent_profile", True)
    monkeypatch.setattr(bm.settings, "pluto_browser_profile_dir", "/tmp/pluto-test-profile")

    r1 = await manager.navigate("https://example.com")
    assert r1.success, r1.error
    assert chromium.calls and chromium.calls[0][0] == "persistent"
    # The page from the persistent context is reused, not re-created.
    r2 = await manager.navigate("youtube")
    assert r2.success
    assert len(chromium.calls) == 1
    assert context.page.url == "https://www.youtube.com"
    assert r1.data["url"] == "https://example.com"
    await manager.close()
    assert context.closed


@pytest.mark.asyncio
async def test_error_page_is_detected_and_reported(monkeypatch):
    import app.tools.browser as bm

    context = _FakeContext()
    context.page._title = "Example Error"
    context.page._body = "This site can’t be reached. net::ERR_NAME_NOT_RESOLVED"
    chromium = _FakeChromium(context)
    manager = bm.BrowserManager()

    monkeypatch.setattr(bm, "_PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr(bm, "async_playwright", lambda: _FakePW(chromium))
    monkeypatch.setattr(bm.settings, "pluto_browser_persistent_profile", True)
    monkeypatch.setattr(bm.settings, "pluto_browser_profile_dir", "/tmp/pluto-test-profile")
    # Only one attempt so the retry doesn't mask the verdict.
    async def fake_goto(url):
        return bm.ToolResult.ok("browser", "loaded")

    monkeypatch.setattr(manager, "_goto", fake_goto)
    import asyncio

    real_sleep = asyncio.sleep

    async def fast_sleep(_s):
        await real_sleep(0)

    monkeypatch.setattr(bm.asyncio, "sleep", fast_sleep)

    r = await manager.navigate("https://does-not-exist.invalid")
    assert not r.success
    assert "did not load" in (r.error or "")
