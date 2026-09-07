@echo off
REM ============================================================
REM PLUTO Backend - Windows launcher (cross-platform parity with start.sh)
REM Uses a virtual environment; runs the fully-local backend.
REM ============================================================
setlocal

echo [PLUTO] Starting backend...

if not exist "venv\Scripts\python.exe" (
  echo [PLUTO] Creating virtual environment...
  python -m venv venv
  if errorlevel 1 goto :error
)

if not exist "venv\installed" (
  echo [PLUTO] Installing dependencies...
  venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 goto :error
  echo installed> "venv\installed"
)

if not exist ".env" (
  echo [PLUTO] No .env found - copying from .env.example
  copy .env.example .env >nul
)

echo [PLUTO] Starting on http://127.0.0.1:8765
venv\Scripts\python.exe run.py
goto :eof

:error
echo [PLUTO] Startup failed - see errors above.
exit /b 1
