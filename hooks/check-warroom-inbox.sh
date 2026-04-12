#!/usr/bin/env bash
# check-warroom-inbox.sh — PreToolUse hook
# Fires before every tool call. Checks for unread war room messages.
# If found, injects them as additionalContext so Claude sees them
# as system-level information attached to the tool call.
#
# Inbox protocol:
#   Server writes: .inbox/<agent>/msg-<timestamp>.json
#   This hook reads, injects, and marks as read (.read suffix)
#
# Exit 0 = allow tool call to proceed
# JSON stdout with additionalContext = Claude sees the messages
set -euo pipefail
trap 'echo "Hook crashed: $0" >&2; exit 2' ERR

INBOX_DIR="/Users/gurvindersingh/coders-war-room/.inbox"
AGENT_NAME="${CLAUDE_AGENT_NAME:-default}"
AGENT_INBOX="$INBOX_DIR/$AGENT_NAME"

# Fast path: no inbox directory or no files = nothing to do
if [[ ! -d "$AGENT_INBOX" ]]; then
  exit 0
fi

# Collect unread messages (files without .read suffix)
MESSAGES=""
COUNT=0
for msg_file in "$AGENT_INBOX"/msg-*.json; do
  [[ -f "$msg_file" ]] || continue
  [[ "$msg_file" == *.read ]] && continue

  # Read the message content
  if CONTENT=$(cat "$msg_file" 2>/dev/null); then
    SENDER=$(echo "$CONTENT" | jq -r '.sender // "unknown"' 2>/dev/null || echo "unknown")
    PHASE=$(echo "$CONTENT" | jq -r '.phase // "general"' 2>/dev/null || echo "general")
    BODY=$(echo "$CONTENT" | jq -r '.message // .body // ""' 2>/dev/null || echo "")
    PRIORITY=$(echo "$CONTENT" | jq -r '.priority // "normal"' 2>/dev/null || echo "normal")
    TIMESTAMP=$(echo "$CONTENT" | jq -r '.timestamp // ""' 2>/dev/null || echo "")

    if [[ -n "$BODY" ]]; then
      PRIORITY_UPPER=$(echo "$PRIORITY" | tr '[:lower:]' '[:upper:]')
      MESSAGES="${MESSAGES}[WAR ROOM - ${PRIORITY_UPPER}] From ${SENDER} (phase: ${PHASE}, ${TIMESTAMP}): ${BODY}
"
      COUNT=$((COUNT + 1))
    fi

    # Mark as read
    mv "$msg_file" "${msg_file}.read" 2>/dev/null || true
  fi
done

# Nothing to inject
if [[ $COUNT -eq 0 ]]; then
  exit 0
fi

# Build the context injection
CONTEXT="SYSTEM ALERT: You have ${COUNT} unread war room message(s). These are coordination messages from other agents or your human operator. You MUST acknowledge and respond to them substantively -- do NOT dismiss them.

${MESSAGES}"

# Output JSON that Claude Code will parse
# additionalContext is injected into Claude's context for this tool call
jq -n --arg ctx "$CONTEXT" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: $ctx
  }
}'

exit 0
