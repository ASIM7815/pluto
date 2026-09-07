# PLUTO Architecture (Tauri + Rust)

## Runtime architecture

```
┌──────────────────────────────────────────────────────────┐
│  Tauri window (WebKitGTK)                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Next.js/React UI  (static export in ../out)        │  │
│  │  - PlutoOrb / animations / CommandBar / Chat       │  │
│  │  - src/services/{ipc,ai,system,voice,tauri}.ts     │  │
│  └──────────────────┬─────────────────────────────────┘  │
│                     │  @tauri-apps/api                 │
│                     │  invoke("pluto_*") + listen(...) │
│                     ▼                                   │
│  Rust backend (pluto binary)                            │
│   - commands.rs        Tauri command surface            │
│   - assistant.rs       orchestrator + event streaming   │
│   - nlu.rs             deterministic intent planner     │
│   - tools/*            real OS tool implementations     │
│   - state.rs           session/confirmation state       │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
                 Linux OS (X11/Wayland)
```

There is **no HTTP server at runtime**. The webview talks to Rust over Tauri IPC only (ports 8899/8765 are gone).

## Frontend ↔ Rust contract

Events (Rust → UI, event name `pluto-event`):

| type | payload |
| --- | --- |
| `agent_state` | `{state, task?, error?, data?: {intent, confidence, recommended_tools, response}}` |
| `execution_step` | `{step: {id, label, status, detail?}}` |
| `activity` | `{activity: {id, title, description, timestamp, status, category}}` |
| `action_preview` | `{preview: {type, title, path?, content?, requiresConfirmation}}` |
| `speak` | `{text, audio?, tts}` |
| `error` | `{error}` |

Commands (UI → Rust, `invoke`):

- Session: `pluto_execute_command`, `pluto_interrupt`, `pluto_reset`, `pluto_confirm`, `pluto_reject`
- System: `pluto_get_system_metrics`, `pluto_get_system_stats`, `pluto_get_system_info`
- OS: `pluto_take_screenshot`, `pluto_set_clipboard`, `pluto_get_clipboard`, `pluto_set_volume`, `pluto_get_volume`, `pluto_get_processes`, `pluto_kill_process`, `pluto_open_url`, `pluto_launch_application`, `pluto_open_file`, `pluto_open_folder`, `pluto_create_folder`, `pluto_create_file`, `pluto_read_file`, `pluto_list_directory`, `pluto_delete_file`, `pluto_copy_file`, `pluto_move_file`, `pluto_find_files`, `pluto_execute_terminal`, `pluto_send_message`
- Voice: `pluto_tts_synthesize`, `pluto_tts_voices`, `pluto_stt_status`, `pluto_stt_transcribe`

## Command flow

1. `pluto_execute_command(command)` → `assistant::run`
2. NLU (`nlu.rs`) plans `Vec<PlanItem>` (tool steps + conversational text)
3. Orchestrator streams `understanding → thinking → planning` with intent/confidence/recommended tools
4. For each step: `execution_step(current)`; CONFIRM-required tools (delete/move/kill/terminal-dangerous/message) emit `action_preview` and wait for `pluto_confirm`/`pluto_reject`
5. Tool executes in a blocking task (never blocks the UI); `execution_step(completed|error)` + `activity` stream
6. Success/error text is spoken (`speak` with local TTS audio or browser fallback) and the loop returns to `listening`

## Security

- Filesystem: all paths resolved and validated against the home directory; traversal and system-root writes rejected.
- Terminal: pattern classification → `SAFE` runs as argv (no shell); `CONFIRM_REQUIRED` waits for the user; `BLOCKED` patterns (rm -rf /, dd, mkfs, fork bomb...) are never run. Shell metacharacters are only interpreted after explicit approval and always under a 45s timeout.
- Confirmation gate for destructive tools; no root execution; no blind shell strings.
- Clipboard/screenshot: native Rust crates (`arboard`, `xcap`) with graceful fallbacks per compositor.
