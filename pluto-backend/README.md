# PLUTO Backend — Python FastAPI Agent

🤖 The **brain & control system** of PLUTO. Runs the autonomous
**Listen → Understand → Plan → Act → Observe → Reason → Speak → Listen** loop.

```
Frontend (Next.js) ←WebSocket/REST→ FastAPI ←GPT-OSS 120B/Tools/voice→ ElevenLabs
                                     ↓
                          Agent Orchestrator (the loop)
                                     ↓
                        Tool Registry (permission-gated)
                                     ↓
             OS Tools: fs | apps | system | terminal | browser
```

## Run

```bash
cd pluto-backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add GPT_OSS_API_KEY / ELEVENLABS_API_KEY (optional)
python -m app.main          # or: uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload
```

> **Mock mode** — with empty API keys the GPT-OSS planner is deterministic and
> speech falls back to the browser's `speechSynthesis`. The loop runs end-to-end
> with no credentials.

## Architecture (`app/`)

| Path | Responsibility |
|------|----------------|
| `main.py` | FastAPI app, CORS, routers, `/health`. |
| `api/routes_chat.py` | **WebSocket hub** — receives `command`/`confirm`/`reject`/`interrupt`/`reset`, streams events back. REST fallbacks. |
| `api/routes_system.py` | Read-only metrics / info / status. |
| `api/routes_voice.py` | `/synthesize`, `/voices`. |
| `api/routes_tools.py` | Tool introspection (`/api/tools`). |
| `agent/orchestrator.py` | **The brain loop** — Understand → Plan → Act → Observe → Reason → Speak → Listen. |
| `agent/session_manager.py` | Per-connection state: event queue, history, confirmation gate, interrupt. |
| `agent/tool_registry.py` | Tool catalogue + LLM function schema + permission metadata. |
| `llm/gpt_oss.py` | GPT-OSS 120B client (`openai/gpt-oss-120b`) + deterministic mock planner. |
| `voice/elevenlabs.py` | ElevenLabs TTS + mock (returns browser-TTS signal when no key). |
| `voice/stt.py` | Speech-to-text stub (server-side STT hook). |
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

## Tests

```bash
pytest tests/
```

Built with FastAPI, GPT-OSS 120B, ElevenLabs and psutil. 🚀
