#!/bin/bash
# hooks/post-edit-lint.sh
# PostToolUse hook — auto-lint after file writes (async, no block)
set -euo pipefail
trap 'echo "Hook crashed: $0" >&2; exit 2' ERR

PROJ_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
AGENT_NAME="${WARROOM_AGENT_NAME:-engineer}"

# Get the file that was just edited from hook input
INPUT=$(cat 2>/dev/null || echo "{}")
FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except:
    print('')
" 2>/dev/null || echo "")

# Only lint Python files
if [[ "$FILE_PATH" == *.py ]]; then
  LINT_OUT=$(cd "$PROJ_DIR" && python3 -m flake8 "$FILE_PATH" --max-line-length=100 2>&1 || true)
  if [ -n "$LINT_OUT" ]; then
    ISSUE_COUNT=$(echo "$LINT_OUT" | wc -l | tr -d ' ')
    curl -sf -X POST "${WARROOM_URL:-http://localhost:5680}/api/hooks/event" \
      -H "Content-Type: application/json" \
      -d "{\"agent\": \"${AGENT_NAME}\", \"event_type\": \"lint\", \"tool\": \"flake8\", \"exit_code\": 1, \"summary\": \"${ISSUE_COUNT} issues in ${FILE_PATH##*/}\"}" \
      2>/dev/null || true
  else
    curl -sf -X POST "${WARROOM_URL:-http://localhost:5680}/api/hooks/event" \
      -H "Content-Type: application/json" \
      -d "{\"agent\": \"${AGENT_NAME}\", \"event_type\": \"lint\", \"tool\": \"flake8\", \"exit_code\": 0, \"summary\": \"clean: ${FILE_PATH##*/}\"}" \
      2>/dev/null || true
  fi
fi

exit 0
