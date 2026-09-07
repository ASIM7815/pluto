#!/bin/bash

# PLUTO AI Assistant Startup Script

PLUTO_DIR="/opt/pluto"
BACKEND_DIR="$PLUTO_DIR/pluto-backend"

echo "Starting PLUTO AI Assistant..."

# Start backend
cd "$BACKEND_DIR"
source venv/bin/activate
python -m app.main &
BACKEND_PID=$!

# Wait for backend to start
echo "Starting backend..."
sleep 3

# Start frontend
cd "$PLUTO_DIR"
if [ -f "package.json" ]; then
    echo "Starting frontend..."
    npm run dev &
    FRONTEND_PID=$!
    
    # Wait for frontend to start
    sleep 3
    
    # Open browser
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open http://localhost:3000
    elif command -v google-chrome >/dev/null 2>&1; then
        google-chrome http://localhost:3000
    elif command -v firefox >/dev/null 2>&1; then
        firefox http://localhost:3000
    fi
    
    echo ""
    echo "✅ PLUTO AI Assistant is running!"
    echo "   Backend: http://localhost:8765"
    echo "   Frontend: http://localhost:3000"
    echo ""
    echo "Press Ctrl+C to stop PLUTO"
    
    # Wait for processes
    wait $BACKEND_PID $FRONTEND_PID
else
    echo "✅ PLUTO Backend is running on http://localhost:8765"
    echo "   (Frontend not built - run 'npm install && npm run dev' manually)"
    wait $BACKEND_PID
fi
