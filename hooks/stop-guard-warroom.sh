#!/usr/bin/env bash
# stop-guard-warroom.sh — Stop hook
# Fires when Claude finishes responding and is about to stop.
# If there are CRITICAL unread war room messages, block the stop
# and force Claude to continue (it will see stderr as an error).
#
# IMPORTANT: This is the "nuclear option." Only blocks for priority=critical.
# Normal messages are handled by PreToolUse and UserPromptSubmit hooks.
#
# RECURSION GUARD: Only blocks once per batch of messages.
# Uses a lockfile to prevent infinite stop loops.
set -euo pipefail
trap 'echo "Hook crashed: $0" >&2; exit 2' ERR

INBOX_DIR="/Users/gurvindersingh/coders-war-room/.inbox"
AGENT_NAME="${CLAUDE_AGENT_NAME:-default}"
AGENT_INBOX="$INBOX_DIR/$AGENT_NAME"
LOCKFILE="/tmp/warroom-stop-guard-${AGENT_NAME}.lock"

# Read hook input
INPUT=$(cat)

# RECURSION GUARD: Check if we already blocked a stop recently (within 30 seconds)
if [[ -f "$LOCKFILE" ]]; then
  LOCK_AGE=$(( $(date +%s) - $(stat -f %m "$LOCKFILE" 2>/dev/null || echo 0) ))
  if [[ $LOCK_AGE -lt 30 ]]; then
    # We blocked within the last 30 seconds. Allow this stop to prevent loops.
    exit 0
  else
    # Lock is stale, remove it
    rm -f "$LOCKFILE"
  fi
fi

# Check for CRITICAL unread messages only
if [[ ! -d "$AGENT_INBOX" ]]; then
  exit 0
fi

CRITICAL_MESSAGES=""
COUNT=0
for msg_file in "$AGENT_INBOX"/msg-*.json; do
  [[ -f "$msg_file" ]] || continue
  [[ "$msg_file" == *.read ]] && continue

  if CONTENT=$(cat "$msg_file" 2>/dev/null); then
    PRIORITY=$(echo "$CONTENT" | jq -r '.priority // "normal"' 2>/dev/null || echo "normal")

    if [[ "$PRIORITY" == "critical" ]]; then
      SENDER=$(echo "$CONTENT" | jq -r '.sender // "unknown"' 2>/dev/null || echo "unknown")
      BODY=$(echo "$CONTENT" | jq -r '.message // .body // ""' 2>/dev/null || echo "")

      if [[ -n "$BODY" ]]; then
        CRITICAL_MESSAGES="${CRITICAL_MESSAGES}CRITICAL from ${SENDER}: ${BODY}
"
        COUNT=$((COUNT + 1))
      fi

      mv "$msg_file" "${msg_file}.read" 2>/dev/null || true
    fi
  fi
done

# No critical messages = allow stop
if [[ $COUNT -eq 0 ]]; then
  exit 0
fi

# BLOCK THE STOP: Create lockfile and write to stderr
touch "$LOCKFILE"

echo "STOP BLOCKED: You have ${COUNT} CRITICAL war room message(s) that require immediate response before you can finish." >&2
echo "" >&2
echo "$CRITICAL_MESSAGES" >&2
echo "" >&2
echo "You MUST address these messages now. After responding, you may attempt to stop again." >&2

exit 2
