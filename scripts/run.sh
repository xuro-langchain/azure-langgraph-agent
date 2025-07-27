#!/bin/bash
set -e

# Create log directories if they don't exist
mkdir -p backend/logs frontend/logs

# Get datetime for log filenames
LOG_TIME=$(date '+%Y-%m-%d_%H-%M-%S')
BACKEND_LOG="backend/logs/backend_$LOG_TIME.log"
FRONTEND_LOG="frontend/logs/frontend_$LOG_TIME.log"

# Start backend (langgraph dev) in background
if pgrep -f "langgraph dev" > /dev/null; then
  echo "Backend already running. Skipping backend start."
else
  echo "Starting backend (langgraph dev)..."
  source .venv/bin/activate
  nohup langgraph dev --no-browser > "$BACKEND_LOG" 2>&1 &
  deactivate
fi

# Start frontend (npm run dev) in background
cd frontend
if pgrep -f "next dev" > /dev/null; then
  echo "Frontend already running. Skipping frontend start."
else
  echo "Starting frontend (npm run dev)..."
  nohup npm run dev > "../$FRONTEND_LOG" 2>&1 &
fi
cd ..

# Wait a moment for servers to start
sleep 3

# Open browser to localhost:3000
if which open > /dev/null; then
  open http://localhost:3000
elif which xdg-open > /dev/null; then
  xdg-open http://localhost:3000
else
  echo "Please open http://localhost:3000 in your browser."
fi

echo "\nBackend and frontend should now be running! Logs: $BACKEND_LOG, $FRONTEND_LOG" 