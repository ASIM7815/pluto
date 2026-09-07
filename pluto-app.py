#!/usr/bin/env python3
"""
PLUTO Desktop Application Wrapper
Loads the built static frontend in a native webview window.
Optionally starts the Python FastAPI backend if available.
"""
import os
import sys
import subprocess
import time

OPT_DIR = "/opt/pluto"
BACKEND_DIR = os.path.join(OPT_DIR, "pluto-backend")
OUT_DIR = os.path.join(OPT_DIR, "out")

def start_backend():
    venv_python = os.path.join(BACKEND_DIR, "venv", "bin", "python")
    if not os.path.isfile(venv_python):
        return None
    try:
        proc = subprocess.Popen(
            [venv_python, "-m", "app.main"],
            cwd=BACKEND_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        # Give backend a moment to initialize
        time.sleep(2)
        return proc
    except Exception as e:
        print(f"[PLUTO] Backend start skipped: {e}", file=sys.stderr)
        return None

def main():
    # Attempt to start backend if installed
    backend_proc = start_backend()

    # Load the static production build
    url = f"file://{OUT_DIR}/index.html"
    if not os.path.isfile(os.path.join(OUT_DIR, "index.html")):
        # Fallback to out/index.html relative path
        url = "file:///opt/pluto/out/index.html"

    import webview
    window = webview.create_window(
        "PLUTO",
        url,
        width=1280,
        height=900,
        resizable=True,
        maximized=False,
    )
    webview.start()

    if backend_proc is not None:
        try:
            backend_proc.terminate()
        except Exception:
            pass

if __name__ == "__main__":
    main()
