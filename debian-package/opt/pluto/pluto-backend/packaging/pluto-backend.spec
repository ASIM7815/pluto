# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the PLUTO backend (Linux).

Build:
    cd pluto-backend
    ./venv/bin/pip install pyinstaller
    ./venv/bin/pyinstaller packaging/pluto-backend.spec

Output: dist/pluto-backend (a single-file executable). It serves the same
fully-local FastAPI app on 127.0.0.1:8765 (or --host/--port/--preview).

Notes:
  * PLUTO's on-device brain + SQLite memory live under ~/.pluto (created on
    first run), NOT inside the bundle, so models persist across upgrades.
  * External optional deps (playwright, SpeechRecognition, faster-whisper,
    gTTS) are intentionally excluded to keep the binary small; the browser Web
    Speech API remains the graceful fallback.
"""
import os

from PyInstaller.utils.hooks import collect_submodules

# Capture the runtime location of the skynet model / dotenv so frozen binary
# can still locate things relative to its own bundle.
hiddenimports = (
    collect_submodules("app")
    + ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto"]
)

a = Analysis(
    ["run.py"],
    pathex=[os.path.abspath("..")],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "playwright",
        "speech_recognition",
        "faster_whisper",
        "gtts",
        "pydub",
        "tkinter",
        "matplotlib",
        "IPython",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pluto-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    name="pluto-backend",
)
