#!/bin/bash
# hooks/qa-quality-gate.sh
# Stop hook — QA cannot stop without running qa-suite.sh
set -euo pipefail
trap 'echo "Hook crashed: qa-quality-gate.sh" >&2; exit 2' ERR

# Check if qa-suite output exists from recent session (last 4 hours)
QA_FILES=$(find /tmp -name "qa-suite-*.json" -mmin -240 2>/dev/null | head -5)

if [ -z "$QA_FILES" ]; then
  echo "qa-suite.sh has not been run this session. Run: scripts/qa-suite.sh <STORY-ID>" >&2

  AGENT_NAME="${WARROOM_AGENT_NAME:-qa}"
  curl -sf -X POST "${WARROOM_URL:-http://localhost:5680}/api/hooks/event" \
    -H "Content-Type: application/json" \
    -d "{\"agent\": \"${AGENT_NAME}\", \"event_type\": \"stop_blocked\", \"tool\": \"qa-suite\", \"exit_code\": 1, \"summary\": \"qa-suite.sh not run\"}" \
    2>/dev/null || true

  exit 2
fi

# qa-suite was run — allow stop
LATEST=$(find /tmp -name "qa-suite-*.json" -mmin -240 -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | cut -d' ' -f2)
PASS=$(python3 -c "import json; print(json.load(open('${LATEST}'))['pass'])" 2>/dev/null || echo "unknown")

AGENT_NAME="${WARROOM_AGENT_NAME:-qa}"
curl -sf -X POST "${WARROOM_URL:-http://localhost:5680}/api/hooks/event" \
  -H "Content-Type: application/json" \
  -d "{\"agent\": \"${AGENT_NAME}\", \"event_type\": \"gate_check\", \"tool\": \"qa-suite\", \"exit_code\": 0, \"summary\": \"qa-suite pass=${PASS}\"}" \
  2>/dev/null || true

exit 0
