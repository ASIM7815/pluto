# PLUTO Backend — Python FastAPI Agent

🤖 The **brain & control system** of PLUTO. Runs the autonomous
**Listen → Understand → Plan → Act → Observe → Reason → Speak → Listen** loop.

```
Frontend (Next.js) ←WebSocket/REST→ FastAPI  (100% local brain)
                                     ↓
               PlutoBrain: intent (TF-IDF+sklearn) → entities → confidence
                                     ↓
                      Multi-step planner (app/agent/nlu.py)
                                     ↓
                        Tool Registry (permission-gated)
                                     ↓
             OS Tools: fs | apps | system | terminal | browser
```

> **No external AI/API.** PLUTO understands commands with its own local model
> (scikit-learn TF-IDF + linear classifier), persistent SQLite memory, and a
> deterministic multi-step planner. Bring your own model/tokens? Not needed.
> Optional cloud TTS (ElevenLabs) and cloud STT are strictly opt-in; the core
> loop works fully offline.

## Run

```bash
cd pluto-backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
./start.sh                          # Linux/macOS (creates venv + installs)
# or: python run.py                 # canonical entry point
# or (Windows): start.bat
```

No `.env` / API keys are required — PLUTO runs fully local by default:

```bash
python run.py                 # 127.0.0.1:8765
python run.py --preview       # bind 0.0.0.0 for container previews
```

## Architecture (`app/`)

| Path | Responsibility |
|------|----------------|
| `main.py` | FastAPI app, CORS, routers, `/health`. |
| `api/routes_chat.py` | **WebSocket hub** — receives `command`/`confirm`/`reject`/`interrupt`/`reset`, streams events back. REST fallbacks. |
| `api/routes_system.py` | Read-only metrics / info / status. |
| `api/routes_voice.py` | `/synthesize`, `/voices`. |
| `api/routes_tools.py` | Tool introspection (`/api/tools`). |
| `agent/pattern_orchestrator.py` | **The active brain loop** — Understand intent → Plan (multi-step) → Act → Observe → Verify → Recover → Speak → Listen. |
| `agent/nlu.py` | Deterministic multi-step planner (never invents a tool). |
| `intelligence/` | **PLUTO's OWN local intelligence** — intent classifier (TF-IDF + scikit-learn), entity extraction, semantic similarity, SQLite memory (`contexts` table + correction pairs), trainer. No external AI/API. |
| `platform/` | **Platform abstraction** — `PlutoPlatform` base + `linux` / `windows` / `android` adapters sharing one core. Exposed via `/api/tools/platform`. |
| `agent/session_manager.py` | Per-connection state: event queue, history, confirmation gate, interrupt. |
| `agent/context_manager.py` | In-memory per-session context (apps/browser/files/search). |
| `agent/orchestrator.py` | Legacy LLM-driven orchestrator (kept for reference; not the active path). |
| `llm/gpt_oss.py` | Legacy GPT-OSS client + deterministic mock planner (used by tests). |
| `voice/elevenlabs.py` | Legacy ElevenLabs TTS (external; unused in the default path). |
| `voice/local_tts.py` | **Offline-first local TTS** — espeak-ng → pyttsx3 → gTTS (last resort). |
| `voice/stt.py` | Speech-to-text (faster-whisper offline, or Google Web Speech; browser Web Speech API is the fallback). |
| `tools/...` | `filesystem`, `applications`, `system`, `terminal`, `browser` tools. |
| `core/config.py` | `Settings` (env-driven), allowed paths, CORS, mock flags. |
| `core/security.py` | Path sandbox, command classification (`SAFE`/`CONFIRM_REQUIRED`/`BLOCKED`). |
| `schemas/` | Pydantic models for events, requests, results. |

## Tools

Filesystem: `create_file`, `read_file`, `list_directory`, `create_directory`,
`delete_file` *(confirm)* · Applications: `open_application`, `open_url` ·
System: `get_processes` · Terminal: `execute_command` *(confirm)* ·
Browser: `browser_navigate`, `browser_click`, `browser_key`,
`browser_fullscreen`, `browser_snapshot`.

## WebSocket Events (server → client)

```jsonc
{ "type": "agent_state",    "state": "executing", "task": "Executing open_url..." }
{ "type": "execution_step", "step": { "id": "s1", "label": "Open YouTube", "status": "current" } }
{ "type": "activity",       "activity": { "title": "Opened YouTube", "status": "success", "category": "app" } }
{ "type": "action_preview", "preview": { "requiresConfirmation": true } }
{ "type": "speak",          "text": "I've opened YouTube.", "audio": "<base64|null>", "tts": "browser" }
{ "type": "agent_state",    "state": "listening", "task": "Ready for your next command." }
```

## Security

- Filesystem sandboxed to `PLUTO_ALLOWED_PATHS`; traversal & system dirs blocked.
- Terminal commands classified `SAFE` / `CONFIRM_REQUIRED` / `BLOCKED`.
- Permission gates pause on dangerous tools until the user confirms.
- API keys live only in `.env`; never exposed to the browser.

## Local intelligence API

PLUTO's on-device brain is fully self-hosted. Key routes:

- `GET  /api/tools/intelligence/status` — classifier state, accuracy, model path.
- `POST /api/tools/intelligence/train`  — train + evaluate from corpus + corrections.
- `GET  /api/tools/intelligence/actions` — recent recorded actions (success/failure).
- `POST /api/chat/correct`              — record a user correction + optional retrain.
- `GET  /api/tools/platform`            — active platform adapter + its capabilities.

Context snapshots persist per `session_id` in SQLite when
`PLUTO_PERSIST_CONTEXT=true` (default), so PLUTO remembers state across restarts.

## Train / evaluate the local intent model

PLUTO trains its own intent classifier from its corpus plus any user
corrections stored in SQLite. The model is saved to `~/.pluto/models/`.

```bash
python -m app.intelligence.trainer        # train + evaluate + save
```

## Tests

```bash
pytest tests/
```

Built with FastAPI + PLUTO's own local brain (TF-IDF + scikit-learn), SQLite
memory, and offline-first voice. No external AI/API required. 🚀
