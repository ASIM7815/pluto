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
| Browser | Open URLs, search, reload/fullscreen keys, window management |
| System | Live CPU/RAM/storage metrics, OS info, process list & kill (gated) |
| Terminal | Safe argv execution for normal commands; destructive commands require your confirmation and are blocked if truly dangerous; never a blind shell |
| Assistant | Pattern-based NLU planner: understands "open YouTube and play a song", "create a folder called PLUTO in Projects", "copy 'hello' to clipboard", etc. |
| Voice | Offline TTS via espeak-ng (WAV → webview playback), optional whisper.cpp STT; browser speech fallback |

## Build

Prerequisites (build machine only): Node 20+, Rust stable, and Tauri Linux deps:

```bash
sudo apt-get install libwebkit2gtk-4.1-dev libgtk-3-dev librsvg2-dev \
  libayatana-appindicator3-dev libssl-dev pkg-config
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

## Docs

- `ARCHITECTURE.md` — component map and IPC contract
- `INSTALL.md` — package installation and verification
- `QUICK_START.md` — what to try first
