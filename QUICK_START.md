# 🚀 PLUTO — Quick Start Guide

PLUTO runs a continuous **Listen → Understand → Plan → Act → Observe → Reason →
Speak → Listen** loop. After each answer it **speaks** and returns to
**LISTENING**, so you can keep giving commands.

## ⚠️ API Keys (optional)

Edited `pluto-backend/.env`:

- `GPT_OSS_API_KEY` — from [console.groq.com](https://console.groq.com) (model `openai/gpt-oss-120b`).
- `ELEVENLABS_API_KEY` — from [elevenlabs.io](https://elevenlabs.io).

Leave them empty to run in **mock mode** (scripted planner + browser TTS). The
full loop still works end-to-end with zero cost.

---

## 🏃 Start PLUTO

### Terminal 1 — Backend

```bash
cd pluto-backend
cp .env.example .env        # edit keys if you have them
./start.sh                  # FastAPI on http://127.0.0.1:8765
```

### Terminal 2 — Frontend

```bash
npm install
npm run dev                 # Next.js on http://localhost:3000
```

The Next dev server proxies `/api/backend/*` to the backend, so the frontend
uses only relative URLs.

---

## 🧪 Try It

Open **http://localhost:3000** and type or speak:

```
Open YouTube and play a great song
```

Expected flow:
1. Orb HUD: `LISTENING → UNDERSTANDING → THINKING → PLANNING → EXECUTING → OBSERVING → REASONING → SPEAKING`.
2. Execution steps animate in the panel; an activity is logged.
3. PLUTO **speaks** the result.
4. PLUTO returns to **LISTENING** — give the next command immediately.

Chain a multi-step task:

```
Open YouTube
Search Iron Man
Play the second video
Fullscreen
```

Each step runs, is spoken, and PLUTO stays ready for the next one.

For a **confirmed** (dangerous) action, e.g.:

```
Delete the cache file
```

PLUTO shows a **confirmation dialog**; you approve (`Confirm`) or cancel
(`Cancel`) and it continues accordingly.

---

## 📡 Check Backend

```bash
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/api/system/metrics
curl http://127.0.0.1:8765/api/tools
```

Docs: http://127.0.0.1:8765/docs

---

## 🐛 Troubleshooting

- **Frontend shows “cannot connect”** → make sure the backend is running on
  port 8765, then reload (the WS auto-reconnects).
- **No voice** → PLUTO uses browser `speechSynthesis` in mock mode (needs no key).
  For ElevenLabs audio, add `ELEVENLABS_API_KEY` and restart.
- **Steps not shown** → the backend emits `execution_step`, `activity`, `speak`
  events over `/api/backend/chat/ws`.
- **Mock planner** → inspect `pluto-backend/app/llm/gpt_oss.py` (`_build_plan`).

**PLUTO — an AI that actually controls your computer, and keeps talking. 🎯**
