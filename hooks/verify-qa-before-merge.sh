#!/bin/bash
# hooks/verify-qa-before-merge.sh
# Claude Code PreToolUse hook — blocks git merge/push to main without QA PASS
# Receives tool input JSON on stdin from Claude Code
#
# Returns:
#   exit 0 = allow the tool call
#   exit 2 = block the tool call (message on stderr shown to agent)
set -euo pipefail
trap 'echo "Hook crashed: $0" >&2; exit 2' ERR

AGENT_NAME="${WARROOM_AGENT_NAME:-git-agent}"
WARROOM_URL="${WARROOM_URL:-http://localhost:5680}"

INPUT=$(cat 2>/dev/null || echo "{}")

# Extract the command being attempted
COMMAND=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('command', ''))
except:
    print('')
" 2>/dev/null || echo "")

# Only check merge and push-to-main commands
if ! echo "$COMMAND" | grep -qE 'git (merge|push.*(origin )?main)'; then
    exit 0
fi

# Extract story ID from current branch name
BRANCH=$(git branch --show-current 2>/dev/null || echo "")
STORY_ID=$(echo "$BRANCH" | grep -oE '(NS|NSV)-[0-9]+' | head -1)

if [ -z "$STORY_ID" ]; then
    # Not on a named feature branch — allow (could be Supervisor on main)
    exit 0
fi

# Find repo root
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || echo ".")
QA_REPORT="${REPO_ROOT}/docs/qa/${STORY_ID}_review.md"

if [ ! -f "$QA_REPORT" ]; then
    echo "" >&2
    echo "MERGE BLOCKED — No QA report found for ${STORY_ID}" >&2
    echo "Expected: docs/qa/${STORY_ID}_review.md" >&2
    echo "Action: Run QA pipeline first" >&2

    curl -sf -X POST "${WARROOM_URL}/api/hooks/event" \
      -H "Content-Type: application/json" \
      -d "{\"agent\": \"${AGENT_NAME}\", \"event_type\": \"merge_blocked\", \"tool\": \"qa-report\", \"exit_code\": 1, \"summary\": \"No QA report for ${STORY_ID}\"}" \
      2>/dev/null || true

    exit 2
fi

if ! grep -q "VERDICT: PASS" "$QA_REPORT"; then
    VERDICT=$(grep "VERDICT:" "$QA_REPORT" | head -1 | sed 's/.*VERDICT: //' | tr -d '\n' || echo "unknown")
    echo "" >&2
    echo "MERGE BLOCKED — QA verdict is not PASS for ${STORY_ID}" >&2
    echo "Verdict: ${VERDICT}" >&2
    echo "Report: docs/qa/${STORY_ID}_review.md" >&2

    curl -sf -X POST "${WARROOM_URL}/api/hooks/event" \
      -H "Content-Type: application/json" \
      -d "{\"agent\": \"${AGENT_NAME}\", \"event_type\": \"merge_blocked\", \"tool\": \"qa-report\", \"exit_code\": 1, \"summary\": \"QA verdict ${VERDICT} for ${STORY_ID}\"}" \
      2>/dev/null || true

    exit 2
fi

curl -sf -X POST "${WARROOM_URL}/api/hooks/event" \
  -H "Content-Type: application/json" \
  -d "{\"agent\": \"${AGENT_NAME}\", \"event_type\": \"merge_allowed\", \"tool\": \"qa-report\", \"exit_code\": 0, \"summary\": \"QA PASS verified for ${STORY_ID}\"}" \
  2>/dev/null || true

echo "QA PASS verified for ${STORY_ID} — merge allowed" >&2
exit 0
