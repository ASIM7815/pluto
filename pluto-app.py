#!/usr/bin/env python3
"""
PLUTO Desktop Application Wrapper
Loads the built static frontend in a native webview window.
Serves via local HTTP server to properly handle static assets.
"""
import os
import sys
import subprocess
import time
import threading
from bottle import Bottle, static_file

OPT_DIR = "/opt/pluto"
BACKEND_DIR = os.path.join(OPT_DIR, "pluto-backend")
OUT_DIR = os.path.join(OPT_DIR, "out")
PORT = 8899

app = Bottle()

# Serve static files from Next.js out directory
@app.route('/')
def index():
    return static_file('index.html', root=OUT_DIR)

@app.route('/<filepath:path>')
def serve_static(filepath):
    return static_file(filepath, root=OUT_DIR)

def start_server():
    """Start the local HTTP server in background thread"""
    app.run(host='127.0.0.1', port=PORT, quiet=True)

def start_backend():
    """Optional: start Python backend if available"""
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
        time.sleep(2)
        return proc
    except Exception as e:
        print(f"[PLUTO] Backend start skipped: {e}", file=sys.stderr)
        return None

def main():
    # Start local HTTP server in background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Give server time to start
    time.sleep(1)
    
    # Attempt to start backend if installed
    backend_proc = start_backend()

    # Open native window pointing to local server
    url = f"http://127.0.0.1:{PORT}"

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

    # Cleanup
    if backend_proc is not None:
        try:
            backend_proc.terminate()
        except Exception:
            pass

if __name__ == "__main__":
    main()
