# P L U T O — Linux Desktop AI Assistant

**Next.js UI + FastAPI backend + GPT-OSS 120B brain + Python OS/tool layer
+ ElevenLabs voice + persistent context + autonomous agent loop.**

PLUTO is a **local, futuristic Linux desktop AI assistant**. The Next.js/React
frontend is the *visual interface* (orb, HUD, command bar, activity timeline);
a Python **FastAPI** backend is the actual *brain and control system*. Your
voice/text command goes to the backend, where **GPT-OSS 120B** understands the
intent, keeps context, plans the task, picks the right tool, checks
permissions, and executes the action through a sandboxed Python tool layer.
**ElevenLabs** (or the browser's built-in TTS) speaks the response, and PLUTO
automatically returns to **LISTENING** for your next command.

```
Listen → Understand → Plan → Act → Observe → Reason → Speak → Listen
```

---

## ⚡ Quick Start

### 1. Backend (FastAPI)

```bash
cd pluto-backend
cp .env.example .env          # optional: add GPT_OSS & ElevenLabs keys
./start.sh                    # runs on http://127.0.0.1:8765
```

> No API keys? PLUTO runs in **mock mode** — the GPT-OSS planner is scripted and
> speech uses the browser's built-in TTS, so the whole loop works with zero cost.
> Add `GPT_OSS_API_KEY` (Groq) and `ELEVENLABS_API_KEY` for the real thing.

### 2. Frontend (Next.js)

```bash
npm install
npm run dev                   # runs on http://localhost:3000
```

The Next dev server **proxies** `/api/backend/*` to the FastAPI backend, so the
frontend always uses relative URLs (works from any host).

Open **http://localhost:3000**, press the red mic (or type), and say / type:

> “Open YouTube and play a great song”

Watch PLUTO plan → execute → **speak** → return to **LISTENING**, ready for the
next command. Then chain steps:

> “Search Iron Man” → “Play the second video” → “Fullscreen”

---

## 🧠 How It Works

| Component | Role |
|-----------|------|
| **Next.js UI** | Orb, HUD (LISTENING/UNDERSTANDING/…/SPEAKING), command bar, execution steps, activity timeline. |
| **FastAPI backend** | WebSocket hub + agent orchestrator (the loop), tool router, sessions. |
| **GPT-OSS 120B** | Understands intent, plans tool calls, reasons on tool results (Observe → Reason). |
| **Python tool layer** | Filesystem, applications, system, terminal, browser automation — all sandboxed. |
| **ElevenLabs / browser TTS** | Speaks each response. Falls back to browser `speechSynthesis` when no API key. |
| **Persistent context** | Conversation history kept per WebSocket session across commands. |
| **Security layer** | Path sandboxing, command classification, permission gates, confirmations. |

## 🔐 Security

All actions pass through **centralized validation** — GPT-OSS never gets
unrestricted shell or filesystem access:

- Filesystem sandboxed to `PLUTO_ALLOWED_PATHS`; traversal & `/etc`, `/sys` blocked.
- Terminal commands classified `SAFE` / `CONFIRM_REQUIRED` / `BLOCKED`.
- Destructive tools emit a **confirmation dialog** and pause until you approve.
- API keys live only in the backend `.env`, never sent to the browser.

## 📁 Repo Layout

```
pluto/
├── src/                         # Next.js frontend (design preserved)
│   ├── services/ai.ts           # WebSocket client → backend loop
│   ├── services/voice.ts        # STT (Web Speech API) + TTS
│   ├── services/tts.ts          # ElevenLabs audio / browser-TTS fallback
│   └── components/...           # Orb, HUD, command bar, cards
├── pluto-backend/               # Python FastAPI backend
│   ├── app/
│   │   ├── agent/               # orchestrator + tool registry + session manager
│   │   ├── llm/                 # GPT-OSS 120B client (+ mock planner)
│   │   ├── voice/               # ElevenLabs TTS (+ mock), STT stub
│   │   ├── api/                 # chat WS, system, voice, tools routes
│   │   ├── tools/               # fs, apps, system, terminal, browser
│   │   ├── core/                # config, security, logging
│   │   └── schemas/             # pydantic models
│   └── start.sh
├── ARCHITECTURE.md              # full system architecture
└── next.config.ts               # /api/backend/* proxy → 127.0.0.1:8765
```

## 📚 Docs

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — complete architecture & agent loop.
- [`pluto-backend/README.md`](pluto-backend/README.md) — backend internals.
- [`QUICK_START.md`](QUICK_START.md) — run & demo guide.
- [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md) — frontend ↔ backend wiring.

Built with Next.js, FastAPI, GPT-OSS 120B, ElevenLabs and psutil. 🎯
