#!/bin/bash
set -e

# Kill backend (langgraph dev)
BACKEND_PIDS=$(pgrep -f "langgraph dev")
if [ -n "$BACKEND_PIDS" ]; then
  echo "Killing backend (langgraph dev) processes: $BACKEND_PIDS"
  kill $BACKEND_PIDS
else
  echo "No backend (langgraph dev) process found."
fi

# Kill frontend (next dev)
FRONTEND_PIDS=$(pgrep -f "next dev")
if [ -n "$FRONTEND_PIDS" ]; then
  echo "Killing frontend (next dev) processes: $FRONTEND_PIDS"
  kill $FRONTEND_PIDS
else
  echo "No frontend (next dev) process found."
fi

echo "Shutdown complete." 