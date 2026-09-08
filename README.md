# PLUTO

**PLUTO** is a native Linux desktop AI assistant: a React/Next.js UI running inside a Tauri window backed by a real Rust engine. It controls your machine directly — files, applications, browser, screenshots, clipboard, volume, processes and safe command execution — with a local, pattern-based intelligence core. No Python, no FastAPI, no PyWebView, no localhost servers, no cloud dependency.

## Architecture

```
Next.js/React UI (static export, loaded by the native webview)
      ↓  Tauri IPC (invoke/events, no HTTP)
Rust backend (src-tauri)
      ↓
Linux OS (file system, X11/Wayland, clipboard, processes, apps)
```

- **Frontend**: `src/` — React 19 + Next.js 15 static export (unchanged PLUTO UI, orb, animations).
- **Backend**: `src-tauri/` — Rust/Tauri v2: NLU planner, tool executor, system tools.
- **Package**: `Pluto_*.deb` — normal Linux desktop app with `.desktop` entry and icon.

## Features (all real, all on-device)

| Category | What PLUTO does |
| --- | --- |
| Screenshots | Native xcap (X11) + grim/gnome-screenshot/scrot/spectacle/imagemagick fallbacks; full, window, and selectable regions; X11 & Wayland |
| Clipboard | Rust `arboard` — native X11/Wayland clipboard (no xclip/pyperclip) |
| Files | Create/read/write/list/find/copy/move/delete/open files & folders — sandboxed to the home directory with traversal protection |
| Applications | Launch, close, switch and list apps (which/pkill/wmctrl) |
| Browser | Open the system default browser (xdg-open / xdg-settings / $BROWSER with clear errors), open any URL or site, engine-aware web search |
| System | Live CPU/RAM/storage metrics, OS info, process list & kill (gated) |
| Terminal | Safe argv execution for normal commands; destructive commands require your confirmation and are blocked if truly dangerous; never a blind shell |
| Assistant | Deterministic intent parser + conversational context: "Search Iron Man on Google", "Google Iron Man", "open GitHub", "open example.com", "play X on YouTube", then "now search Avengers" follows the last platform |
| Voice input | Native microphone capture (Rust/cpal, no Web Speech API, no HTTPS) with lightweight VAD; optional whisper.cpp transcription with an external model (~/.cache/pluto) |
| Voice output | Auto-detected best free engine: Piper (neural) → pico2wave → espeak-ng female (+f3) → espeak → browser speech fallback. Never crashes without TTS |

## Build

Prerequisites (build machine only): Node 20+, Rust stable, and Tauri Linux deps:

```bash
sudo apt-get install libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev \
  libayatana-appindicator3-dev libssl-dev pkg-config libasound2-dev \
  libclang-dev clang
npm install
npm run build:deb        # -> dist/Pluto_1.0.0_amd64.deb
```

`npm run tauri:dev` runs the live desktop app during development.

## Install

```bash
sudo apt install ./dist/Pluto_1.0.0_amd64.deb   # or dpkg -i
pluto                                            # launch from terminal or the app menu
```

After installation nothing else is needed: no Python, no Node, no pip/venv, no server. See `INSTALL.md`.

## Verification

The GitHub Actions workflow (`.github/workflows/build.yml`) builds and tests
every push to this branch:

1. TypeScript type check + `next build` static export
2. `cargo test` — NLU routing, terminal safety, voice
3. Tauri release build → `Pluto_1.0.0_amd64.deb`
4. **Installs the real `.deb` with apt** (resolves its `Depends`), verifies
   `/usr/bin/pluto`, `/usr/share/applications/Pluto.desktop` (`Exec=pluto`)
   and the hicolor icons, launches the installed app under Xvfb for 12 s and
   screenshots it
5. Dev-binary GUI smoke under Xvfb (app alive 12 s + screenshot)
6. Rust smoke tests: real clipboard round-trip, X11 screenshot capture, and
   the full file tool chain (create/read/list/copy/move/find/delete)
7. Uploads the `.deb` as the `pluto-deb` artifact and commits it back to
   `dist/Pluto_1.0.0_amd64.deb`

Latest build: `Pluto_1.0.0_amd64.deb`
SHA-256: `3e72991ebca69bf847227d1fee50752ccd62c0f38b6f904e854b7eaa2358efb3`

## Docs

- `ARCHITECTURE.md` — component map and IPC contract
- `INSTALL.md` — package installation and verification
- `QUICK_START.md` — what to try first
