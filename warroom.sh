#!/bin/bash
# Coder's War Room — Agent CLI
# Usage:
#   warroom.sh post "message"                    # broadcast
#   warroom.sh post --to <agent> "message"       # direct message
#   warroom.sh history                            # last 20 messages
#   warroom.sh history --count 50                 # last 50 messages

WARROOM_SERVER="${WARROOM_SERVER_URL:-http://localhost:5680}"
# Auto-detect identity: env var > tmux session name > unknown
if [ -n "$WARROOM_AGENT_NAME" ]; then
    WARROOM_AGENT="$WARROOM_AGENT_NAME"
else
    WARROOM_AGENT=$(tmux display-message -p '#S' 2>/dev/null | sed 's/^warroom-//' || echo "unknown")
fi

post_message() {
    local target="all"
    if [ "$1" = "--to" ]; then
        target="$2"
        shift 2
    fi
    local message="$*"

    if [ -z "$message" ]; then
        echo "Error: no message provided"
        echo "Usage: warroom.sh post [--to agent] message"
        return 1
    fi

    # Escape message content for JSON using Python
    local escaped
    escaped=$(printf '%s' "$message" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "$WARROOM_SERVER/api/messages" \
        -H "Content-Type: application/json" \
        -d "{\"sender\": \"$WARROOM_AGENT\", \"target\": \"$target\", \"content\": $escaped}")

    local http_code
    http_code=$(echo "$response" | tail -1)
    local body
    body=$(echo "$response" | python3 -c 'import sys; lines=sys.stdin.read().splitlines(); print("\n".join(lines[:-1]))')

    if [ "$http_code" = "200" ]; then
        echo "OK — message sent"
    else
        echo "Error ($http_code): $body"
        return 1
    fi
}

show_history() {
    local count=20
    if [ "$1" = "--count" ]; then
        count="$2"
    fi

    curl -s "$WARROOM_SERVER/api/messages?limit=$count" | python3 -c "
import sys, json
try:
    msgs = json.load(sys.stdin)
    for m in msgs:
        ts = m['timestamp'][:19].replace('T', ' ')
        tag = f' @{m[\"target\"]}' if m['target'] != 'all' else ''
        prefix = f'[{ts}]{tag} {m[\"sender\"]}'
        print(f'{prefix}: {m[\"content\"]}')
except Exception as e:
    print(f'Error reading messages: {e}', file=sys.stderr)
"
}

show_mentions() {
    local count=50
    if [ "$1" = "--count" ]; then
        count="$2"
    fi

    curl -s "$WARROOM_SERVER/api/messages?limit=$count" | python3 -c "
import sys, json
try:
    agent = '$WARROOM_AGENT'
    msgs = json.load(sys.stdin)
    for m in msgs:
        if m['target'] == agent or m['target'] == 'all':
            ts = m['timestamp'][:19].replace('T', ' ')
            tag = f' @{m[\"target\"]}' if m['target'] != 'all' else ''
            prefix = f'[{ts}]{tag} {m[\"sender\"]}'
            print(f'{prefix}: {m[\"content\"]}')
except Exception as e:
    print(f'Error: {e}', file=sys.stderr)
"
}

deboard_agent() {
    local agent="${1:-$WARROOM_AGENT}"
    local resp
    resp=$(curl -s -w "\n%{http_code}" -X POST "$WARROOM_SERVER/api/agents/$agent/deboard")
    local code
    code=$(echo "$resp" | tail -1)
    if [ "$code" = "200" ]; then
        echo "De-boarded from the war room. Session still alive — keep working."
        echo "Re-board anytime: warroom.sh reboard"
    else
        echo "Error: $resp"
    fi
}

reboard_agent() {
    local agent="${1:-$WARROOM_AGENT}"
    local resp
    resp=$(curl -s -w "\n%{http_code}" -X POST "$WARROOM_SERVER/api/agents/$agent/reboard")
    local code
    code=$(echo "$resp" | tail -1)
    if [ "$code" = "200" ]; then
        echo "Re-boarded to the war room. Messages will be delivered again."
    else
        echo "Error: $resp"
    fi
}

case "$1" in
    post)
        shift
        post_message "$@"
        ;;
    history)
        shift
        show_history "$@"
        ;;
    mentions)
        shift
        show_mentions "$@"
        ;;
    deboard)
        shift
        deboard_agent "$@"
        ;;
    reboard)
        shift
        reboard_agent "$@"
        ;;
    *)
        echo "Coder's War Room — Agent CLI"
        echo ""
        echo "Usage:"
        echo "  warroom.sh post [--to agent] message   Send a message"
        echo "  warroom.sh history [--count N]          Show all recent messages"
        echo "  warroom.sh mentions [--count N]         Show messages for me + @all"
        echo "  warroom.sh deboard [agent]               Leave war room (keep working)"
        echo "  warroom.sh reboard [agent]               Rejoin the war room"
        echo ""
        echo "Agent identity: $WARROOM_AGENT"
        echo "Server: $WARROOM_SERVER"
        ;;
esac
