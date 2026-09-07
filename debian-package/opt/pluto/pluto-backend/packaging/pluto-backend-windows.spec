# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the PLUTO backend (Windows).

Build:
    cd pluto-backend
    venv\Scripts\pip install pyinstaller
    venv\Scripts\pyinstaller packaging\pluto-backend-windows.spec

Output: dist\pluto-backend\pluto-backend.exe. Same fully-local FastAPI app.
"""
import os

from PyInstaller.utils.hooks import collect_submodules

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
