#!/bin/bash
# hooks/block-code-writes.sh
# PreToolUse hook — denies Write/Edit for non-coding agent roles
set -euo pipefail
trap 'echo "Hook crashed: block-code-writes.sh" >&2; exit 2' ERR

AGENT_NAME="${WARROOM_AGENT_NAME:-unknown}"

cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "Agent '${AGENT_NAME}' is a non-coding role. Write and Edit tools are blocked. You verify and report — the Engineer writes code."
  }
}
EOF

exit 0
