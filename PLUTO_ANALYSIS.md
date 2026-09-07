# PLUTO — Current State Analysis & Implementation Plan

> Prepared before any code changes. Goal: turn PLUTO into a real standalone,
> fully-local autonomous computer assistant with its own Python intelligence —
> **no OpenAI / GPT / Gemini / Claude / Ollama / LM Studio / OpenRouter / Groq
> or any other external AI/API.**

---

## 1. What PLUTO currently is

PLUTO is a two-part local desktop app:

| Layer | Tech | Location |
|-------|------|----------|
| **Frontend / UI** | Next.js 15 + React 19 + TypeScript + Zustand + Tailwind 4 + framer-motion | `src/` |
| **Backend / brain** | Python 3.11 + FastAPI + Uvicorn + Pydantic | `pluto-backend/` |

**Transport:** browser ↔ Next.js (proxies `/api/backend/*` → `127.0.0.1:8765`)
→ FastAPI. Streaming via WebSocket; a REST fallback shares the same session/context.

### Backend architecture (`pluto-backend/app/`)

- `main.py` — FastAPI app + CORS + routers + `/health`.
- `api/routes_chat.py` — **WebSocket hub** (command/confirm/reject/interrupt/reset) + REST execute/confirm/reset.
- `api/routes_tools.py` — tool introspection + context + intent/recommend endpoints.
- `api/routes_system.py` — read-only metrics/info.
- `api/routes_voice.py` — synthesize / voices / stt-status / transcribe.
- `agent/`
  - `state_machine.py` — robust `IDLE→LISTENING→UNDERSTANDING→THINKING→PLANNING→EXECUTING→VERIFYING→OBSERVING→REASONING→SPEAKING→SUCCESS→ERROR` machine.
  - `session_manager.py` — per-session queue, history, confirmation gate, interrupt.
  - `context_manager.py` — **in-memory** per-session context (apps/browser/files/search/recent-actions).
  - `pattern_orchestrator.py` — **the ACTIVE orchestrator** (deterministic pattern path).
  - `pattern_matcher.py` — keyword/regex + fuzzy (`SequenceMatcher`) matching.
  - `orchestrator.py` — legacy LLM orchestrator (uses `gpt_oss`), currently **not wired in**.
  - `nlu.py` — richer deterministic multi-step `intent_planner` (only used by the mock-LLM planner and the `/intent/analyze` recommendations).
- `tools/` — unified **Tool Registry** + real tools:
  - application, file, system, browser (Playwright/Chromium), messaging, terminal.
  - Every tool is a `TerminalTool` returning a canonical `ToolResult`; every one **verifies** its effect (honest success/failure).
- `core/`
  - `config.py` — `Settings` (env-driven).
  - `security.py` — path sandbox + command classification (`SAFE`/`CONFIRM_REQUIRED`/`BLOCKED`).
  - `logging.py` — structlog.
- `llm/gpt_oss.py` — GPT-OSS 120B client (Groq) **plus a deterministic mock planner**.
- `voice/` — ElevenLabs TTS, local TTS (gTTS/pydub), STT (`faster-whisper` or Google Web Speech).
- `schemas/` — Pydantic models.

### What actually runs (verified)

- `pytest tests/` → **92 passed, 1 skipped** (the pattern-based path).
- `npm run build` → **11 static pages generated, 0 type errors**.
- Tools are genuinely real and sandboxed (screenshot capture w/ image validation, clipboard read-back, volume read-back, browser navigation error detection, file sandbox).

---

## 2. What is broken / inconsistent today

1. **There is no local intelligence.** The two "brains" are either (a) an external
   LLM (Groq/GPT-OSS) or (b) deterministic keyword/regex matching. No TF-IDF, no
   classifier, no entity extraction, no semantic similarity, no training, no
   persisted model, no feedback learning.
2. **Two divergent orchestrators + two NLU systems.** `pattern_orchestrator`
   (active) uses the simple `pattern_matcher`; the richer multi-step `intent_planner`
   in `nlu.py` is *only* exercised by mock-LLM mode and `/intent/analyze`. So
   autonomous multi-step planning ("open browser → search → click result → verify")
   is **not** wired into the active path — the active path runs a single step.
3. **`pattern_matcher` misuse of confidence.** It scores a substring keyword hit as
   `0.90 + priority/100` and does fuzzy similarity against the *entire input*, giving
   misleading confidence and poor intent separation. It also has **no real entity
   extraction** for the active path (it string-mangles arguments).
4. **No durable memory.** `context_manager` is purely in-memory (lost on restart).
   No SQLite. No corrections/success/failure store that could drive learning.
5. **No training / evaluation system.** No dataset → train → evaluate → save model
   → improve from corrections.
6. **No platform abstraction.** Tools hardcode Linux binaries and commands
   (`wmctrl`, `pactl`, `pgrep`, `xdg-open`, `pkill`, `scrot`, …). Windows `.exe`
   and Android could not share this core. The user wants Linux/Windows/Android to
   share one core with platform-specific **adapters**.
7. **No recovery/verification loop in the active path.** `pattern_orchestrator`
   runs one tool and stops. Tool-level `verify` runs, but there is no outer
   observe→reason→re-plan→retry loop.
8. **External voice deps.** ElevenLabs (cloud), gTTS (needs model download/proxy),
   Google Web Speech (internet). Only `faster-whisper` is fully local, and it is
   optional/uninstalled.
9. **Frontend orb is an external Sketchfab iframe** (`PlutoOrb`) — a remote asset,
   not local/offline-safe, and it doesn't reflect intent/plan/confidence.
10. **Bugs / papercuts**
    - `pattern_orchestrator._build_activity` uses `id=f"act_{tool_name}"` → duplicate
      keys in the activity feed.
    - Duplicate names: `session_manager` imports `pattern_orchestrator as
      agent_orchestrator`; `agent/orchestrator.py` (LLM) is orphaned dead weight.
    - Pydantic `class Config` deprecation warnings (should be `ConfigDict`).
    - `security.sanitize_command` returns the command unchanged (no-op).
    - Stale docs (`ARCHITECTURE.md`/README reference `agent/tool_registry.py` and
      GPT-OSS external path).
    - LLM mock `_conversation_context` hack in `gpt_oss.py`; duplicate planner logic.

---

## 3. What should be PRESERVED (do not rewrite)

- The **state machine** and all PLUTO states — it's solid and mirrors the UI.
- The **Tool Registry + `ToolResult`/`SafetyLevel`/`TerminalTool`** contract — this
  is the right seam; keep the modules but add a platform-abstracted execution base.
- Every **tool implementation and its real verification** (filesystem sandbox,
  screenshot validation, clipboard read-back, volume read-back, browser nav error
  detection, app-launch process verify). These are genuinely good and honest.
- The **confirmation gate** and safety classification.
- The **WebSocket/REST transport**, session/context plumbing, and the shared
  session id strategy.
- The **UI identity** (layout, orb concept, command bar, execution panel, states).
- The **existing tests** (they encode correct, honest behavior — keep them green).

---

## 4. Exact implementation plan (incremental, tested after each step)

The build is phased; each phase lands tested and doesn't break the green suite.

### Phase 0 — Report & scaffolding
- [x] This analysis report.
- [x] Add `scikit-learn` (classifier) + SQLite standard lib to the backend; make
      `intelligence` package importable.

### Phase 1 — Local intelligence core (the heart)
- `app/intelligence/` new package:
  - `dataset.py` — PLUTO's own command→intent corpus (+ labels & entity patterns).
  - `classifier.py` — `LocalIntentClassifier`: TF-IDF + linear classifier
    (scikit-learn, no PyTorch unless truly needed); `train`, `predict`, `predict_topk`,
    `evaluate`, `save`, `load` (joblib), confidence via `predict_proba`/decision.
  - `entities.py` — rule + dictionary + regex entity extraction
    (apps, sites, paths/folders, file names, numbers, ordinals, recipients, queries).
  - `similarity.py` — TF-IDF cosine semantic similarity + fuzzy fallback.
  - `pipeline.py` — `PlutoBrain`: **input → intent → entities → context → confidence
    → plan (multi-step) → tool selection → execution (via registry) → observation →
    verification → recovery → result**. Reuses `nlu.intent_planner` for planning and
    enriches it with ML intent + confidence.
  - `memory.py` — SQLite store for sessions, actions, corrections, successes/failures
    (persistent memory + feedback learning source).
  - `trainer.py` — training + eval + save; CLI `python -m app.intelligence.trainer`.
- Tests: `tests/test_intelligence.py` (classifier accuracy, entity extraction,
  memory persistence, pipeline planning).

### Phase 2 — Integrate the brain into the active orchestrator
- Replace the `pattern_matcher.match_command` single-step logic with the
  `PlutoBrain` pipeline in `pattern_orchestrator` (or fold pattern_orchestrator into
  the brain loop), keeping the state machine, confirmation gate, and `ToolResult`
  contract. Add outer verification + recovery/re-plan loop.
- Surface **intent, confidence, and the plan** to the frontend.

### Phase 3 — Persistence + learning
- SQLite memory for context (replace/augment in-memory ContextManager), recording
  every action with success/failure; corrections from user feedback feed the trainer.
- Automatic re-train on corrections + manual trainer CLI.

### Phase 4 — Platform abstraction
- `platform/` base (`Platform` protocol: executable lookup, process, volume,
  clipboard, screenshot, file open) with `linux/` and `windows/` adapters sharing
  the same core; keep existing Linux tool behavior as the reference. Design for a
  future `android/` adapter that only exposes capabilities Android actually has.

### Phase 5 — Fully-local voice
- Preferred local TTS (e.g. `pyttsx3`/`espeak-ng` on Linux) + local STT
  (`faster-whisper`) as the default; keep browser TTS as graceful fallback. No
  external service required for the core loop.

### Phase 6 — UI/UX
- Replace external Sketchfab orb with a local, state-driven animated orb/glow that
  reflects the agent states and the current intent/plan/confidence (listening,
  understanding, planning, executing, waiting, success, error, confirmation).
- Show intent + confidence + plan steps in a clean, minimal way.

### Phase 7 — Packaging & hardening
- Platform abstraction + entry points for Linux `.deb` and Windows `.exe`
  (PyInstaller spec; platform launchers). Android feasibility note in docs.
- Comprehensive logging, error handling, security checks, performance (non-blocking,
  no UI freeze), and an expanded automated test suite.

---

## 5. This session's scope

Per the instruction *"do not try to build everything at once,"* this session
delivers:

- **Phase 0** — this report + scaffolding (`scikit-learn` added; model/db live
  under `~/.pluto`, outside the repo).
- **Phase 1** — the local intelligence core, fully tested:
  `app/intelligence/` (dataset, classifier, entities, similarity, memory, brain,
  trainer) + `tests/test_intelligence.py` (19 tests).
- **Phase 2 (core)** — the brain is wired into the **active** orchestrator
  (`app/agent/pattern_orchestrator.py`): it now understands intent + confidence,
  plans **multi-step** sequences, executes + verifies, recovers from transient
  failures, records outcomes to SQLite, and reports intent/confidence.

Remaining phases (persistence of context, full platform abstraction for
Windows/Android, fully-local voice, UI/UX redesign, `.deb`/`.exe` packaging) are
the next increments. No working code was removed or rewritten; the green suite
went from **92 passed → 111 passed** (all prior tests still green).
