#!/usr/bin/env bash
# deliver-to-inbox.sh — Write a war room message to an agent's file inbox
# Usage: deliver-to-inbox.sh <agent-name> <sender> <phase> <message> [priority]
#
# This is called by the war room server as an alternative to tmux paste.
# The hooks (PreToolUse, UserPromptSubmit, Stop) will pick up the message.
set -euo pipefail
trap 'echo "Hook crashed: $0" >&2; exit 2' ERR

AGENT_NAME="${1:?Usage: deliver-to-inbox.sh <agent> <sender> <phase> <message> [priority]}"
SENDER="${2:?Missing sender}"
PHASE="${3:?Missing phase}"
MESSAGE="${4:?Missing message}"
PRIORITY="${5:-normal}"

INBOX_DIR="/Users/gurvindersingh/coders-war-room/.inbox"
AGENT_INBOX="$INBOX_DIR/$AGENT_NAME"

mkdir -p "$AGENT_INBOX"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
FILENAME="msg-$(date +%s%N 2>/dev/null || date +%s).json"

jq -n \
  --arg sender "$SENDER" \
  --arg phase "$PHASE" \
  --arg message "$MESSAGE" \
  --arg priority "$PRIORITY" \
  --arg timestamp "$TIMESTAMP" \
  '{
    sender: $sender,
    phase: $phase,
    message: $message,
    priority: $priority,
    timestamp: $timestamp
  }' > "$AGENT_INBOX/$FILENAME"

echo "Delivered to $AGENT_INBOX/$FILENAME"
