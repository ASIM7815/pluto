"""Canonical PLUTO backend entry point (cross-platform).

Used directly (``python run.py``), packaged with PyInstaller for Linux/Windows,
or as the target for the platform launchers. Runs the local-only FastAPI app
with PLUTO's own on-device intelligence - no external AI/API.

Usage:
    python run.py                # host/port from env (default 127.0.0.1:8765)
    python run.py --preview      # bind 0.0.0.0 (for network/container previews)
    python run.py --host 0.0.0.0 --port 8765
"""
from __future__ import annotations

import argparse
import os

from app.core.config import settings


def main() -> None:
    import uvicorn

    # FastAPI app object refuses to be imported twice under PyInstaller's
    # re-dispatch; import once and hand uvicorn the module path.
    parser = argparse.ArgumentParser(description="Start the PLUTO backend")
    parser.add_argument("--host", default=None, help="Bind host (default from env)")
    parser.add_argument("--port", type=int, default=None, help="Bind port (default from env)")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Bind 0.0.0.0 for remote/container preview",
    )
    args = parser.parse_args()

    host = args.host or (
        "0.0.0.0" if args.preview else settings.pluto_backend_host
    )
    port = args.port or settings.pluto_backend_port

    # Ensure dev auto-reload stays off when frozen, so the packaged binary is
    # a stable long-running server.
    reload_enabled = settings.pluto_env == "development" and not getattr(
        os, "environ", {}
    ).get("PLUTO_FROZEN")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=reload_enabled,
        log_level=settings.pluto_log_level.lower(),
    )


if __name__ == "__main__":
    main()
