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

status_cmd() {
    local task=""
    local progress=""
    local eta=""
    local blocked=""
    local blocked_reason=""
    local show=false
    local clear=false
    local unblocked=false

    while [ $# -gt 0 ]; do
        case "$1" in
            --progress) progress="$2"; shift 2 ;;
            --eta) eta="$2"; shift 2 ;;
            --blocked)
                blocked="$2"; shift 2
                blocked_reason="$*"; break ;;
            --unblocked) unblocked=true; shift ;;
            --show) show=true; shift ;;
            --clear) clear=true; shift ;;
            *) task="$1"; shift ;;
        esac
    done

    if [ "$show" = true ]; then
        curl -s "$WARROOM_SERVER/api/agents/$WARROOM_AGENT/status" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"Agent:    {d.get('name', '?')}\")
print(f\"Presence: {d.get('presence', '?')}\")
if d.get('activity'): print(f\"Activity: {d['activity']}\")
if d.get('task'): print(f\"Task:     {d['task']}\")
if d.get('progress') is not None: print(f\"Progress: {d['progress']}%\")
if d.get('eta'): print(f\"ETA:      {d['eta']}\")
if d.get('blocked_by'): print(f\"BLOCKED:  by {d['blocked_by']} — {d.get('blocked_reason', '')}\")
if d.get('stalled'): print(f\"STALLED:  {d.get('stalled_minutes', 0)}m on same file\")
if d.get('owns'): print(f\"Owns:     {', '.join(d['owns'][:5])}{'...' if len(d.get('owns',[])) > 5 else ''}\")
if d.get('last_commit'): print(f\"Commit:   {d['last_commit']['hash']} {d['last_commit']['message']}\")
"
        return
    fi

    if [ "$clear" = true ]; then
        curl -s -X POST "$WARROOM_SERVER/api/agents/$WARROOM_AGENT/status" \
            -H "Content-Type: application/json" \
            -d '{"clear": true}' > /dev/null
        echo "Status cleared"
        return
    fi

    if [ "$unblocked" = true ]; then
        curl -s -X POST "$WARROOM_SERVER/api/agents/$WARROOM_AGENT/status" \
            -H "Content-Type: application/json" \
            -d '{"blocked_by": null, "blocked_reason": null}' > /dev/null
        echo "Blocker cleared"
        return
    fi

    # Build JSON payload
    local payload="{"
    local sep=""
    if [ -n "$task" ]; then
        local escaped_task
        escaped_task=$(printf '%s' "$task" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')
        payload="${payload}${sep}\"task\": $escaped_task"
        sep=", "
    fi
    if [ -n "$progress" ]; then
        payload="${payload}${sep}\"progress\": $progress"
        sep=", "
    fi
    if [ -n "$eta" ]; then
        payload="${payload}${sep}\"eta\": \"$eta\""
        sep=", "
    fi
    if [ -n "$blocked" ]; then
        local escaped_reason
        escaped_reason=$(printf '%s' "$blocked_reason" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')
        payload="${payload}${sep}\"blocked_by\": \"$blocked\", \"blocked_reason\": $escaped_reason"
        sep=", "
    fi
    payload="${payload}}"

    if [ "$payload" = "{}" ]; then
        echo "Usage: warroom.sh status 'task' [--progress N] [--eta Nm]"
        echo "       warroom.sh status --blocked <agent> 'reason'"
        echo "       warroom.sh status --unblocked"
        echo "       warroom.sh status --clear"
        echo "       warroom.sh status --show"
        return
    fi

    curl -s -X POST "$WARROOM_SERVER/api/agents/$WARROOM_AGENT/status" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null
    echo "Status updated"
}

roll_call() {
    echo "Roll call sent. Waiting 10s for responses..."
    local result
    result=$(curl -s -X POST "$WARROOM_SERVER/api/roll-call" --max-time 15)
    echo "$result" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    total = d.get('total', 0)
    responded = d.get('responded', [])
    missing = d.get('missing', [])
    print(f\"{len(responded)}/{total} responded: {', '.join(responded) if responded else 'none'}\")
    if missing:
        print(f\"Missing: {', '.join(missing)}\")
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
    status)
        shift
        status_cmd "$@"
        ;;
    deboard)
        shift
        deboard_agent "$@"
        ;;
    reboard)
        shift
        reboard_agent "$@"
        ;;
    roll-call)
        shift
        roll_call
        ;;
    attach)
        shift
        AGENT="${1:-$WARROOM_AGENT}"
        SESSION="warroom-$AGENT"
        if ! tmux has-session -t "$SESSION" 2>/dev/null; then
            echo "Error: No session '$SESSION'. Agent not onboarded."
            exit 1
        fi
        # Get the agent's working directory from tmux pane
        AGENT_DIR=$(tmux display-message -t "$SESSION" -p '#{pane_current_path}' 2>/dev/null || echo "$HOME")
        # Set window title for Warp tab
        tmux rename-window -t "$SESSION" "$AGENT"
        # Create launcher IN the project directory so Warp file browser opens there
        LAUNCHER="${AGENT_DIR}/.warroom-attach.sh"
        cat > "$LAUNCHER" << LAUNCH_EOF
#!/bin/bash
# War Room — $AGENT
cd $AGENT_DIR
printf '\033]0;$AGENT — War Room\007'
exec tmux attach -t $SESSION
LAUNCH_EOF
        chmod +x "$LAUNCHER"
        # Try Warp first, fall back to Terminal.app
        if [ -d "/Applications/Warp.app" ]; then
            open -a Warp "$LAUNCHER" && echo "Opened $AGENT in Warp (dir: $AGENT_DIR)"
        else
            osascript -e "tell application \"Terminal\"
                activate
                do script \"cd $AGENT_DIR && tmux attach -t $SESSION\"
            end tell" 2>/dev/null && echo "Opened $AGENT in Terminal.app"
        fi || echo "Manual: tmux attach -t $SESSION"
        ;;
    *)
        echo "Coder's War Room — Agent CLI"
        echo ""
        echo "Usage:"
        echo "  warroom.sh post [--to agent] message   Send a message"
        echo "  warroom.sh history [--count N]          Show all recent messages"
        echo "  warroom.sh mentions [--count N]         Show messages for me + @all"
        echo "  warroom.sh status 'task' [--progress N] [--eta Nm]  Set status"
        echo "  warroom.sh status --blocked <agent> 'reason'        Set blocker"
        echo "  warroom.sh status --unblocked                       Clear blocker"
        echo "  warroom.sh status --clear                           Clear all status"
        echo "  warroom.sh status --show                            Show your card"
        echo "  warroom.sh roll-call                         Check who's alive
  warroom.sh deboard [agent]               Leave war room (keep working)"
        echo "  warroom.sh reboard [agent]               Rejoin the war room"
        echo "  warroom.sh attach <agent>                Pop out agent in Terminal.app"
        echo ""
        echo "Agent identity: $WARROOM_AGENT"
        echo "Server: $WARROOM_SERVER"
        ;;
esac
