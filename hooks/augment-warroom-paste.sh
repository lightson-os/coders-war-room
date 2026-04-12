#!/usr/bin/env bash
# augment-warroom-paste.sh — UserPromptSubmit hook
# Fires when ANY user input is submitted (including tmux pastes).
# If the input contains [WARROOM], augment it with system-level framing
# so Claude treats it as a high-priority coordination message.
#
# For UserPromptSubmit, stdout is added as context that Claude sees
# alongside the user's prompt. This is our chance to reframe the paste.
#
# Also checks the file-based inbox for any other pending messages.
set -euo pipefail
trap 'echo "Hook crashed: $0" >&2; exit 2' ERR

# Read the hook input from stdin
INPUT=$(cat)

# Extract the user's prompt text
PROMPT_TEXT=$(echo "$INPUT" | jq -r '.prompt // .user_prompt // ""' 2>/dev/null || echo "")

INBOX_DIR="/Users/gurvindersingh/coders-war-room/.inbox"
AGENT_NAME="${CLAUDE_AGENT_NAME:-default}"
AGENT_INBOX="$INBOX_DIR/$AGENT_NAME"

# Check if this is a war room paste
if echo "$PROMPT_TEXT" | grep -q '\[WARROOM'; then
  # This IS a war room message delivered via tmux paste.
  # Add system-level framing so Claude does not dismiss it.
  cat <<'CONTEXT'
SYSTEM PRIORITY OVERRIDE: The message you just received is a WAR ROOM COORDINATION MESSAGE from another agent or your human operator. This is NOT casual side input. You MUST:
1. Read the full message carefully
2. Understand the sender, phase, and content
3. Respond substantively with your status, acknowledgment, or the requested information
4. If the message requests action, take that action or explain why you cannot
Do NOT respond with just "Noted." — that indicates a delivery failure.
CONTEXT
  exit 0
fi

# Even if this is not a war room paste, check the file inbox
# and surface any pending messages as context
if [[ -d "$AGENT_INBOX" ]]; then
  MESSAGES=""
  COUNT=0
  for msg_file in "$AGENT_INBOX"/msg-*.json; do
    [[ -f "$msg_file" ]] || continue
    [[ "$msg_file" == *.read ]] && continue

    if CONTENT=$(cat "$msg_file" 2>/dev/null); then
      SENDER=$(echo "$CONTENT" | jq -r '.sender // "unknown"' 2>/dev/null || echo "unknown")
      BODY=$(echo "$CONTENT" | jq -r '.message // .body // ""' 2>/dev/null || echo "")
      PRIORITY=$(echo "$CONTENT" | jq -r '.priority // "normal"' 2>/dev/null || echo "normal")

      if [[ -n "$BODY" ]]; then
        PRIORITY_UPPER=$(echo "$PRIORITY" | tr '[:lower:]' '[:upper:]')
        MESSAGES="${MESSAGES}[WAR ROOM - ${PRIORITY_UPPER}] From ${SENDER}: ${BODY}
"
        COUNT=$((COUNT + 1))
      fi

      mv "$msg_file" "${msg_file}.read" 2>/dev/null || true
    fi
  done

  if [[ $COUNT -gt 0 ]]; then
    echo "SYSTEM ALERT: You have ${COUNT} pending war room message(s). Read and respond to them before continuing your current task."
    echo ""
    echo "$MESSAGES"
  fi
fi

exit 0
