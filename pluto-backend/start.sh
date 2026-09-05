#!/bin/bash
# PLUTO Backend Startup Script

echo "🚀 Starting PLUTO Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Check if requirements are installed
if [ ! -f "venv/installed" ]; then
    echo "📥 Installing dependencies..."
    pip install -r requirements.txt
    touch venv/installed
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "⚙️  Please edit .env and add your API keys!"
    exit 1
fi

# Start FastAPI backend
echo "✅ Starting PLUTO Agent on http://127.0.0.1:8765"
python -m app.main
