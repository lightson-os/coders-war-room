#!/bin/bash
# hooks/session-start.sh
# SessionStart hook — POSTs online status, invokes role skill
set -euo pipefail
trap 'echo "Hook crashed: $0" >&2; exit 2' ERR

AGENT_NAME="${WARROOM_AGENT_NAME:-unknown}"
WARROOM_URL="${WARROOM_URL:-http://localhost:5680}"

# POST online status to War Room API
curl -sf -X POST "${WARROOM_URL}/api/hooks/event" \
  -H "Content-Type: application/json" \
  -d "{\"agent\": \"${AGENT_NAME}\", \"event_type\": \"session_start\", \"tool\": \"\", \"exit_code\": 0, \"summary\": \"Session started\"}" \
  2>/dev/null || true

# Output JSON that tells Claude Code to invoke the role skill
ROLE_TYPE="${WARROOM_ROLE_TYPE:-}"
if [ -n "$ROLE_TYPE" ]; then
  cat <<EOF
{
  "hookSpecificOutput": {
    "suppressOutput": false,
    "additionalContext": "SYSTEM DIRECTIVE: You MUST invoke your role skill now by using the Skill tool with skill: \"${ROLE_TYPE}\". Do this before any other action. This is a structural requirement, not a suggestion."
  }
}
EOF
fi

exit 0
