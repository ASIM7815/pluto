#!/bin/bash
# PLUTO Backend Startup Script (Linux/macOS)
# Runs the fully-local backend - no external AI/API, no API key required.
set -e

echo "🚀 Starting PLUTO Backend..."

if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate

if [ ! -f "venv/installed" ]; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
    touch venv/installed
fi

# .env is optional in local mode (defaults are fully offline).
if [ ! -f ".env" ]; then
    echo "ℹ️  No .env found - using fully-local defaults (no API keys needed)."
fi

# Optional: pass --preview to expose on 0.0.0.0 (container/network preview).
echo "✅ Starting PLUTO Agent (local-intelligence, NO external AI/API)"
exec python run.py "$@"
