#!/bin/bash
# hooks/engineer-quality-gate.sh
# Stop hook — Engineer cannot stop until pytest passes
set -euo pipefail
trap 'echo "Hook crashed: engineer-quality-gate.sh" >&2; exit 2' ERR

PROJ_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

# Find the northstar test directory
if [ -d "${PROJ_DIR}/northstar/tests" ]; then
  TEST_DIR="${PROJ_DIR}/northstar"
elif [ -d "${PROJ_DIR}/tests" ]; then
  TEST_DIR="${PROJ_DIR}"
else
  # No tests directory found — allow stop
  exit 0
fi

cd "$TEST_DIR"

# Activate venv if it exists
if [ -f "venv/bin/activate" ]; then
  source venv/bin/activate
fi

# Timeout from registry via settings generator env var (default 120s)
GATE_TIMEOUT="${WARROOM_PYTEST_TIMEOUT:-120}"

# Run pytest with registry-driven timeout
# Temporarily disable errexit so non-zero exit doesn't trigger ERR trap
set +e
OUTPUT=$(timeout "$GATE_TIMEOUT" python -m pytest tests/ -q --tb=line 2>&1)
EXIT_CODE=$?
set -e

# Handle timeout signal (exit code 124 from GNU timeout)
if [ "$EXIT_CODE" -eq 124 ]; then
  echo "pytest timed out after ${GATE_TIMEOUT}s — test suite may need splitting or timeout increase in gate-registry.yaml" >&2

  AGENT_NAME="${WARROOM_AGENT_NAME:-engineer}"
  curl -sf -X POST "${WARROOM_URL:-http://localhost:5680}/api/hooks/event" \
    -H "Content-Type: application/json" \
    -d "{\"agent\": \"${AGENT_NAME}\", \"event_type\": \"stop_blocked\", \"tool\": \"pytest\", \"exit_code\": 124, \"summary\": \"Timed out after ${GATE_TIMEOUT}s\"}" \
    2>/dev/null || true

  exit 2
fi

if echo "$OUTPUT" | grep -qE '(FAILED|ERROR|no tests ran)'; then
  FAIL_COUNT=$(echo "$OUTPUT" | grep -oE '[0-9]+ failed' | head -1 || echo "unknown")
  echo "Tests failing (${FAIL_COUNT}). Fix all test failures before stopping." >&2

  # POST to War Room API
  AGENT_NAME="${WARROOM_AGENT_NAME:-engineer}"
  curl -sf -X POST "${WARROOM_URL:-http://localhost:5680}/api/hooks/event" \
    -H "Content-Type: application/json" \
    -d "{\"agent\": \"${AGENT_NAME}\", \"event_type\": \"stop_blocked\", \"tool\": \"pytest\", \"exit_code\": 1, \"summary\": \"Tests failing: ${FAIL_COUNT}\"}" \
    2>/dev/null || true

  exit 2
fi

# Tests pass — POST success and allow stop
PASS_COUNT=$(echo "$OUTPUT" | grep -oE '[0-9]+ passed' | head -1 || echo "all")
AGENT_NAME="${WARROOM_AGENT_NAME:-engineer}"
curl -sf -X POST "${WARROOM_URL:-http://localhost:5680}/api/hooks/event" \
  -H "Content-Type: application/json" \
  -d "{\"agent\": \"${AGENT_NAME}\", \"event_type\": \"gate_check\", \"tool\": \"pytest\", \"exit_code\": 0, \"summary\": \"${PASS_COUNT} passed\"}" \
  2>/dev/null || true

exit 0
