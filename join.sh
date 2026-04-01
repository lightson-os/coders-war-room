#!/bin/bash
# Coder's War Room — Join as an agent
# Usage: ~/coders-war-room/join.sh <agent-name>
# Example: ~/coders-war-room/join.sh supervisor

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_URL="http://localhost:5680"
AGENT_NAME="$1"

if [ -z "$AGENT_NAME" ]; then
    echo "Usage: ~/coders-war-room/join.sh <agent-name>"
    echo "Available: supervisor, phase-1..6, git-agent"
    exit 1
fi

TARGET_SESSION="warroom-$AGENT_NAME"

# Get current tmux session name
CURRENT_SESSION=$(tmux display-message -p '#S' 2>/dev/null || true)
if [ -z "$CURRENT_SESSION" ]; then
    echo "ERROR: Not running inside tmux. Start this terminal in tmux first:"
    echo "  tmux new-session -s $TARGET_SESSION"
    exit 1
fi

# Check if the target session name is already taken by ANOTHER session
if [ "$CURRENT_SESSION" != "$TARGET_SESSION" ]; then
    if tmux has-session -t "$TARGET_SESSION" 2>/dev/null; then
        echo "WARNING: tmux session '$TARGET_SESSION' already exists (stale from previous run?)"
        echo "Killing stale session..."
        tmux kill-session -t "$TARGET_SESSION"
        sleep 0.5
    fi
    tmux rename-session -t "$CURRENT_SESSION" "$TARGET_SESSION"
    echo "Renamed tmux session: $CURRENT_SESSION -> $TARGET_SESSION"
fi

# Fetch role from server
ROLE=$(curl -s "$SERVER_URL/api/agents" 2>/dev/null | python3 -c "
import sys, json
try:
    agents = json.load(sys.stdin)
    match = [a for a in agents if a['name'] == '$AGENT_NAME']
    print(match[0]['role'] if match else 'Agent')
except: print('Agent')
" 2>/dev/null || echo "Agent")

# Announce to war room
curl -s -X POST "$SERVER_URL/api/messages" \
    -H "Content-Type: application/json" \
    -d "{\"sender\": \"system\", \"content\": \"$AGENT_NAME has joined the war room\", \"type\": \"system\"}" \
    > /dev/null 2>&1 || true

# Output the brief protocol
cat << EOF

======================================
  JOINED: $AGENT_NAME
  ROLE: $ROLE
======================================

WAR ROOM COMMANDS:
  ~/coders-war-room/warroom.sh post "message"
  ~/coders-war-room/warroom.sh post --to <agent> "message"
  ~/coders-war-room/warroom.sh history

PROTOCOL:
  [WARROOM @$AGENT_NAME] = directed at you, MUST act
  [WARROOM] = broadcast, respond only if relevant
  [WARROOM SYSTEM] = info only, ignore

EOF
