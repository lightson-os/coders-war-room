# Live Dashboard Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the agent sidebar into a live dashboard with auto-detected activity, manual status (progress, ETA, blockers), owned files, staleness detection, and last-commit tracking.

**Architecture:** Three-layer data model (config → auto-detect → manual). Server stores manual status with 30min TTL. Auto-detection via tmux pane parsing every 2s. Ownership from config.yaml glob patterns resolved at startup. Git log polled every 30s. All merged into the existing `agent_status` WebSocket push. Frontend renders progressive card states.

**Tech Stack:** Python 3.12, FastAPI, subprocess (tmux + git), vanilla JS

**Design Spec:** `docs/superpowers/specs/2026-04-02-status-board-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `config.yaml` | Modify | Add `owns` glob patterns per agent |
| `server.py` | Modify | Status store, status API endpoints, staleness tracking, ownership resolution, git log, enhanced agent_status_loop |
| `warroom.sh` | Modify | Add `status` subcommand with all flags |
| `static/index.html` | Modify | Redesign agent cards with progressive disclosure, progress bars, blocker display, owned files pills |
| `tests/test_api.py` | Modify | Tests for status endpoints |

---

### Task 1: Config — Add `owns` Field

**Files:**
- Modify: `~/coders-war-room/config.yaml`

- [ ] **Step 1: Add `owns` glob patterns to each agent**

Update `~/coders-war-room/config.yaml` — add `owns` to every agent entry. Keep existing fields untouched, just append `owns`:

```yaml
agents:
  - name: supervisor
    role: "Oversees all 6 North Star phases, coordinates cross-phase wiring and bug fixes, resolves conflicts between phase agents, maintains the big picture of daemon integration"
    tmux_session: warroom-supervisor
    auto_onboard: false
    owns: []

  - name: phase-1
    role: "Phase 1: Foundation — owns supervisor.py, config.py, state.py, safety.py, telegram_bot.py, monitor.py. Responsible for daemon skeleton, config loading, SQLite DatabaseManager, action registry, bash classifier, rate limiter, Telegram bot, health monitor, LaunchAgent plist."
    tmux_session: warroom-phase-1
    owns:
      - "northstar/supervisor.py"
      - "northstar/config.py"
      - "northstar/state.py"
      - "northstar/safety.py"
      - "northstar/telegram_bot.py"
      - "northstar/monitor.py"

  - name: phase-2
    role: "Phase 2: Scheduled Tasks — owns retry.py, tools/hindsight.py, tools/accession.py, reasoning.py, sweep_engine.py, master_run.py, scheduler.py. Responsible for retry engine, Hindsight API wrapper, document accession pipeline, two-tier reasoning (Haiku+Opus), sweep engine (Gmail/WhatsApp/iMessage/Notes), master run orchestrator, APScheduler cron jobs."
    tmux_session: warroom-phase-2
    owns:
      - "northstar/retry.py"
      - "northstar/tools/*"
      - "northstar/reasoning.py"
      - "northstar/sweep_engine.py"
      - "northstar/master_run.py"
      - "northstar/scheduler.py"

  - name: phase-3
    role: "Phase 3: Heartbeat Cycle — owns tier0.py, context_assembly.py, composition.py, drafts.py, deferral.py, interaction.py, session.py, dock.py, heartbeat.py. Responsible for Tier 0 pulse engine, context tiers 1-3, heartbeat message composition, draft-first actions, 4-tier deferral escalation, interaction heuristics, session semaphore, HB7 day summary dock."
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
    role: "Phase 4: Intelligence — owns targeted_query.py, watchlist.py, dirty_flags.py, proactive.py, quality_audit.py, kpi.py. Responsible for targeted query engine, watchlist monitor, mental model dirty flags, deadline warnings, Thinker Problem coaching, weekly quality audit, KPI tracker, confidence analytics, dashboard."
    tmux_session: warroom-phase-4
    owns:
      - "northstar/targeted_query.py"
      - "northstar/watchlist.py"
      - "northstar/dirty_flags.py"
      - "northstar/proactive.py"
      - "northstar/quality_audit.py"
      - "northstar/kpi.py"

  - name: phase-5
    role: "Phase 5: Polish & Hardening — owns approval.py, headless.py, health_endpoint.py, document_handler.py, simulation.py, cost_tracker.py, maintenance.py. Responsible for IMPACT approval workflow, IDE handover, headless fallback clients, health endpoint (port 9999), emergency stop, document filing pipeline, cost tracker ($8 warn/$10 stop), simulation mode, maintenance manager."
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
    role: "Phase 6: Skill Framework (6A+6B) — owns skill_manifest.py, skill_evaluator.py, skill_generator.py, skill_discovery.py, skill_engine.py, skill_executor.py, skill_detector.py, skill_observer.py, plus compile.py mods and 4 starter skills (monthly-invoicing, document-filing, sweep-processing, visa-status-check). Responsible for skill compilation, engine harness, discovery, execution, pattern detection, observer, and all skill definitions."
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
    role: "Handles all git operations: commits, branches, PRs, conflict resolution. NEVER execute git commands without posting plan to the war room and receiving explicit confirmation from gurvinder or supervisor first. Always post a diff summary before committing. Never force-push without gurvinder's confirmation. Never commit directly to main."
    tmux_session: warroom-git-agent
    owns: []
```

- [ ] **Step 2: Commit**

```bash
cd ~/coders-war-room
git add config.yaml
git commit -m "feat: add owns glob patterns to agent config"
```

---

### Task 2: Server — Status Store, Ownership Resolution, Staleness Tracking

**Files:**
- Modify: `~/coders-war-room/server.py`
- Modify: `~/coders-war-room/tests/test_api.py`

This task adds the server-side data structures and helper functions. No new endpoints yet — those come in Task 3.

- [ ] **Step 1: Add new imports and data structures**

At the top of `server.py`, after the existing imports, add `import glob as globmod` and `import time`.

After the existing state variables (line ~47), add:

```python
# ---------------------------------------------------------------------------
# Status store (manual status per agent, 30min TTL)
# ---------------------------------------------------------------------------
agent_manual_status: dict[str, dict] = {}
# Example: {"phase-3": {"task": "...", "progress": 60, "eta": "8m", "updated_at": 1234567890.0}}

# Staleness tracking (auto-detected)
agent_last_state: dict[str, dict] = {}
# Example: {"phase-3": {"tool": "Edit", "file": "composition.py", "since": 1234567890.0}}

# Resolved ownership (computed at startup from config.yaml globs)
agent_owns_resolved: dict[str, list[str]] = {}

# Last commit per agent (refreshed every 30s)
agent_last_commit: dict[str, dict] = {}

STATUS_TTL_SECONDS = 1800  # 30 minutes
STALE_THRESHOLD_SECONDS = 300  # 5 minutes
STALE_EXEMPT_TOOLS = {"Read", "Bash", "WebFetch", "WebSearch", "Agent"}
```

- [ ] **Step 2: Add ownership resolution function**

Add after the new data structures:

```python
def resolve_ownership():
    """Resolve glob patterns from config.yaml into actual filenames."""
    for agent in AGENTS:
        name = agent["name"]
        patterns = agent.get("owns", [])
        resolved = set()
        for pattern in patterns:
            full_pattern = str(Path(PROJECT_PATH) / pattern)
            matches = globmod.glob(full_pattern, recursive=True)
            for match in matches:
                p = Path(match)
                if p.is_file():
                    resolved.add(p.name)
        agent_owns_resolved[name] = sorted(resolved)
```

- [ ] **Step 3: Add staleness detection function**

```python
def update_staleness(agent_name: str, tool: str, file: str):
    """Track how long an agent has been on the same tool+file. Returns stalled info."""
    now = time.time()
    prev = agent_last_state.get(agent_name)

    if prev and prev.get("tool") == tool and prev.get("file") == file:
        # Same state — check duration
        elapsed = now - prev["since"]
        return elapsed >= STALE_THRESHOLD_SECONDS and tool not in STALE_EXEMPT_TOOLS
    else:
        # State changed — reset
        agent_last_state[agent_name] = {"tool": tool, "file": file, "since": now}
        return False


def get_stalled_minutes(agent_name: str) -> int:
    """Get how many minutes the agent has been in the same state."""
    prev = agent_last_state.get(agent_name)
    if not prev:
        return 0
    return int((time.time() - prev["since"]) / 60)
```

- [ ] **Step 4: Add manual status helpers**

```python
def get_manual_status(agent_name: str) -> dict:
    """Get manual status for an agent, respecting TTL."""
    status = agent_manual_status.get(agent_name)
    if not status:
        return {}
    # Check TTL (but blockers never expire)
    elapsed = time.time() - status.get("updated_at", 0)
    if elapsed > STATUS_TTL_SECONDS:
        # Expired — but keep blocker fields
        result = {}
        if status.get("blocked_by"):
            result["blocked_by"] = status["blocked_by"]
            result["blocked_reason"] = status.get("blocked_reason")
        if not result:
            agent_manual_status.pop(agent_name, None)
        return result
    return {k: v for k, v in status.items() if k != "updated_at"}


def reset_manual_ttl(agent_name: str):
    """Reset TTL timer when agent shows any activity."""
    if agent_name in agent_manual_status:
        agent_manual_status[agent_name]["updated_at"] = time.time()
```

- [ ] **Step 5: Add last-commit detection function**

```python
def refresh_last_commits():
    """Get latest commit touching each agent's owned files."""
    for agent in AGENTS:
        name = agent["name"]
        patterns = agent.get("owns", [])
        if not patterns:
            continue
        # Build file list for git log
        files = []
        for pattern in patterns:
            full = str(Path(PROJECT_PATH) / pattern)
            matches = globmod.glob(full, recursive=True)
            files.extend(m for m in matches if Path(m).is_file())
        if not files:
            continue
        try:
            result = subprocess.run(
                ["git", "-C", PROJECT_PATH, "log", "-1", "--format=%h %s", "--"] + files,
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                parts = result.stdout.strip().split(" ", 1)
                agent_last_commit[name] = {"hash": parts[0], "message": parts[1] if len(parts) > 1 else ""}
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
```

- [ ] **Step 6: Update agent_status_loop to merge all three layers**

Replace the existing `agent_status_loop` function (line ~323) with:

```python
async def agent_status_loop():
    """Background: push rich agent status (config + auto + manual) every 2s."""
    commit_counter = 0
    while True:
        await asyncio.sleep(2)
        commit_counter += 1

        # Refresh git commits every 30s (15 iterations * 2s)
        if commit_counter >= 15:
            commit_counter = 0
            refresh_last_commits()

        agents_data = {}
        for a in AGENTS:
            name = a["name"]
            session = a["tmux_session"]

            # Layer 1: auto-detected
            activity = get_agent_activity(session)

            # Parse tool and file from activity string for staleness tracking
            tool, file = None, None
            act_str = activity.get("activity") or ""
            if " → " in act_str:
                parts = act_str.split(" → ", 1)
                tool = parts[0].strip()
                file = parts[1].split(":")[0].strip() if len(parts) > 1 else None

            # Staleness detection
            stalled = False
            stalled_minutes = 0
            if tool and file and activity["presence"] == "busy":
                stalled = update_staleness(name, tool, file)
                stalled_minutes = get_stalled_minutes(name)
                # Reset manual TTL on activity
                reset_manual_ttl(name)
            elif activity["presence"] == "busy":
                # Busy but no parseable tool — reset staleness
                agent_last_state.pop(name, None)
                reset_manual_ttl(name)

            # Layer 2: manual status (with TTL)
            manual = get_manual_status(name)

            # Layer 3: config
            owns = agent_owns_resolved.get(name, [])
            last_commit = agent_last_commit.get(name)

            # Merge: manual overrides auto
            agents_data[name] = {
                "presence": "blocked" if manual.get("blocked_by") else ("stalled" if stalled else activity["presence"]),
                "activity": activity.get("activity"),
                "in_room": agent_membership.get(name, False),
                "dynamic": a.get("dynamic", False),
                "task": manual.get("task"),
                "progress": manual.get("progress"),
                "eta": manual.get("eta"),
                "blocked_by": manual.get("blocked_by"),
                "blocked_reason": manual.get("blocked_reason"),
                "stalled": stalled,
                "stalled_minutes": stalled_minutes,
                "owns": owns,
                "last_commit": last_commit,
            }

        data = json.dumps({"type": "agent_status", "agents": agents_data})
        for client in connected_clients[:]:
            try:
                await client.send_text(data)
            except Exception:
                if client in connected_clients:
                    connected_clients.remove(client)
```

- [ ] **Step 7: Call resolve_ownership() in lifespan**

Update the `lifespan` function to call `resolve_ownership()` after `reconcile_tmux_sessions()`:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    reconcile_tmux_sessions()
    resolve_ownership()
    refresh_last_commits()
    task1 = asyncio.create_task(flush_queues_loop())
    task2 = asyncio.create_task(agent_status_loop())
    yield
    task1.cancel()
    task2.cancel()
```

- [ ] **Step 8: Run existing tests**

```bash
cd ~/coders-war-room
python3 -m pytest tests/test_api.py -v
```

Expected: All 11 existing tests pass.

- [ ] **Step 9: Commit**

```bash
cd ~/coders-war-room
git add server.py
git commit -m "feat: add status store, ownership resolution, staleness tracking, git log"
```

---

### Task 3: Server — Status API Endpoints

**Files:**
- Modify: `~/coders-war-room/server.py`
- Modify: `~/coders-war-room/tests/test_api.py`

- [ ] **Step 1: Write failing tests**

Add to `~/coders-war-room/tests/test_api.py`:

```python
@pytest.mark.asyncio
async def test_set_agent_status():
    from server import app, agent_manual_status
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/agents/phase-1/status", json={
            "task": "fixing state import",
            "progress": 60,
            "eta": "5m",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "updated"
        assert "phase-1" in agent_manual_status
        assert agent_manual_status["phase-1"]["task"] == "fixing state import"
        assert agent_manual_status["phase-1"]["progress"] == 60


@pytest.mark.asyncio
async def test_get_agent_status():
    from server import app, agent_manual_status
    import time
    # Pre-set some status
    agent_manual_status["phase-2"] = {"task": "test task", "progress": 40, "updated_at": time.time()}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agents/phase-2/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["task"] == "test task"
        assert data["progress"] == 40


@pytest.mark.asyncio
async def test_clear_agent_status():
    from server import app, agent_manual_status
    import time
    agent_manual_status["phase-3"] = {"task": "old task", "progress": 80, "updated_at": time.time()}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/agents/phase-3/status", json={"clear": True})
        assert resp.status_code == 200
        assert "phase-3" not in agent_manual_status


@pytest.mark.asyncio
async def test_get_agent_owns():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agents/phase-1/owns")
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent"] == "phase-1"
        assert "patterns" in data
        assert "resolved" in data


@pytest.mark.asyncio
async def test_set_blocked_status():
    from server import app, agent_manual_status
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/agents/phase-3/status", json={
            "blocked_by": "phase-1",
            "blocked_reason": "needs config change",
        })
        assert resp.status_code == 200
        assert agent_manual_status["phase-3"]["blocked_by"] == "phase-1"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/coders-war-room
python3 -m pytest tests/test_api.py::test_set_agent_status tests/test_api.py::test_get_agent_status tests/test_api.py::test_clear_agent_status tests/test_api.py::test_get_agent_owns tests/test_api.py::test_set_blocked_status -v
```

Expected: FAIL — no routes

- [ ] **Step 3: Add the Pydantic model**

Add after `AgentCreate` model in server.py:

```python
class AgentStatus(BaseModel):
    task: Optional[str] = None
    progress: Optional[int] = None
    eta: Optional[str] = None
    blocked_by: Optional[str] = None
    blocked_reason: Optional[str] = None
    clear: bool = False
```

- [ ] **Step 4: Add the three endpoints**

Add before the `/api/agents/{agent_name}/deboard` endpoint:

```python
@app.post("/api/agents/{agent_name}/status")
async def set_agent_status(agent_name: str, req: AgentStatus):
    """Set manual status fields for an agent."""
    if agent_name not in AGENT_NAMES:
        return JSONResponse({"error": f"Unknown agent: {agent_name}"}, status_code=404)

    if req.clear:
        agent_manual_status.pop(agent_name, None)
        return {"status": "cleared", "agent": agent_name}

    current = agent_manual_status.get(agent_name, {})

    # Update only provided fields
    if req.task is not None:
        current["task"] = req.task
    if req.progress is not None:
        current["progress"] = max(0, min(100, req.progress))
    if req.eta is not None:
        current["eta"] = req.eta
    if req.blocked_by is not None:
        current["blocked_by"] = req.blocked_by
        current["blocked_reason"] = req.blocked_reason or ""
        # Auto-DM the blocking agent
        if req.blocked_by in AGENT_NAMES:
            dm_content = f"{agent_name} is blocked on you — {req.blocked_reason or 'no details'}"
            saved = await save_message("system", req.blocked_by, dm_content, "message")
            await broadcast_ws({"type": "message", "message": saved})
            await dispatch_to_agents(saved)
    elif req.blocked_by is None and "blocked_by" in current and req.clear is False:
        # Explicit unblock: blocked_by sent as null
        pass  # handled by the clear check above

    current["updated_at"] = time.time()
    agent_manual_status[agent_name] = current
    return {"status": "updated", "agent": agent_name}


@app.get("/api/agents/{agent_name}/status")
async def get_agent_status_endpoint(agent_name: str):
    """Query an agent's full computed card state."""
    if agent_name not in AGENT_NAMES:
        return JSONResponse({"error": f"Unknown agent: {agent_name}"}, status_code=404)

    session = AGENT_SESSIONS.get(agent_name, "")
    activity = get_agent_activity(session) if session else {"presence": "offline", "activity": None}
    manual = get_manual_status(agent_name)
    owns = agent_owns_resolved.get(agent_name, [])
    last_commit = agent_last_commit.get(agent_name)
    stalled_min = get_stalled_minutes(agent_name)

    return {
        "name": agent_name,
        "presence": activity["presence"],
        "activity": activity.get("activity"),
        "task": manual.get("task"),
        "progress": manual.get("progress"),
        "eta": manual.get("eta"),
        "blocked_by": manual.get("blocked_by"),
        "blocked_reason": manual.get("blocked_reason"),
        "stalled": stalled_min >= 5,
        "stalled_minutes": stalled_min,
        "owns": owns,
        "last_commit": last_commit,
        "in_room": agent_membership.get(agent_name, False),
    }


@app.get("/api/agents/{agent_name}/owns")
async def get_agent_owns(agent_name: str):
    """Get ownership patterns and resolved filenames."""
    if agent_name not in AGENT_NAMES:
        return JSONResponse({"error": f"Unknown agent: {agent_name}"}, status_code=404)
    agent = next((a for a in AGENTS if a["name"] == agent_name), None)
    patterns = agent.get("owns", []) if agent else []
    resolved = agent_owns_resolved.get(agent_name, [])
    return {"agent": agent_name, "patterns": patterns, "resolved": resolved}
```

- [ ] **Step 5: Update conftest to patch new globals**

Add to the `_init_db` fixture in `tests/conftest.py`:

```python
    monkeypatch.setattr(server, "agent_manual_status", {})
    monkeypatch.setattr(server, "agent_last_state", {})
    monkeypatch.setattr(server, "agent_last_commit", {})
```

- [ ] **Step 6: Run all tests**

```bash
cd ~/coders-war-room
python3 -m pytest tests/test_api.py -v
```

Expected: All tests pass (11 existing + 5 new = 16).

- [ ] **Step 7: Commit**

```bash
cd ~/coders-war-room
git add server.py tests/test_api.py tests/conftest.py
git commit -m "feat: add status API endpoints (set, get, owns) with blocker auto-DM"
```

---

### Task 4: CLI — `warroom.sh status` Command

**Files:**
- Modify: `~/coders-war-room/warroom.sh`

- [ ] **Step 1: Add the status subcommand**

Add the `status_cmd` function before the `case` statement in `warroom.sh`:

```bash
status_cmd() {
    # Parse flags
    local task=""
    local progress=""
    local eta=""
    local blocked=""
    local blocked_reason=""
    local show=false
    local clear=false
    local unblocked=false

    while [ $# -gt 0 ]; do
        case "$1" in
            --progress)
                progress="$2"; shift 2 ;;
            --eta)
                eta="$2"; shift 2 ;;
            --blocked)
                blocked="$2"; shift 2
                # Remaining args are the reason
                blocked_reason="$*"; break ;;
            --unblocked)
                unblocked=true; shift ;;
            --show)
                show=true; shift ;;
            --clear)
                clear=true; shift ;;
            *)
                # Positional arg = task description
                task="$1"; shift ;;
        esac
    done

    if [ "$show" = true ]; then
        curl -s "$WARROOM_SERVER/api/agents/$WARROOM_AGENT/status" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f\"Agent:    {d.get('name', '?')}\")
print(f\"Presence: {d.get('presence', '?')}\")
if d.get('activity'): print(f\"Activity: {d['activity']}\")
if d.get('task'): print(f\"Task:     {d['task']}\")
if d.get('progress') is not None: print(f\"Progress: {d['progress']}%\")
if d.get('eta'): print(f\"ETA:      {d['eta']}\")
if d.get('blocked_by'): print(f\"BLOCKED:  by {d['blocked_by']} — {d.get('blocked_reason', '')}\")
if d.get('stalled'): print(f\"STALLED:  {d.get('stalled_minutes', 0)}m on same file\")
if d.get('owns'): print(f\"Owns:     {', '.join(d['owns'][:5])}{'...' if len(d.get('owns',[])) > 5 else ''}\")
if d.get('last_commit'): print(f\"Commit:   {d['last_commit']['hash']} {d['last_commit']['message']}\")
"
        return
    fi

    if [ "$clear" = true ]; then
        curl -s -X POST "$WARROOM_SERVER/api/agents/$WARROOM_AGENT/status" \
            -H "Content-Type: application/json" \
            -d '{"clear": true}' > /dev/null
        echo "Status cleared"
        return
    fi

    if [ "$unblocked" = true ]; then
        curl -s -X POST "$WARROOM_SERVER/api/agents/$WARROOM_AGENT/status" \
            -H "Content-Type: application/json" \
            -d '{"blocked_by": null, "blocked_reason": null}' > /dev/null
        echo "Blocker cleared"
        return
    fi

    # Build JSON payload with only non-empty fields
    local payload="{"
    local sep=""
    if [ -n "$task" ]; then
        local escaped_task
        escaped_task=$(printf '%s' "$task" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')
        payload="${payload}${sep}\"task\": $escaped_task"
        sep=", "
    fi
    if [ -n "$progress" ]; then
        payload="${payload}${sep}\"progress\": $progress"
        sep=", "
    fi
    if [ -n "$eta" ]; then
        payload="${payload}${sep}\"eta\": \"$eta\""
        sep=", "
    fi
    if [ -n "$blocked" ]; then
        local escaped_reason
        escaped_reason=$(printf '%s' "$blocked_reason" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')
        payload="${payload}${sep}\"blocked_by\": \"$blocked\", \"blocked_reason\": $escaped_reason"
        sep=", "
    fi
    payload="${payload}}"

    if [ "$payload" = "{}" ]; then
        echo "Usage: warroom.sh status 'task description' [--progress N] [--eta Nm]"
        echo "       warroom.sh status --blocked <agent> 'reason'"
        echo "       warroom.sh status --unblocked"
        echo "       warroom.sh status --clear"
        echo "       warroom.sh status --show"
        return
    fi

    curl -s -X POST "$WARROOM_SERVER/api/agents/$WARROOM_AGENT/status" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null
    echo "Status updated"
}
```

- [ ] **Step 2: Add the case entry**

In the `case "$1" in` block, add before the `deboard` entry:

```bash
    status)
        shift
        status_cmd "$@"
        ;;
```

- [ ] **Step 3: Update the help text**

In the `*)` default case, add:

```bash
        echo "  warroom.sh status 'task' [--progress N] [--eta Nm]  Set status"
        echo "  warroom.sh status --blocked <agent> 'reason'        Set blocker"
        echo "  warroom.sh status --unblocked                       Clear blocker"
        echo "  warroom.sh status --clear                           Clear all status"
        echo "  warroom.sh status --show                            Show your card"
```

- [ ] **Step 4: Test manually**

```bash
cd ~/coders-war-room
# Start server if not running
python3 server.py &
sleep 2

# Test status commands
WARROOM_AGENT_NAME=phase-1 ./warroom.sh status "testing the status CLI" --progress 50 --eta 3m
WARROOM_AGENT_NAME=phase-1 ./warroom.sh status --show
WARROOM_AGENT_NAME=phase-1 ./warroom.sh status --clear
WARROOM_AGENT_NAME=phase-1 ./warroom.sh status --show

# Cleanup
pkill -f "python3.*server.py"
```

- [ ] **Step 5: Commit**

```bash
cd ~/coders-war-room
git add warroom.sh
git commit -m "feat: add warroom.sh status command with progress, ETA, blockers"
```

---

### Task 5: Frontend — Live Dashboard Agent Cards

**Files:**
- Modify: `~/coders-war-room/static/index.html`

This is the largest task. The agent cards need to render all three data layers with progressive disclosure.

- [ ] **Step 1: Add new CSS for progress bar, blocker, owned files pills, stalled state**

Add to the `<style>` section:

```css
/* ─── Progress bar ─── */
.ac-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  padding-left: 15px;
}

.ac-progress-bar {
  flex: 1;
  height: 4px;
  background: var(--border);
  border-radius: 2px;
  overflow: hidden;
  max-width: 120px;
}

.ac-progress-fill {
  height: 100%;
  background: var(--green);
  border-radius: 2px;
  transition: width 0.5s ease;
}

.ac-progress-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  color: var(--text-secondary);
  white-space: nowrap;
}

/* ─── Blocker ─── */
.ac-blocker {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
  padding: 3px 8px 3px 15px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  color: var(--red);
  background: var(--red-dim);
  border-radius: 3px;
  margin-left: 15px;
  margin-right: 4px;
}

/* ─── Owned files pills ─── */
.ac-owns {
  display: flex;
  flex-wrap: wrap;
  gap: 3px;
  margin-top: 5px;
  padding-left: 15px;
}

.ac-own-pill {
  font-family: 'JetBrains Mono', monospace;
  font-size: 8px;
  color: var(--text-dim);
  background: rgba(62,78,100,0.15);
  padding: 1px 5px;
  border-radius: 2px;
}

.ac-own-more {
  font-family: 'JetBrains Mono', monospace;
  font-size: 8px;
  color: var(--text-dim);
  padding: 1px 5px;
  cursor: default;
}

/* ─── Last commit ─── */
.ac-commit {
  font-family: 'JetBrains Mono', monospace;
  font-size: 8px;
  color: var(--text-dim);
  margin-top: 3px;
  padding-left: 15px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ─── Stalled card ─── */
.ac.stalled {
  border-color: rgba(255,215,64,0.3);
}

.ac.blocked-card {
  border-color: rgba(255,82,82,0.3);
}

.ac-stalled-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  color: var(--yellow);
  margin-top: 3px;
  padding-left: 15px;
}
```

- [ ] **Step 2: Rewrite the `renderAgents` agent card rendering**

In the `renderAgents()` function, replace the agent card `innerHTML` construction and surrounding logic (the `agentRoster.forEach` block) with the new progressive card rendering. The key changes:

1. Add `stalled` and `blocked-card` CSS classes based on data
2. Show `ac-progress` bar when progress is set
3. Show `ac-blocker` when blocked_by is set
4. Show `ac-stalled-text` when stalled
5. Show `ac-owns` pills (first 3 + overflow)
6. Show `ac-commit` when last_commit is set
7. Hide idle badge (already done in previous UX pass)
8. Manual task overrides auto activity line

The rendering logic per card:

```javascript
// Inside agentRoster.forEach(a => { ... })
const d = agentData[a.name] || {};
const presence = d.presence || 'offline';
const activity = d.activity || null;
const inRoom = d.in_room !== undefined ? d.in_room : true;
const deboarded = !inRoom;
const role = shortRole(a.role, a.name);

// Manual status fields
const task = d.task || null;
const progress = d.progress != null ? d.progress : null;
const eta = d.eta || null;
const blockedBy = d.blocked_by || null;
const blockedReason = d.blocked_reason || null;
const stalled = d.stalled || false;
const stalledMin = d.stalled_minutes || 0;
const owns = d.owns || [];
const lastCommit = d.last_commit || null;
const isDynamic = a.dynamic || d.dynamic || false;

// Card class
let cardClass = 'ac';
if (deboarded) cardClass = 'ac off';
else if (blockedBy) cardClass = 'ac blocked-card';
else if (stalled) cardClass = 'ac stalled';

// Dot class
let dotClass = deboarded ? 'session' : (blockedBy ? 'offline' : (stalled ? 'busy' : presence));

// Status badge — only for non-default states
let stBadge = '';
if (deboarded) stBadge = '<span class="ac-status st-deboarded">de-boarded</span>';
else if (blockedBy) stBadge = '<span class="ac-status st-deboarded">blocked</span>';
else if (stalled) stBadge = `<span class="ac-status st-busy">stalled ${stalledMin}m</span>`;
else if (presence === 'busy') stBadge = '<span class="ac-status st-busy">working</span>';
else if (presence === 'typing') stBadge = '<span class="ac-status st-typing">thinking</span>';
else if (presence === 'offline') stBadge = '<span class="ac-status st-offline">offline</span>';

// Activity/task line (manual overrides auto)
let actLine = '';
if (task) actLine = `<div class="ac-activity">${esc(task)}</div>`;
else if (activity && !deboarded) actLine = `<div class="ac-activity ${presence === 'typing' ? 'tp' : ''}">${esc(activity)}</div>`;

// Progress bar
let progressHtml = '';
if (progress != null && !deboarded) {
  const etaText = eta ? ` · ~${esc(eta)}` : '';
  progressHtml = `
    <div class="ac-progress">
      <div class="ac-progress-bar"><div class="ac-progress-fill" style="width:${progress}%"></div></div>
      <span class="ac-progress-text">${progress}%${etaText}</span>
    </div>`;
}

// Blocker
let blockerHtml = '';
if (blockedBy && !deboarded) {
  blockerHtml = `<div class="ac-blocker">⚠ blocked: ${esc(blockedReason || blockedBy)}</div>`;
}

// Stalled
let stalledHtml = '';
if (stalled && !blockedBy && !deboarded) {
  stalledHtml = `<div class="ac-stalled-text">${stalledMin}m+ on same file</div>`;
}

// Owned files pills
let ownsHtml = '';
if (owns.length > 0) {
  const shown = owns.slice(0, 3).map(f => `<span class="ac-own-pill">${esc(f)}</span>`).join('');
  const more = owns.length > 3 ? `<span class="ac-own-more">+${owns.length - 3}</span>` : '';
  ownsHtml = `<div class="ac-owns" title="${esc(owns.join(', '))}">${shown}${more}</div>`;
}

// Last commit
let commitHtml = '';
if (lastCommit && !deboarded) {
  commitHtml = `<div class="ac-commit">${esc(lastCommit.hash)} ${esc(lastCommit.message)}</div>`;
}

// Dynamic badge
const dynBadge = isDynamic ? '<span class="ac-dynamic" title="Dynamic agent">~</span>' : '';
```

Then the card `innerHTML`:

```javascript
card.innerHTML = `
  <div class="ac-row1">
    <span class="dot ${dotClass}"></span>
    <span class="ac-name" style="color:${color(a.name)}">${a.name}${dynBadge}</span>
    <div class="ac-actions">${btns}</div>
  </div>
  <div class="ac-row2">
    <span class="ac-role" title="${esc(a.role || '')}">${role}</span>
    ${stBadge}
  </div>
  ${actLine}
  ${progressHtml}
  ${blockerHtml}
  ${stalledHtml}
  ${ownsHtml}
  ${commitHtml}
`;
```

- [ ] **Step 3: Test manually**

```bash
cd ~/coders-war-room
pkill -f "python3.*server.py"; sleep 1
python3 server.py &
sleep 2
open http://localhost:5680
```

Test flow:
1. Cards should show owned file pills for each agent
2. Use CLI to set status: `WARROOM_AGENT_NAME=phase-1 ./warroom.sh status "fixing imports" --progress 40 --eta 3m`
3. Card should show progress bar within 2s
4. Set a blocker: `WARROOM_AGENT_NAME=phase-3 ./warroom.sh status --blocked phase-1 "needs config change"`
5. phase-3 card should show red blocker, phase-1 should receive auto-DM
6. Clear: `WARROOM_AGENT_NAME=phase-3 ./warroom.sh status --clear`

- [ ] **Step 4: Commit**

```bash
cd ~/coders-war-room
git add static/index.html
git commit -m "feat: live dashboard agent cards with progress, blockers, ownership, staleness"
```

---

### Task 6: Integration Test

**Files:**
- Modify: `~/coders-war-room/tests/test_integration.py`

- [ ] **Step 1: Add integration tests**

```python
def test_status_flow():
    """Test the full status lifecycle: set, query, clear."""
    # Set status
    resp = httpx.post(f"{SERVER_URL}/api/agents/phase-1/status", json={
        "task": "integration test task",
        "progress": 75,
        "eta": "2m",
    })
    assert resp.status_code == 200

    # Query status
    resp = httpx.get(f"{SERVER_URL}/api/agents/phase-1/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["task"] == "integration test task"
    assert data["progress"] == 75
    assert data["eta"] == "2m"

    # Clear
    resp = httpx.post(f"{SERVER_URL}/api/agents/phase-1/status", json={"clear": True})
    assert resp.status_code == 200

    # Verify cleared
    resp = httpx.get(f"{SERVER_URL}/api/agents/phase-1/status")
    data = resp.json()
    assert data["task"] is None


def test_ownership_api():
    """Test that ownership patterns are resolved."""
    resp = httpx.get(f"{SERVER_URL}/api/agents/phase-1/owns")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent"] == "phase-1"
    assert isinstance(data["patterns"], list)
    assert isinstance(data["resolved"], list)
```

- [ ] **Step 2: Run integration tests**

```bash
cd ~/coders-war-room
python3 -m pytest tests/test_integration.py -v -s
```

- [ ] **Step 3: Commit**

```bash
cd ~/coders-war-room
git add tests/test_integration.py
git commit -m "test: add integration tests for status flow and ownership API"
```
