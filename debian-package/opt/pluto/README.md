# P L U T O — Linux Desktop AI Assistant

**Next.js UI + FastAPI backend + 100% local PLUTO brain + Python OS/tool layer
+ persistent context + autonomous agent loop.**

PLUTO is a **local, futuristic Linux desktop AI assistant**. The Next.js/React
frontend is the *visual interface* (orb, HUD, command bar, activity timeline);
a Python **FastAPI** backend is the actual *brain and control system*. Your
voice/text command goes to the backend, where **PLUTO's own local intelligence**
understands the intent (TF-IDF + a locally trained scikit-learn classifier),
extracts entities, scores confidence, plans a multi-step task, picks the right
tool, checks permissions, executes the action through a sandboxed Python tool
layer, verifies it worked, and recovers on failure. **No external AI/API
(OpenAI/GPT/Gemini/Claude/Ollama/OpenRouter/Groq) is required.** Speech falls
back to the browser's built-in TTS; cloud TTS/STT are strictly optional.

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

> **No API keys required.** PLUTO uses its own local model (TF-IDF + scikit-learn
> classifier) for understanding and the browser's built-in TTS for speech, so the
> whole loop works offline at zero cost. Cloud `GPT_OSS_API_KEY` / ElevenLabs
> keys are strictly optional and not needed for local tasks.

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
| **FastAPI backend** | WebSocket hub + brain-driven orchestrator (the loop), tool router, sessions. |
| **PlutoBrain (local)** | PLUTO's own intelligence: intent classification (TF-IDF + scikit-learn), entity extraction, confidence, multi-step planning, verification & recovery. |
| **Persistent memory** | SQLite-backed actions/corrections so PLUTO remembers and learns. |
| **Python tool layer** | Filesystem, applications, system, terminal, browser automation — all sandboxed & verified. |
| **Browser / optional TTS** | Speaks each response via the browser `speechSynthesis` (or optional local/cloud TTS). |
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
│   │   ├── agent/               # brain-driven orchestrator, planner, session manager
│   │   ├── intelligence/        # PLUTO's OWN local brain: classifier, entities,
│   │   │                        #   memory, trainer, pipeline  (NO external AI)
│   │   ├── llm/                 # legacy GPT-OSS client (kept for reference)
│   │   ├── voice/               # optional TTS/STT, browser TTS fallback
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
