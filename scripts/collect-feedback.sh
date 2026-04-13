#!/bin/bash
# scripts/collect-feedback.sh — Post-session data collection and analysis
# Run after agents complete work to gather hook events, feedback, and metrics.
#
# Usage: ./scripts/collect-feedback.sh [output-dir]
# Default output: docs/feedback/YYYY-MM-DD_session-report.md
set -euo pipefail
trap 'echo "Script crashed: $0" >&2; exit 1' ERR

WARROOM_URL="${WARROOM_URL:-http://localhost:5680}"
OUTPUT_DIR="${1:-docs/feedback}"
TIMESTAMP=$(date +%Y-%m-%d_%H%M)
REPORT="${OUTPUT_DIR}/${TIMESTAMP}_session-report.md"

mkdir -p "$OUTPUT_DIR"

echo "Collecting War Room session data..."
echo ""

# ── 1. Hook Events ────────────────────────────────────────
echo "→ Fetching hook events..."
HOOK_EVENTS=$(curl -sf "${WARROOM_URL}/api/hooks/events/all?limit=500" 2>/dev/null || echo '{"events":[]}')

TOTAL_EVENTS=$(echo "$HOOK_EVENTS" | python3 -c "
import json, sys
events = json.load(sys.stdin).get('events', [])
print(len(events))
" 2>/dev/null || echo "0")

GATE_CHECKS=$(echo "$HOOK_EVENTS" | python3 -c "
import json, sys
events = json.load(sys.stdin).get('events', [])
gate = [e for e in events if e.get('event_type') == 'gate_check']
print(len(gate))
" 2>/dev/null || echo "0")

STOP_BLOCKS=$(echo "$HOOK_EVENTS" | python3 -c "
import json, sys
events = json.load(sys.stdin).get('events', [])
blocked = [e for e in events if e.get('event_type') == 'stop_blocked']
print(len(blocked))
" 2>/dev/null || echo "0")

MERGE_EVENTS=$(echo "$HOOK_EVENTS" | python3 -c "
import json, sys
events = json.load(sys.stdin).get('events', [])
merges = [e for e in events if 'merge' in e.get('event_type', '')]
print(len(merges))
" 2>/dev/null || echo "0")

# ── 2. Agent Status ───────────────────────────────────────
echo "→ Fetching agent status..."
AGENTS=$(curl -sf "${WARROOM_URL}/api/agents" 2>/dev/null || echo '[]')

AGENT_COUNT=$(echo "$AGENTS" | python3 -c "
import json, sys
agents = json.load(sys.stdin)
print(len(agents))
" 2>/dev/null || echo "0")

# ── 3. War Room Messages ─────────────────────────────────
echo "→ Fetching War Room messages..."
MESSAGES=$(curl -sf "${WARROOM_URL}/api/messages?limit=500" 2>/dev/null || echo '[]')

MSG_COUNT=$(echo "$MESSAGES" | python3 -c "
import json, sys
msgs = json.load(sys.stdin)
print(len(msgs))
" 2>/dev/null || echo "0")

FEEDBACK_MSGS=$(echo "$MESSAGES" | python3 -c "
import json, sys
msgs = json.load(sys.stdin)
feedback = [m for m in msgs if '[FEEDBACK]' in m.get('content', '')]
for f in feedback:
    print(f'  - {f[\"sender\"]}: {f[\"content\"][:200]}')
if not feedback:
    print('  (none)')
" 2>/dev/null || echo "  (none)")

# ── 4. Per-Agent Hook Event Breakdown ─────────────────────
echo "→ Analyzing per-agent hook activity..."
AGENT_BREAKDOWN=$(echo "$HOOK_EVENTS" | python3 -c "
import json, sys
from collections import defaultdict
events = json.load(sys.stdin).get('events', [])
by_agent = defaultdict(lambda: defaultdict(int))
for e in events:
    agent = e.get('agent', 'unknown')
    etype = e.get('event_type', 'unknown')
    by_agent[agent][etype] += 1

for agent, counts in sorted(by_agent.items()):
    parts = [f'{k}={v}' for k, v in sorted(counts.items())]
    print(f'  {agent}: {\"  \".join(parts)}')
if not by_agent:
    print('  (no events)')
" 2>/dev/null || echo "  (error reading events)")

# ── 5. Tool Execution Summary ─────────────────────────────
TOOL_SUMMARY=$(echo "$HOOK_EVENTS" | python3 -c "
import json, sys
from collections import defaultdict
events = json.load(sys.stdin).get('events', [])
tools = defaultdict(lambda: {'pass': 0, 'fail': 0})
for e in events:
    tool = e.get('tool', '')
    if not tool:
        continue
    if e.get('exit_code', 0) == 0:
        tools[tool]['pass'] += 1
    else:
        tools[tool]['fail'] += 1

for tool, counts in sorted(tools.items()):
    status = 'PASS' if counts['fail'] == 0 else f'FAIL ({counts[\"fail\"]}x)'
    print(f'  | {tool} | {counts[\"pass\"]} pass | {counts[\"fail\"]} fail | {status} |')
if not tools:
    print('  (no tool events)')
" 2>/dev/null || echo "  (error)")

# ── 6. Settings Files Check ──────────────────────────────
echo "→ Checking generated settings files..."
SETTINGS_CHECK=""
for dir in ~/contextualise ~/coders-war-room; do
    if [ -f "${dir}/.claude/settings.local.json" ]; then
        hooks=$(python3 -c "
import json
d = json.load(open('${dir}/.claude/settings.local.json'))
print(len(d.get('hooks', {})))
" 2>/dev/null || echo "?")
        SETTINGS_CHECK="${SETTINGS_CHECK}\n  ${dir}: ${hooks} hook events configured"
    fi
done
if [ -z "$SETTINGS_CHECK" ]; then
    SETTINGS_CHECK="\n  (no settings.local.json found — agents may not have hooks)"
fi

# ── 7. Signal Analysis ────────────────────────────────────
SIGNALS=$(echo "$MESSAGES" | python3 -c "
import json, sys
msgs = json.load(sys.stdin)
signals = {
    'GATE-.*FAIL': 0,
    'READY-FOR-QA': 0,
    'MERGED': 0,
    'BLOCKED': 0,
    'PIPELINE-IDLE': 0,
    'EXCEPTION-PROPOSED': 0,
    'DONE:': 0,
    'START:': 0,
}
import re
for m in msgs:
    c = m.get('content', '')
    for pattern in signals:
        if re.search(pattern, c):
            signals[pattern] += 1

for sig, count in signals.items():
    if count > 0:
        print(f'  {sig}: {count}')
if all(v == 0 for v in signals.values()):
    print('  (no pipeline signals detected)')
" 2>/dev/null || echo "  (error)")

# ── Write Report ──────────────────────────────────────────
cat > "$REPORT" << EOF
# War Room Session Report — ${TIMESTAMP}

## Summary

| Metric | Value |
|--------|-------|
| Agents active | ${AGENT_COUNT} |
| Total hook events | ${TOTAL_EVENTS} |
| Gate checks | ${GATE_CHECKS} |
| Stop blocks (agent prevented from stopping) | ${STOP_BLOCKS} |
| Merge events | ${MERGE_EVENTS} |
| War Room messages | ${MSG_COUNT} |

## Hook Events by Agent

${AGENT_BREAKDOWN}

## Tool Execution Summary

| Tool | Passes | Failures | Status |
|------|--------|----------|--------|
${TOOL_SUMMARY}

## Pipeline Signals

${SIGNALS}

## Agent Feedback ([FEEDBACK] tagged messages)

${FEEDBACK_MSGS}

## Settings Files

$(echo -e "$SETTINGS_CHECK")

## Questions for Next Session

1. Did SessionStart hooks successfully load role skills for every agent?
2. Were any Stop hooks triggered? If so, did agents fix the issue and retry?
3. Did any agent attempt to bypass a gate (Write/Edit on non-coding role)?
4. Were War Room messages delivered and acted on?
5. Did the Gates dashboard show accurate, real-time status?

---
*Generated by collect-feedback.sh at $(date)*
EOF

echo ""
echo "Report saved: ${REPORT}"
echo ""
echo "Quick summary:"
echo "  Agents: ${AGENT_COUNT}"
echo "  Hook events: ${TOTAL_EVENTS} (${GATE_CHECKS} gate checks, ${STOP_BLOCKS} stop blocks)"
echo "  Messages: ${MSG_COUNT}"
echo "  Feedback: $(echo "$FEEDBACK_MSGS" | grep -c '-' || echo 0) items"
