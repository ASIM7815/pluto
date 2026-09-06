# 🔌 PLUTO Frontend ↔ Backend Integration Guide

The frontend talks to the backend through a Next.js **rewrite proxy** so it
always uses **relative URLs** (`/api/backend/*`) — no hardcoded `127.0.0.1`.

```ts
// next.config.ts — proxies /api/backend/* -> http://127.0.0.1:8765/api/*
async rewrites() {
  return [{ source: "/api/backend/:path*", destination: "http://127.0.0.1:8765/api/:path*" }];
}
```

---

## 🗂 Services

### `src/services/ai.ts`
The WebSocket client (the core bridge). Connects to relative
`/api/backend/chat/ws`, sends `{ type: "command", command }`, and maps incoming
events to `plutoStore`:

| Backend event | Frontend action |
|---------------|-----------------|
| `agent_state` | sets state (`listening`, `observing`, `reasoning`, `speaking`, …) + current task |
| `execution_step` | updates the step list (pending → current → completed) |
| `activity` | prepends to the activity timeline |
| `action_preview` | shows a confirmation / preview dialog |
| `speak` | plays ElevenLabs audio **or** browser TTS, then returns to LISTENING |
| `error` | shows the error card |

### `src/services/voice.ts`
Speech-to-text via the **Web Speech API** (`webkitSpeechRecognition`) when
available, with a simulated-typing fallback for browsers/iframes without mic
access. Also calls the backend `/api/backend/voice/synthesize` for TTS.

### `src/services/tts.ts`
`speak(text, audioBase64?)` — plays ElevenLabs audio when present, otherwise
uses `window.speechSynthesis`. On finish it sets the UI back to **LISTENING**
(continuous loop). `cancelSpeech()` stops any in-flight utterance.

### `src/services/system.ts`
Fetches real metrics from `/api/backend/system/metrics` and `/api/backend/system/info`,
falling back to mock data when the backend is unreachable.

---

## 📡 WebSocket Protocol

Client → Server (JSON):

```jsonc
{ "type": "command",   "command": "Open YouTube" }
{ "type": "confirm",   "action": "delete_file" }
{ "type": "reject",    "action": "delete_file" }
{ "type": "interrupt" }
{ "type": "reset",     "clearHistory": true }
```

Server → Client (JSON):

```jsonc
{ "type": "agent_state",     "state": "planning", "task": "Planning 1 action(s)..." }
{ "type": "execution_step",  "step": { "id": "s1", "label": "Open YouTube", "status": "current" } }
{ "type": "activity",        "activity": { "title": "Opened YouTube", "status": "success", "category": "app" } }
{ "type": "action_preview",  "preview": { "title": "Confirm File Deletion", "requiresConfirmation": true } }
{ "type": "speak",           "text": "I've opened YouTube.", "audio": null, "tts": "browser" }
{ "type": "agent_state",     "state": "listening", "task": "Ready for your next command." }
```

---

## 🧪 Manual Test

1. `cd pluto-backend && ./start.sh`
2. `npm run dev` (from repo root)
3. Open http://localhost:3000, press the mic or type a command.
4. Confirm the orb HUD cycles through the loop and PLUTO speaks, then returns
   to LISTENING. Chain another command.

**PLUTO keeps talking and stays ready — command after command. 🎯**
