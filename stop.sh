#!/bin/bash
# Coder's War Room — Stop Everything

echo "==========================================="
echo "  CODER'S WAR ROOM — Shutting Down"
echo "==========================================="

# Kill warroom tmux sessions
echo "Killing agent sessions..."
tmux list-sessions 2>/dev/null | grep "^warroom-" | cut -d: -f1 | while read -r session; do
    echo "  Killing: $session"
    tmux kill-session -t "$session" 2>/dev/null || true
done

# Stop server — LaunchAgent first, then PID file
PLIST_DEST="$HOME/Library/LaunchAgents/com.warroom.server.plist"
PID_FILE="/tmp/warroom-server.pid"

if [ -f "$PLIST_DEST" ] && launchctl list 2>/dev/null | grep -q com.warroom.server; then
    echo "Stopping server (LaunchAgent)..."
    launchctl bootout "gui/$(id -u)" com.warroom.server 2>/dev/null || true
    echo "Server stopped"
elif [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping server (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        echo "Server stopped"
    else
        echo "PID $PID not running"
        rm -f "$PID_FILE"
    fi
else
    echo "No server process found"
fi

echo ""
echo "War Room shut down."
