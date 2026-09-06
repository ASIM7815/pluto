# PLUTO — Complete System Architecture

> **Next.js UI + FastAPI backend + GPT-OSS 120B brain + Python OS/tool layer
> + ElevenLabs voice + persistent context + autonomous agent loop**

PLUTO is a **local, futuristic Linux desktop AI assistant**. The existing
Next.js/React frontend is the *visual interface only*; a Python **FastAPI**
backend is the actual *brain and control system*. The frontend sends a
voice/text command to the backend, where **GPT-OSS 120B** understands the
intent, maintains context, plans the task, selects the appropriate tool,
checks permissions, and executes the action through Python.

---

## 1. The Core Agent Loop

PLUTO does not stop after one command. It runs a continuous autonomous loop:

```
     ┌─────────────────────────────────────────────────────────────────┐
     │                                                                 │
     ▼                                                                 │
  LISTEN ──► UNDERSTAND ──► PLAN ──► ACT ──► OBSERVE ──► REASON ──► SPEAK
  ▲                                                │        │        │
  │                                                │        └────────┘
  └────────────────────── (auto-return to LISTENING) ──────────────────┘
```

| Step | Backend module | What happens |
|------|----------------|--------------|
| **Listen**  | `app/voice/stt`, WebSocket | Speech/text captured from frontend, normalised into a command. |
| **Understand** | `app/llm` | GPT-OSS 120B parses the command with full conversation context + tool schema. |
| **Plan**    | `app/agent/orchestrator` | LLM returns either a plain answer or an ordered set of tool calls. |
| **Act**     | `app/tools` | Tool router dispatches to filesystem / apps / system / terminal / browser tools under permission control. |
| **Observe** | `app/tools` → `ToolResult` | Every tool returns a typed result (stdout, files list, success/error) — the *observation*. |
| **Reason**  | `app/agent/orchestrator` | The observation is fed back to GPT-OSS, which decides whether to call another tool or finish. This is what enables **multi-step tasks**. |
| **Speak**   | `app/voice/elevenlabs` | Final natural-language answer is synthesised to speech and streamed to the frontend. |
| **→ Listen** | WebSocket `listening` event | After speaking, the backend signals the frontend to return to `LISTENING` automatically. |

**Multi-step example** (each step loops through Act → Observe → Reason):

> “Open YouTube” → `open_url(youtube.com)` → observe OK
> → “Search Iron Man” → `open_url(youtube.com/results?search_query=iron+man)` → observe OK
> → “Play the second video” → `browser_click(second_result)` → observe OK
> → “Fullscreen” → `browser_key(press=F11)` → observe OK → done → speak.

---

## 2. High-Level Components

```
┌────────────────────────────  BROWSER (Next.js UI)  ────────────────────────────┐
│  PlutoOrb │ CommandBar │ VoiceButton │ ChatSession │ ActivityPanel │ Execution│
│        │  SystemOverview  │ ActionPreviewCard  │  ResponseDisplay              │
└───────────────┬─────────────────────────────────────────────────────────────────┘
                │  HTTPS/WS (proxied by Next.js dev server → relative /api/backend)
                ▼
┌────────────────────────────  FASTAPI BACKEND  ──────────────────────────────────┐
│                                                                                 │
│  ┌──────────────┐  ┌───────────────────┐  ┌────────────────────┐                │
│  │ API Layer    │  │  Agent Orchestrator│  │  Session Manager   │                │
│  │ REST + WS    │  │  (the brain loop)  │  │  (context + queue) │                │
│  └──────┬───────┘  └────────┬──────────┘  └─────────┬──────────┘                │
│         │                   │                       │                            │
│  ┌──────▼────────┐  ┌───────▼──────────┐  ┌─────────▼─────────┐                  │
│  │ LLM (GPT-OSS) │  │ Tool Registry     │  │ Voice (ElevenLabs)│                  │
│  │ 120B client   │  │ + Router          │  │ TTS + STT         │                  │
│  └───────────────┘  └───────┬──────────┘  └────────────────────┘                  │
│                             │                                                    │
│  ┌──────────────────────────▼─────────────────────────────────────────────┐     │
│  │  Python OS / Tool Layer                                                │     │
│  │  filesystem │ applications │ system │ terminal │ browser │ permissions │     │
│  └──────────────────────────┬─────────────────────────────────────────────┘     │
│                             │                                                    │
│  ┌──────────────────────────▼───────────┐                                       │
│  │ Security / Permissions Layer         │                                       │
│  │ path sandbox │ cmd classify │ limits │                                       │
│  └──────────────────────────────────────┘                                       │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Backend Module Design (`pluto-backend/app/`)

| Path | Responsibility |
|------|----------------|
| `main.py` | FastAPI app, CORS, lifespan, router mounting, `/health`. |
| `core/config.py` | `Settings` (env-driven), allowed paths, CORS origins, LLM/TTS keys, feature flags. |
| `core/security.py` | Path traversal prevention, filesystem sandbox, command safety classification (`SAFE`/`CONFIRM_REQUIRED`/`BLOCKED`), rate limits. |
| `core/logging.py` | Structured JSON logging (structlog). |
| `api/routes_chat.py` | WebSocket session hub: receives commands, emits events, handles `confirm`/`reject`/`interrupt`/`reset`. REST fallback `/execute`. |
| `api/routes_system.py` | Metrics, info, status (read-only). |
| `api/routes_voice.py` | `/synthesize` (TTS audio bytes), `/voices`, `/transcribe` (STT). |
| `api/routes_files.py` | Direct filesystem REST (guarded, permission-checked). |
| `api/routes_apps.py` | Direct application/URL REST (guarded). |
| `api/routes_tools.py` | Generic tool dispatch for the registry. |
| `agent/orchestrator.py` | The **brain loop**: Understand → Plan → Act → Observe → Reason → Speak → Listen. Owns per-session state and emits typed events. |
| `agent/session_manager.py` | Per-connection session (queue, history, pending confirmation, interrupt). Enables async WS while a command is paused on confirmation. |
| `agent/tool_registry.py` | Central tool catalogue + LLM function schema + permission metadata. |
| `agent/planner.py` | Structured plan builder (execution steps for the UI). |
| `llm/gpt_oss.py` | GPT-OSS 120B client (Groq / OpenAI-compatible), function calling, **mock mode** when no API key. |
| `llm/prompts.py` | System prompt, tool-use instructions, safety rules. |
| `voice/elevenlabs.py` | ElevenLabs TTS (audio bytes + streaming), mock mode returning a silent/beep audio. |
| `voice/stt.py` | Speech-to-text (Whisper / Web Speech pass-through), mock mode. |
| `tools/filesystem.py` | `create_file`, `read_file`, `list_directory`, `create_directory`, `delete_file`, `move`, `copy`. |
| `tools/applications.py` | `open_application`, `open_url` + app registry. |
| `tools/system.py` | `get_system_metrics`, `get_system_info`, `get_processes`, `kill_process`. |
| `tools/terminal.py` | `execute_command` (classified, timed, sandboxed). |
| `tools/browser.py` | Browser automation: `browser_click`, `browser_key`, `browser_navigate`, `browser_search`, `browser_snapshot`, `fullscreen`. |
| `schemas/*.py` | Pydantic models for events, requests, tool results, metrics. |

---

## 4. State Machine

The backend emits states that drive the orb & HUD:

```
idle ──► listening ──► understanding ──► thinking ──► planning ──► executing
                                                                 │
                                            executing ─► observing ─► reasoning ─► speaking
                                                                                     │
                                                                                     ▼
                                              (final answer) ──► listening (auto-return)
```

States: `idle, listening, understanding, thinking, planning, executing,
observing, reasoning, speaking, success, error`.

---

## 5. WebSocket Event Protocol (`/api/backend/chat/ws`)

Client → Server:
```jsonc
{ "type": "command",   "command": "Open YouTube and play Iron Man", "context": {} }
{ "type": "confirm",   "action": "execute_command" }   // approve pending CONFIRM_REQUIRED action
{ "type": "reject",    "action": "execute_command" }   // cancel pending action
{ "type": "interrupt" }                                 // stop current task
{ "type": "reset",     "clearHistory": true }
```

Server → Client:
```jsonc
{ "type": "agent_state", "state": "understanding", "task": "Parsing request..." }
{ "type": "agent_state", "state": "planning",     "task": "Planning steps..." }
{ "type": "execution_step", "step": { "id": "s1", "label": "Open YouTube", "status": "current" } }
{ "type": "activity", "activity": { "id": "...", "title": "Opened YouTube", "status": "success", "category": "app" } }
{ "type": "action_preview", "preview": { "type": "command", "title": "Confirm", "requiresConfirmation": true } }
{ "type": "agent_state", "state": "observing", "task": "Checking result..." }
{ "type": "agent_state", "state": "reasoning", "task": "Deciding next step..." }
{ "type": "agent_state", "state": "speaking", "task": "Speaking response..." }
{ "type": "speak", "text": "I have opened YouTube.", "audio": "<base64 mp3|null>", "tts": "elevenlabs|browser" }
{ "type": "agent_state", "state": "listening", "task": "Ready for your next command." }
{ "type": "error", "error": "..." }
```

---

## 6. Data Flow (single command)

1. Frontend captures command (voice via STT or text).
2. `aiService.executeCommand()` → `ws.send(command)`.
3. Backend `SessionManager.submit_command()` spawns an async agent task.
4. Orchestrator: `UNDERSTANDING` → LLM `complete(messages, tools)`.
5. LLM returns `tool_calls` or `content`.
6. If `tool_calls`: build `execution_step`s, `PLANNING`.
7. Permission check:
   - `SAFE` → execute.
   - `CONFIRM_REQUIRED` → emit `action_preview`, **pause** the task on an `asyncio.Event`.
   - `BLOCKED` → emit `error`.
8. Tool runs → `ToolResult` (**observation**). Emit `execution_step completed` + `activity`.
9. Append observation to messages; call LLM again (**OBSERVE → REASON**). Loop until no more tool calls.
10. Final `content` → emit `speaking`, synthesise via ElevenLabs (or fall back to browser TTS).
11. Emit `speak` event (text + audio) and a final `success`.
12. Emit `listening` → frontend returns to LISTENING.

---

## 7. Security Model

All actions pass through **centralized validation** so GPT-OSS never gets
unrestricted shell or filesystem access.

- **Filesystem sandbox**: every path resolved & checked against
  `PLUTO_ALLOWED_PATHS`; traversal & `/etc`, `/sys`, `/proc` blocked.
- **Command classification**: `SAFE` (auto), `CONFIRM_REQUIRED` (ask user),
  `BLOCKED` (never) via pattern list.
- **Permissions registry**: each tool declares `permission_level`.
- **Confirmation gate**: dangerous tools emit `action_preview` and pause until the user confirms.
- **Rate limits / timeouts**: tool execution timeouts, max steps per task, max command length.
- **No arbitrary code**: terminal uses `subprocess.run` with `shlex.split`; no `shell=True`.
- **API keys never exposed** to the browser; they live only in backend `.env`.

---

## 8. Frontend Changes (`src/`)

- `services/ai.ts`: real WS client (relative `/api/backend/chat/ws`), handle
  `speak`, `listening`, `observing`, `reasoning`, `speaking` events.
- `services/voice.ts`: STT via Web Speech API (with simulated fallback), TTS
  via backend ElevenLabs **with browser `speechSynthesis` fallback** so PLUTO
  always talks even without an API key.
- `services/system.ts`: real metrics (proxied REST).
- `store/plutoStore.ts`: new states + `isSpeaking`.
- `components/orb/OrbStateLabels.tsx`: show OBSERVING / REASONING / SPEAKING.
- `components/command/CommandBar.tsx`: keyboard submit → executeCommand.
- `app/page.tsx` / `app/chat/page.tsx`: wire continuous listening.

---

## 9. Environment / Run

```bash
# Backend
cd pluto-backend
cp .env.example .env          # add keys (optional; mock mode works without them)
./start.sh                    # FastAPI on http://127.0.0.1:8765

# Frontend
npm run dev                   # Next.js on http://localhost:3001 (proxies /api/backend -> 8765)
```

- Without API keys the backend runs in **mock mode**: GPT-OSS 120B + ElevenLabs
  are simulated, and the frontend speaks via the browser's built-in TTS. This
  lets the full Listen→…→Speak→Listen loop be demoed end-to-end with zero cost.

---

## 10. Running the Loop Live

1. Press the red mic (or click a Quick Action / type a command).
2. PLUTO emits `understanding → planning → executing → observing → reasoning → speaking`.
3. The orb HUD tracks the state; execution steps and activities update live.
4. PLUTO **speaks** the result, then automatically returns to **LISTENING**.
5. Give the next command — the loop continues without ever "ending".
