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
    *)
        echo "Coder's War Room — Agent CLI"
        echo ""
        echo "Usage:"
        echo "  warroom.sh post [--to agent] message   Send a message"
        echo "  warroom.sh history [--count N]          Show all recent messages"
        echo "  warroom.sh mentions [--count N]         Show messages for me + @all"
        echo ""
        echo "Agent identity: $WARROOM_AGENT"
        echo "Server: $WARROOM_SERVER"
        ;;
esac
