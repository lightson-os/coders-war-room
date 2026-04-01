#!/bin/bash
# Coder's War Room — Agent Onboarding
# Creates tmux sessions, starts Claude Code, injects agent identity.
#
# Usage:
#   ./onboard.sh                      # Onboard all auto_onboard agents
#   ./onboard.sh phase-1 phase-2      # Onboard specific agents only
#   ./onboard.sh --force phase-1      # Force re-onboard (kills active session)
#   ./onboard.sh --all                # Include agents with auto_onboard: false

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"
WARROOM_SH="$SCRIPT_DIR/warroom.sh"
SERVER_URL="http://localhost:5680"
FORCE=false
INCLUDE_MANUAL=false

# Parse flags
POSITIONAL=()
for arg in "$@"; do
    case "$arg" in
        --force) FORCE=true ;;
        --all) INCLUDE_MANUAL=true ;;
        *) POSITIONAL+=("$arg") ;;
    esac
done

get_config() {
    python3 -c "
import yaml, json
with open('$CONFIG_FILE') as f:
    config = yaml.safe_load(f)
print(json.dumps(config))
"
}

CONFIG_JSON=$(get_config)
PROJECT_PATH=$(echo "$CONFIG_JSON" | python3 -c "import sys,json,os; print(os.path.expanduser(json.load(sys.stdin)['project_path']))")

get_agents() {
    local filter="$1"
    local include_manual="$2"
    echo "$CONFIG_JSON" | python3 -c "
import sys, json
config = json.load(sys.stdin)
agents = config.get('agents', [])
filter_names = '$filter'.split() if '$filter' else []
include_manual = '$include_manual' == 'true'
for a in agents:
    # If specific agents requested, include them regardless of auto_onboard
    if filter_names:
        if a['name'] in filter_names:
            print(f\"{a['name']}|{a['tmux_session']}|{a['role']}\")
    else:
        # No filter: respect auto_onboard (default True)
        auto = a.get('auto_onboard', True)
        if auto or include_manual:
            print(f\"{a['name']}|{a['tmux_session']}|{a['role']}\")
        else:
            import sys as s
            print(f\"  Skipping {a['name']} (auto_onboard: false — use join.sh or --all)\", file=s.stderr)
"
}

wait_for_prompt() {
    local session="$1"
    local max_wait=30
    local waited=0

    echo "  Waiting for Claude Code to start..."
    while [ $waited -lt $max_wait ]; do
        sleep 2
        waited=$((waited + 2))

        local content
        content=$(tmux capture-pane -t "$session" -p -S -15 2>/dev/null || true)

        # Claude Code's TUI shows ❯ (U+276F) when waiting for input
        if echo "$content" | grep -q '❯'; then
            echo "  Claude Code is ready (${waited}s)"
            return 0
        fi
        # Fallback: check for Claude Code banner
        if echo "$content" | grep -q 'Claude Code'; then
            echo "  Claude Code detected (${waited}s)"
            sleep 2  # Give it a moment to fully initialize
            return 0
        fi
    done

    echo "  WARNING: Timed out waiting for Claude Code (${max_wait}s). Sending onboarding anyway."
    return 0
}

check_session_active() {
    # Returns 0 if session exists AND has Claude Code running
    local session="$1"
    if ! tmux has-session -t "$session" 2>/dev/null; then
        return 1
    fi
    local content
    content=$(tmux capture-pane -t "$session" -p -S -15 2>/dev/null || true)
    if echo "$content" | grep -q '❯\|Claude Code'; then
        return 0  # Active Claude Code session
    fi
    return 1
}

onboard_agent() {
    local name="$1"
    local session="$2"
    local role="$3"

    echo ""
    echo "=== Onboarding: $name ==="

    # Safety: refuse to kill active sessions without --force
    if tmux has-session -t "$session" 2>/dev/null; then
        if check_session_active "$session"; then
            if [ "$FORCE" = true ]; then
                echo "  WARNING: Killing ACTIVE session (--force): $session"
                tmux kill-session -t "$session"
                sleep 1
            else
                echo "  ERROR: Session '$session' is ACTIVE with Claude Code running."
                echo "  Refusing to kill an active agent's work."
                echo "  Use --force to override, or join.sh to connect an existing instance."
                return 0
            fi
        else
            echo "  Killing stale session: $session"
            tmux kill-session -t "$session"
            sleep 1
        fi
    fi

    # Create new session with project directory as default path
    echo "  Creating tmux session: $session"
    tmux new-session -d -s "$session" -x 200 -y 50 -c "$PROJECT_PATH"

    # Set default-path so new panes/windows open in the project directory
    tmux set-option -t "$session" default-command "cd $PROJECT_PATH && exec $SHELL"

    # Set window title for Warp tab display
    tmux rename-window -t "$session" "$name"

    # Enable mouse scroll + set scrollback buffer
    tmux set-option -t "$session" mouse on
    if [ "$name" = "supervisor" ]; then
        tmux set-option -t "$session" history-limit 50000
        echo "  Scrollback: 50000 (supervisor) + mouse on"
    else
        tmux set-option -t "$session" history-limit 10000
    fi

    # Set environment variable for agent identity
    tmux send-keys -t "$session" "export WARROOM_AGENT_NAME=$name" Enter
    sleep 0.5

    # Start Claude Code
    echo "  Starting Claude Code..."
    tmux send-keys -t "$session" "cd $PROJECT_PATH && claude --dangerously-skip-permissions" Enter

    # Wait for Claude Code to become ready
    wait_for_prompt "$session"

    # Write onboarding to a temp file (avoids paste-buffer race conditions)
    local onboard_file="/tmp/warroom-onboard-${name}.md"
    cat > "$onboard_file" << ONBOARD_EOF
You are $name in the Coder's War Room — a real-time communication system for parallel Claude Code agents working on the same project.

YOUR IDENTITY: $name
YOUR ROLE: $role
PROJECT: $PROJECT_PATH

WAR ROOM PROTOCOL:
- Messages prefixed with [WARROOM @$name] are directed at you. You MUST respond and act on them.
- Messages prefixed with [WARROOM] (no specific tag) are broadcasts. Read them for context. Only respond if it directly impacts your current work. If not relevant, just say "Noted" and continue your work. Do NOT post acknowledgements to the war room.
- Messages prefixed with [WARROOM SYSTEM] are informational. Do not respond.
- To send a message to the war room, run: $WARROOM_SH post "your message"
- To send a direct message: $WARROOM_SH post --to <agent-name> "your message"
- To check recent messages: $WARROOM_SH history
- To see messages for you: $WARROOM_SH mentions
- Keep war room messages concise. This is a chat, not a document.
- When you complete a task or hit a blocker, post it to the war room immediately.

Acknowledge with your name and role, then wait for instructions.
ONBOARD_EOF

    # Inject onboarding via file read command (safer than paste-buffer)
    tmux set-buffer -b warroom-onboard "Read the onboarding instructions at $onboard_file and follow them. After reading, acknowledge with your name and role."
    tmux paste-buffer -b warroom-onboard -t "$session"
    sleep 0.5
    tmux send-keys -t "$session" Enter

    # Verify Claude acknowledged (check pane for response within 15s)
    local verify_wait=0
    while [ $verify_wait -lt 15 ]; do
        sleep 3
        verify_wait=$((verify_wait + 3))
        local pane_content
        pane_content=$(tmux capture-pane -t "$session" -p -S -10 2>/dev/null || true)
        if echo "$pane_content" | grep -qi "$name"; then
            echo "  Verified: $name acknowledged onboarding"
            break
        fi
    done

    echo "  Onboarded: $name"

    # Announce join and mark as active in war room
    curl -s -X POST "$SERVER_URL/api/messages" \
        -H "Content-Type: application/json" \
        -d "{\"sender\": \"system\", \"content\": \"$name has joined the war room\", \"type\": \"system\"}" \
        > /dev/null 2>&1 || true

    curl -s -X POST "$SERVER_URL/api/agents/$name/join" > /dev/null 2>&1 || true
}

# Main
echo "==========================================="
echo "  CODER'S WAR ROOM — Agent Onboarding"
echo "==========================================="
echo "Project: $PROJECT_PATH"
[ "$FORCE" = true ] && echo "Mode: FORCE (will kill active sessions)"
echo ""

# Check prerequisites
if ! command -v tmux &> /dev/null; then
    echo "ERROR: tmux is not installed. Run: brew install tmux"
    exit 1
fi

if ! curl -s "$SERVER_URL/api/agents" > /dev/null 2>&1; then
    echo "ERROR: War Room server not running at $SERVER_URL"
    echo "Start it first: python3 $SCRIPT_DIR/server.py &"
    exit 1
fi

FILTER="${POSITIONAL[*]}"
while IFS='|' read -r name session role; do
    onboard_agent "$name" "$session" "$role"
done < <(get_agents "$FILTER" "$INCLUDE_MANUAL")

echo ""
echo "==========================================="
echo "  Onboarding complete!"
echo "  Web UI: $SERVER_URL"
echo "  tmux sessions: tmux ls | grep warroom"
echo "==========================================="
