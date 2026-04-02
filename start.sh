#!/bin/bash
# Coder's War Room — Start Everything
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=5680
PLIST_DEST="$HOME/Library/LaunchAgents/com.warroom.server.plist"
PID_FILE="/tmp/warroom-server.pid"

echo "==========================================="
echo "  CODER'S WAR ROOM — Starting Up"
echo "==========================================="

# Check if server is already running
if curl -s "http://localhost:$PORT/api/agents" > /dev/null 2>&1; then
    echo "Server already running on port $PORT"
elif [ -f "$PLIST_DEST" ]; then
    echo "Starting server via LaunchAgent..."
    launchctl load "$PLIST_DEST" 2>/dev/null || true
    sleep 2
    echo "Server running (LaunchAgent managed, port $PORT)"
else
    echo "Starting server on port $PORT..."
    cd "$SCRIPT_DIR"
    nohup python3 server.py > /tmp/warroom-server.log 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2
    if curl -s "http://localhost:$PORT/api/agents" > /dev/null 2>&1; then
        echo "Server started (PID: $(cat $PID_FILE))"
    else
        echo "ERROR: Server failed to start. Check /tmp/warroom-server.log"
        exit 1
    fi
fi

# Onboard agents
echo ""
"$SCRIPT_DIR/onboard.sh" "$@"

# Open web UI
echo ""
echo "Opening web UI..."
open "http://localhost:$PORT"
