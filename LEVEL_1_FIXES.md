# PLUTO Level 1 — Reliability & UX Fixes

> **Date**: September 6, 2026
> **Scope**: Fixes for the four issues reported after the Level-1 build:
> wrong browser being launched, unreliable voice detection with silent
> failures, no way to stop the AI's voice, and replies that were too terse.

---

## 1. "Open YouTube" now uses YOUR real Chrome (not Playwright's Chromium)

**Before:** `BrowserManager` always called `playwright.chromium.launch()`,
which spawns Playwright's own downloaded Chromium — an anonymous window with
no profile, even when Google Chrome was installed on the machine.

**Now** (`pluto-backend/app/tools/browser.py`) the browser binary is resolved
in this order:

1. `PLUTO_BROWSER_EXECUTABLE` env var (explicit override)
2. `PLUTO_BROWSER_EXECUTABLE` setting in `.env`
3. **Your real installed browser**, auto-detected:
   `google-chrome-stable` → `google-chrome` → `chromium` → `brave` → `edge` → `vivaldi`
4. Playwright's bundled Chromium (last resort)

### Persistent profile
PLUTO launches the browser with `launch_persistent_context` and keeps its own
profile at `~/.pluto/browser-profile`. Logins (YouTube, GitHub…) survive
between runs, so it behaves like a normal browser you keep using.

### New configuration (`.env` in `pluto-backend/`)
```ini
PLUTO_BROWSER_EXECUTABLE=            # empty = auto-detect your real browser
PLUTO_BROWSER_CHANNEL=               # optional playwright channel, e.g. chrome
PLUTO_BROWSER_PERSISTENT_PROFILE=true
PLUTO_BROWSER_PROFILE_DIR=~/.pluto/browser-profile
PLUTO_BROWSER_HEADLESS=auto          # auto = headless only without a display
```

### Other browser fixes
- `normalize_url()`: "youtube", "YouTube", "youtube.com", "www.youtube.com"
  all resolve correctly; free text falls back to a Google search URL instead
  of an invalid domain.
- **Retry once** on navigation timeout/failure before reporting the error.
- **Error-page detection**: Chrome's "This site can't be reached /
  `net::ERR_*`" pages are detected and reported as failures — previously a
  DNS error could be announced as success.
- Friendly, actionable launch errors (install Chrome / set
  `PLUTO_BROWSER_EXECUTABLE` / `playwright install chromium`).
- `open_application("youtube")` no longer secretly launches Firefox —
  websites always go through `open_url` (PLUTO's browser).

---

## 2. Voice detection: robust continuous listening + visible errors

**Before:** every `SpeechRecognition` error was swallowed silently, the mic
died permanently on the first `no-speech`/`network` error, and when the Web
Speech API was missing the UI *simulated* fake commands — which looked like
"voice detection not working".

**Now** (`src/services/voice.ts`, fully rewritten):

| Problem | Behaviour now |
|---|---|
| Mic permission denied | Clear message: allow the microphone via the lock icon |
| No microphone found | Clear "No microphone was found…" message |
| `network` speech-service errors | Auto-retry ×3, then fall back to server STT |
| Chrome ending the session after silence | Transparent auto-restart watchdog — **listening never dies** |
| Speaking too early / trailing silence | End-of-utterance detection (1.4 s pause ⇒ run command) |
| Browser has no Web Speech API (Firefox) | Records via `MediaRecorder` → backend transcription |
| Neither engine available | Honest error + install hints, never fake input |

### New server-side STT (Python)
- `GET  /api/voice/stt-status` — reports which engines are installed
- `POST /api/voice/transcribe` — transcribes an audio clip

Engines (optional, auto-detected in this order):
1. **faster-whisper** — fully offline: `pip install faster-whisper`
2. **SpeechRecognition** (Google Web Speech) — `pip install SpeechRecognition`
3. `ffmpeg` on the system converts browser audio (webm/ogg → wav)

`SpeechRecognition` was added to `requirements.txt`.

---

## 3. You can now STOP the voice (button or just say "stop")

- **New `StopButton` component** appears on Home (command bar) and in Chat
  whenever PLUTO is speaking or executing. One click stops the speech **and**
  interrupts the running task.
- **The mic button doubles as a stop button** while PLUTO is talking.
- **Voice barge-in**: saying just *"stop"*, *"cancel"*, *"quiet"* or
  *"silence"* (exact phrases) interrupts the current task/speech instead of
  being executed as a command. Sentences like *"stop the music"* still work
  as normal commands.
- Fixed a real hang: `cancelSpeech()` previously left the UI stuck in the
  "speaking" state forever because pausing audio never resolved the playback
  promise (`src/services/tts.ts`).
- **Chat page is now real** — it previously showed a fake "Understood:
  … Initiating AI agent execution sequence…" reply. It now shows PLUTO's
  actual responses from the agent pipeline, live state (thinking/executing/
  speaking), the live voice transcript, mic support, and a Stop control.

---

## 4. PLUTO is now communicative

- The system prompt told the model to answer in **"one or two short
  sentences"** — replaced with a *How you speak* section: warm, 2–4 spoken
  sentences, confirm what was done, add a useful detail (page title, number
  of results, what was verified), offer the next step, sign with "BOSS"
  once in a while. Examples included for success *and* failure.
- New setting `PLUTO_RESPONSE_STYLE` = `friendly` (default) | `concise` |
  `detailed`.
- Mock mode (no API key) upgrades its canned replies the same way, e.g.
  *"YouTube is open in your browser, BOSS — the homepage loaded just fine.
  Want me to search for something?"*
- Failure messages now recover out loud: *"I couldn't complete that, BOSS:
  … I'm still listening — want me to try again?"*

---

## Testing

```bash
cd pluto-backend && python3 -m pytest tests/ -q   # 26 passed
cd . && npx tsc --noEmit && npm run lint && npm run build
```

New test file `pluto-backend/tests/test_level1_fixes.py` covers URL
normalization, browser detection & override, persistent-profile launch (with
a mocked Playwright), error-page detection, STT status/transcription
plumbing, communicative replies, interrupt phrases, and the new endpoints.

## Quick sanity flow to try on your machine

1. `cd pluto-backend && ./start.sh` (backend) and `npm run dev` (frontend)
2. Say/press mic: **"Open YouTube"** → opens in your installed Chrome, says
   *"YouTube is open in your browser, BOSS…"*, returns to listening.
3. **"Search Iron Man"** → searches on the YouTube page it knows is open.
4. **"Choose the second video"** → clicks result #2, verifies, speaks.
5. While it talks, click **STOP** (or say *"stop"*) → silence, back to
   listening.
