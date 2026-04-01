# Live Dashboard Sidebar + Task Tracking — Design Spec

**Date:** 2026-04-02
**Goal:** Transform the agent sidebar from a static roster into a live dashboard — always-visible, stock-ticker-style instrument panels showing what each agent is doing, their progress, blockers, and owned files.
**Principle:** Ambient awareness. Information absorbed passively, like a stock ticker or Uber's live car tracking. Zero clicks to check status.

---

## Problem

The sidebar shows agent names, roles, and presence dots. Users can't see what agents are working on, their progress, blockers, or which files they own. The user must ask "how's it going?" via chat — polling humans for state that the system should show automatically.

## Solution

Three-layer data model per agent:
1. **Config** (static) — name, role, owned files (glob patterns from config.yaml)
2. **Auto-detected** (2s refresh) — presence, current tool/action, file being touched, staleness
3. **Manual** (agent-posted, 30min TTL) — task description, progress %, ETA, blocker

Manual overrides auto. Auto fills gaps. TTL garbage-collects stale manual fields. Cards are clean when idle, rich when active.

---

## Agent Card States

### Idle (no manual status, no auto-detected activity)

```
● phase-1                          [cli] [@] [x]
  Foundation
  supervisor.py config.py state.py +3
```

### Active (auto-detected tool use)

```
● phase-3                          [cli] [@] [x]
  Heartbeat
  Edit → composition.py:45
  tier0.py context_assembly.py +6
```

### Active + Manual Status

```
● phase-3                          [cli] [@] [x]
  Heartbeat
  fixing tier logic in composition.py
  ████████░░ 60% · ~8 min
  tier0.py context_assembly.py +6
```

### Blocked

```
🔴 phase-3                         [cli] [@] [x]
   Heartbeat
   fixing tier logic in composition.py
   ████████░░ 60% · ~8 min
   ⚠ blocked: needs phase-1 config change
   tier0.py context_assembly.py +6
```

When an agent sets `--blocked phase-1 "reason"`, the server auto-DMs phase-1:
`[WARROOM @phase-1] system: phase-3 is blocked on you — needs config change`

### Stalled (auto-detected, 5+ min same tool+file)

```
🟡 phase-4                         [cli] [@] [x]
   Intelligence
   Edit → targeted_query.py:89
   5m+ on same file
   targeted_query.py watchlist.py +4
```

Stalled detection does NOT trigger during:
- `Read` operations (normal for large files)
- `Bash` commands (pytest runs, builds, long compilations)
- Only triggers for `Edit`, `Write`, and idle-with-no-tool states

---

## Card Elements

| Element | Source | Display |
|---------|--------|---------|
| **Name** | Config | Always shown. Color-coded. Dynamic agents get `~` indicator. |
| **Role** | Config (shortRole) | Short label. Full role on hover tooltip. |
| **Current action** | Auto-detected (tmux) | Normalized: `Edit → file.py:line`, `Bash → pytest`, `Read → config.yaml`. Only shown when active. |
| **Task description** | Manual (`warroom.sh status "..."`) | Replaces auto-detected line when set. One line, truncated with ellipsis. |
| **Progress bar** | Manual (`--progress N`) | Only shown when set. `████░░ 60%` format. |
| **ETA** | Manual (`--eta Nm`) | Shown next to progress bar: `60% · ~8 min`. |
| **Blocker** | Manual (`--blocked agent "reason"`) | Red warning line. Auto-DMs the blocking agent. |
| **Stalled** | Auto-detected (5+ min same state) | Yellow dot, "5m+ on same file" text. |
| **Owned files** | Config (`owns` globs, resolved) | Compact pill row: first 3 basenames + "+N" overflow. Hover shows full list. |
| **Last commit** | Auto-detected (git log in project dir) | `abc1234 fix state import` — latest commit hash + short message. Refreshed every 30s. |
| **Status dot** | Computed | Green=active, Yellow=stalled/busy, Red=blocked, Grey=session/offline |
| **Action buttons** | Static | `[cli]` `[@]` `[x]` — always visible |

---

## Owned Files in config.yaml

Each agent declares ownership via glob patterns:

```yaml
agents:
  - name: phase-1
    role: "Phase 1: Foundation — ..."
    tmux_session: warroom-phase-1
    owns:
      - "northstar/supervisor.py"
      - "northstar/config.py"
      - "northstar/state.py"
      - "northstar/safety.py"
      - "northstar/telegram_bot.py"
      - "northstar/monitor.py"

  - name: phase-2
    role: "Phase 2: Scheduled Tasks — ..."
    tmux_session: warroom-phase-2
    owns:
      - "northstar/retry.py"
      - "northstar/tools/*"
      - "northstar/reasoning.py"
      - "northstar/sweep_engine.py"
      - "northstar/master_run.py"
      - "northstar/scheduler.py"

  - name: phase-3
    role: "Phase 3: Heartbeat Cycle — ..."
    tmux_session: warroom-phase-3
    owns:
      - "northstar/tier0.py"
      - "northstar/context_assembly.py"
      - "northstar/composition.py"
      - "northstar/drafts.py"
      - "northstar/deferral.py"
      - "northstar/interaction.py"
      - "northstar/session.py"
      - "northstar/dock.py"
      - "northstar/heartbeat.py"

  - name: phase-4
    role: "Phase 4: Intelligence — ..."
    tmux_session: warroom-phase-4
    owns:
      - "northstar/targeted_query.py"
      - "northstar/watchlist.py"
      - "northstar/dirty_flags.py"
      - "northstar/proactive.py"
      - "northstar/quality_audit.py"
      - "northstar/kpi.py"

  - name: phase-5
    role: "Phase 5: Polish & Hardening — ..."
    tmux_session: warroom-phase-5
    owns:
      - "northstar/approval.py"
      - "northstar/headless.py"
      - "northstar/health_endpoint.py"
      - "northstar/document_handler.py"
      - "northstar/simulation.py"
      - "northstar/cost_tracker.py"
      - "northstar/maintenance.py"

  - name: phase-6
    role: "Phase 6: Skill Framework (6A+6B) — ..."
    tmux_session: warroom-phase-6
    owns:
      - "skill_manifest.py"
      - "skill_evaluator.py"
      - "skill_generator.py"
      - "northstar/skill_discovery.py"
      - "northstar/skill_engine.py"
      - "northstar/skill_executor.py"
      - "northstar/skill_detector.py"
      - "northstar/skill_observer.py"
      - "skills/**"

  - name: git-agent
    role: "Handles all git operations — ..."
    tmux_session: warroom-git-agent
    owns: []

  - name: supervisor
    role: "Oversees all phases — ..."
    tmux_session: warroom-supervisor
    auto_onboard: false
    owns: []
```

Glob patterns are resolved at startup against the project directory. The WebSocket payload sends the expanded list (basenames), not raw globs.

---

## API

### `POST /api/agents/{name}/status` — Set manual status

```json
{
  "task": "fixing tier logic in composition.py",
  "progress": 60,
  "eta": "8m",
  "blocked_by": "phase-1",
  "blocked_reason": "needs config change"
}
```

All fields optional. Only provided fields are updated. Omitted fields keep current values.

When `blocked_by` is set, the server auto-posts a DM:
`[WARROOM @phase-1] system: phase-3 is blocked on you — needs config change`

**Clear all manual fields:**
```json
{"clear": true}
```

**Unblock only:**
```json
{"blocked_by": null, "blocked_reason": null}
```

### `GET /api/agents/{name}/status` — Query own card state

Returns the full computed card data (config + auto + manual merged):

```json
{
  "name": "phase-3",
  "role": "Phase 3: Heartbeat Cycle — ...",
  "presence": "busy",
  "activity": "Edit → composition.py:45",
  "task": "fixing tier logic in composition.py",
  "progress": 60,
  "eta": "8m",
  "blocked_by": "phase-1",
  "blocked_reason": "needs config change",
  "stalled": false,
  "stalled_minutes": 0,
  "owns": ["tier0.py", "context_assembly.py", "composition.py", "drafts.py", "deferral.py", "interaction.py", "session.py", "dock.py", "heartbeat.py"],
  "last_commit": {"hash": "3ff52d0", "message": "fix state import"},
  "in_room": true,
  "dynamic": false
}
```

### `GET /api/agents/{name}/owns` — Get ownership patterns

```json
{
  "agent": "phase-3",
  "patterns": ["northstar/tier0.py", "northstar/context_assembly.py", ...],
  "resolved": ["tier0.py", "context_assembly.py", "composition.py", ...]
}
```

Returns both the raw glob patterns and the resolved filenames.

---

## WebSocket Push (every 2s)

Extends the existing `agent_status` event with new fields:

```json
{
  "type": "agent_status",
  "agents": {
    "phase-3": {
      "presence": "busy",
      "activity": "Edit → composition.py:45",
      "in_room": true,
      "dynamic": false,
      "task": "fixing tier logic",
      "progress": 60,
      "eta": "8m",
      "blocked_by": "phase-1",
      "blocked_reason": "needs config change",
      "stalled": false,
      "stalled_minutes": 0,
      "owns": ["tier0.py", "context_assembly.py", "composition.py", "drafts.py", "deferral.py", "interaction.py", "session.py", "dock.py", "heartbeat.py"],
      "last_commit": {"hash": "3ff52d0", "message": "fix state import"}
    }
  }
}
```

Fields not set (no manual status, no last commit) are `null` — the frontend skips rendering them.

---

## CLI: `warroom.sh status`

```bash
# Set task + progress + ETA
warroom.sh status "fixing tier logic" --progress 60 --eta 8m

# Set a blocker (auto-DMs the blocking agent)
warroom.sh status --blocked phase-1 "needs config change"

# Clear blocker only
warroom.sh status --unblocked

# Clear all manual fields (back to auto-detect only)
warroom.sh status --clear

# Query your own card state
warroom.sh status --show
```

Maps 1:1 to the API. Uses `WARROOM_AGENT_NAME` (auto-detected from tmux session) for identity.

---

## TTL Rules

- Manual fields (task, progress, eta) expire **30 minutes** after last set
- TTL timer **resets on ANY agent activity** (tool calls detected via tmux pane changes)
- `--clear` expires all manual fields immediately
- Blocker fields expire only via `--unblocked` or `--clear` (never auto-expire — blockers are important)
- Stalled state auto-clears when the agent's tool/file changes

---

## Last Commit Detection

Every 30 seconds, for each agent that has an `owns` list, the server runs:

```bash
git -C <project_dir> log -1 --format="%h %s" -- <owned_files>
```

This returns the latest commit that touched any of the agent's owned files. Displayed on the card as:
```
abc1234 fix state import
```

Lightweight (one git command per agent, every 30s) and requires no agent cooperation.

---

## Server-Side Data Structures

```python
# Per-agent manual status store
agent_manual_status: dict[str, dict] = {}
# Example: {"phase-3": {"task": "...", "progress": 60, "eta": "8m", "updated_at": timestamp}}

# Per-agent staleness tracking
agent_last_state: dict[str, dict] = {}
# Example: {"phase-3": {"tool": "Edit", "file": "composition.py", "since": timestamp}}

# Resolved ownership (computed at startup from config.yaml globs)
agent_owns_resolved: dict[str, list[str]] = {}
# Example: {"phase-6": ["skill_manifest.py", "skill_evaluator.py", ...]}

# Last commit per agent (refreshed every 30s)
agent_last_commit: dict[str, dict] = {}
# Example: {"phase-1": {"hash": "3ff52d0", "message": "fix state import"}}
```

---

## What This Does NOT Include

- No kanban/column view (embedded in sidebar is the chosen layout)
- No task assignment system (agents set their own status)
- No drag-and-drop task reordering
- No historical status tracking (only current state)
- No cross-agent dependency graph visualization
- No automatic ETA estimation (agents provide their own)
