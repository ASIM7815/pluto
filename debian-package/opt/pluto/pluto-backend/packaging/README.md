# PLUTO Backend Packaging

PLUTO runs **100% locally** — its own on-device scikit-learn brain, SQLite
memory, and offline-first voice. No external AI/API is ever called in the
active path. This folder holds the packaging tooling for Linux and Windows.

## Run from source

```bash
# Linux / macOS
./start.sh            # or: python run.py

# Windows
start.bat             # or: python run.py
```

`run.py` is the canonical entry point:

```bash
python run.py               # 127.0.0.1:8765 (default)
python run.py --preview     # 0.0.0.0:8765, for container/network previews
python run.py --host 0.0.0.0 --port 8765
```

No `.env` or API key is required — local mode is the default.

## Build a standalone binary (PyInstaller)

```bash
cd pluto-backend
./venv/bin/pip install pyinstaller

# Linux
./venv/bin/pyinstaller packaging/pluto-backend.spec

# Windows (from cmd/PowerShell)
venv\Scripts\pip install pyinstaller
venv\Scripts\pyinstaller packaging\pluto-backend-windows.spec
```

Output lands in `dist/pluto-backend/`. The brain models and SQLite DB live in
`~/.pluto` (created on first run), so they survive binary upgrades.

> Excluded optional deps (`playwright`, `SpeechRecognition`, `faster-whisper`,
> `gTTS`) keep the binary lean. The browser Web Speech API stays the graceful
> voice fallback when these aren't bundled.

## Platform feasibility

- **Linux** — full adapter (volume, clipboard, screenshot, process, file-open).
- **Windows** — PowerShell-backed adapter covers the same surface.
- **Android** — honest adapter: only reports capabilities the OS actually has;
  desktop-only operations return `ok=False / UNSUPPORTED` instead of pretending.
