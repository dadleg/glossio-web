#!/bin/bash
# Development startup script - runs both backend and Electron frontend

set -e

cd "$(dirname "$0")/.."
PROJECT_ROOT=$(pwd)

echo "=== Glossio Development Mode ==="
echo ""

# Check if backend is already running
if curl -s http://127.0.0.1:5000/health > /dev/null 2>&1; then
    echo "Backend already running on port 5000"
else
    echo "Starting backend..."
    cd "$PROJECT_ROOT"
    source .venv/bin/activate
    python run.py &
    BACKEND_PID=$!
    echo "Backend PID: $BACKEND_PID"
    
    # Wait for backend
    echo "Waiting for backend to be ready..."
    for i in {1..30}; do
        if curl -s http://127.0.0.1:5000/health > /dev/null 2>&1; then
            echo "Backend is ready!"
            break
        fi
        sleep 0.5
    done
fi

echo ""
echo "Starting Electron..."
cd "$PROJECT_ROOT/frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install
fi

npm start

# Cleanup
if [ -n "$BACKEND_PID" ]; then
    echo "Stopping backend..."
    kill $BACKEND_PID 2>/dev/null || true
fi
