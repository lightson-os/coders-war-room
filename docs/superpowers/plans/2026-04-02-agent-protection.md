# Package D: Agent Protection & Server Management — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent accidental agent session death, detect dead sessions with one-click recovery, and add always-visible server management to the header.

**Architecture:** Test isolation via separate port (5681). Health watchdog extends existing agent_status_loop with session_alive field. Recovery endpoint reuses create_agent logic. Server health tracked via startup timestamp and launchctl checks.

**Tech Stack:** Python 3.12, FastAPI, tmux, macOS launchctl, vanilla JS

**Design Spec:** `docs/superpowers/specs/2026-04-02-agent-protection-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `server.py` | Modify | Recovery endpoint, server health endpoints, startup_time, agent_config store, session_alive in status loop |
| `static/index.html` | Modify | Recovery button on dead agent cards, server management bar in header |
| `tests/test_integration.py` | Modify | Use port 5681, no pkill |
| `start.sh` | Modify | Remove pkill, use PID/LaunchAgent only |
| `stop.sh` | Modify | Remove pkill, use PID/LaunchAgent only |
| `tests/test_api.py` | Modify | Test for recovery and server health |
| `tests/conftest.py` | Modify | Patch new globals |

---

### Task 1: Test Isolation — Separate Port for Integration Tests

**Files:**
- Modify: `~/coders-war-room/tests/test_integration.py`

- [ ] **Step 1: Change SERVER_URL to port 5681**

In `tests/test_integration.py`, change line 17:

```python
SERVER_URL = "http://localhost:5681"
```

- [ ] **Step 2: Rewrite the server fixture to use port 5681 and no pkill**

Replace the existing `server` fixture (around line 23) with:

```python
@pytest.fixture(scope="module", autouse=True)
def server():
    """Start an isolated test server on port 5681 — never touches the live server on 5680."""
    # Use a temp database for test isolation
    test_db = Path(__file__).parent.parent / "test_warroom.db"
    if test_db.exists():
        test_db.unlink()

    env = {**os.environ, "WARROOM_TEST_PORT": "5681", "WARROOM_TEST_DB": str(test_db)}
    proc = subprocess.Popen(
        ["python3", "-c", f"""
import sys, os
sys.path.insert(0, '{Path(__file__).parent.parent}')
os.environ['WARROOM_TEST_PORT'] = '5681'
os.environ['WARROOM_TEST_DB'] = '{test_db}'

# Patch before importing server
import server
server.PORT = 5681
server.DB_PATH = __import__('pathlib').Path('{test_db}')

import uvicorn
uvicorn.run(server.app, host='0.0.0.0', port=5681, log_level='error')
"""],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(3)  # Wait for test server to start
    yield proc
    proc.terminate()
    proc.wait(timeout=5)
    if test_db.exists():
        test_db.unlink()
```

- [ ] **Step 3: Add missing imports if needed**

Ensure `os` and `Path` are imported at the top of test_integration.py:

```python
import os
from pathlib import Path
```

- [ ] **Step 4: Run integration tests (should pass without touching live server)**

```bash
cd ~/coders-war-room
# Verify live server is still running on 5680
curl -s http://localhost:5680/api/agents > /dev/null && echo "Live server: OK"
# Run tests on port 5681
python3 -m pytest tests/test_integration.py -v -s
# Verify live server is STILL running on 5680 (not killed)
curl -s http://localhost:5680/api/agents > /dev/null && echo "Live server: still OK"
```

- [ ] **Step 5: Commit**

```bash
cd ~/coders-war-room
git add tests/test_integration.py
git commit -m "feat: isolate integration tests on port 5681 — never kill live server"
```

---

### Task 2: Safe start.sh and stop.sh

**Files:**
- Modify: `~/coders-war-room/start.sh`
- Modify: `~/coders-war-room/stop.sh`

- [ ] **Step 1: Update start.sh — remove all pkill**

Replace `~/coders-war-room/start.sh`:

```bash
#!/bin/bash
# Coder's War Room — Start Everything
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=5680
PLIST_DEST="$HOME/Library/LaunchAgents/com.warroom.server.plist"
PID_FILE="/tmp/warroom-server.pid"

echo "==========================================="
echo "  CODER'S WAR ROOM — Starting Up"
echo "==========================================="

# Check if server is already running
if curl -s "http://localhost:$PORT/api/agents" > /dev/null 2>&1; then
    echo "Server already running on port $PORT"
elif [ -f "$PLIST_DEST" ]; then
    echo "Starting server via LaunchAgent..."
    launchctl load "$PLIST_DEST" 2>/dev/null || true
    sleep 2
    echo "Server running (LaunchAgent managed, port $PORT)"
else
    echo "Starting server on port $PORT..."
    cd "$SCRIPT_DIR"
    nohup python3 server.py > /tmp/warroom-server.log 2>&1 &
    echo $! > "$PID_FILE"
    sleep 2
    if curl -s "http://localhost:$PORT/api/agents" > /dev/null 2>&1; then
        echo "Server started (PID: $(cat $PID_FILE))"
    else
        echo "ERROR: Server failed to start. Check /tmp/warroom-server.log"
        exit 1
    fi
fi

# Onboard agents
echo ""
"$SCRIPT_DIR/onboard.sh" "$@"

# Open web UI
echo ""
echo "Opening web UI..."
open "http://localhost:$PORT"
```

- [ ] **Step 2: Update stop.sh — use PID/bootout only**

Replace `~/coders-war-room/stop.sh`:

```bash
#!/bin/bash
# Coder's War Room — Stop Everything

echo "==========================================="
echo "  CODER'S WAR ROOM — Shutting Down"
echo "==========================================="

# Kill warroom tmux sessions
echo "Killing agent sessions..."
tmux list-sessions 2>/dev/null | grep "^warroom-" | cut -d: -f1 | while read -r session; do
    echo "  Killing: $session"
    tmux kill-session -t "$session" 2>/dev/null || true
done

# Stop server — LaunchAgent first, then PID file, then targeted pkill as last resort
PLIST_DEST="$HOME/Library/LaunchAgents/com.warroom.server.plist"
PID_FILE="/tmp/warroom-server.pid"

if [ -f "$PLIST_DEST" ] && launchctl list 2>/dev/null | grep -q com.warroom.server; then
    echo "Stopping server (LaunchAgent)..."
    launchctl bootout "gui/$(id -u)" com.warroom.server 2>/dev/null || true
    echo "Server stopped"
elif [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping server (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        echo "Server stopped"
    else
        echo "PID $PID not running"
        rm -f "$PID_FILE"
    fi
else
    echo "No server process found"
fi

echo ""
echo "War Room shut down."
```

- [ ] **Step 3: Commit**

```bash
cd ~/coders-war-room
git add start.sh stop.sh
git commit -m "fix: remove pkill from start/stop scripts — use PID and LaunchAgent only"
```

---

### Task 3: Server — Recovery Endpoint + Agent Config Store + Health API

**Files:**
- Modify: `~/coders-war-room/server.py`
- Modify: `~/coders-war-room/tests/test_api.py`
- Modify: `~/coders-war-room/tests/conftest.py`

- [ ] **Step 1: Add new state variables**

Add to server.py after existing state variables (around line 77):

```python
# Agent creation config (preserved for recovery)
agent_config: dict[str, dict] = {}
# Example: {"phase-1": {"directory": "/path", "model": "opus", "skip_permissions": True}}

# Server startup timestamp
import time as _time
SERVER_START_TIME = _time.time()
```

For config.yaml agents, populate agent_config in lifespan after reconcile:

```python
# In lifespan, after reconcile_tmux_sessions():
for a in AGENTS:
    if a["name"] not in agent_config:
        agent_config[a["name"]] = {
            "directory": AGENT_DIRS.get(a["name"], PROJECT_PATH),
            "model": "opus",
            "skip_permissions": True,
        }
```

- [ ] **Step 2: Add session_alive to agent_status_loop**

In the `agent_status_loop` function, where `agents_data[name]` is built, add:

```python
                "session_alive": tmux_session_exists(session),
```

- [ ] **Step 3: Add recovery endpoint**

Add before the deboard endpoint:

```python
@app.post("/api/agents/{agent_name}/recover")
async def recover_agent(agent_name: str):
    """Recover a dead agent session — re-creates tmux and starts Claude Code."""
    if agent_name not in AGENT_NAMES:
        return JSONResponse({"error": f"Unknown agent: {agent_name}"}, status_code=404)

    # Guard: refuse to recover de-boarded agents
    if not agent_membership.get(agent_name, False):
        return JSONResponse(
            {"error": f"Agent '{agent_name}' was de-boarded — use reboard first"},
            status_code=400,
        )

    session = AGENT_SESSIONS.get(agent_name, f"warroom-{agent_name}")

    # Guard: refuse if session is already alive
    if tmux_session_exists(session):
        return JSONResponse({"error": f"Agent '{agent_name}' session is already alive"}, status_code=400)

    # Get stored config
    config = agent_config.get(agent_name, {})
    agent_dir = config.get("directory", PROJECT_PATH)
    model = config.get("model", "opus")
    skip_perms = config.get("skip_permissions", True)

    try:
        # Create fresh tmux session
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session, "-x", "200", "-y", "50", "-c", agent_dir],
            check=True, capture_output=True, timeout=5,
        )
        subprocess.run(["tmux", "set-option", "-t", session, "mouse", "on"], capture_output=True, timeout=2)
        subprocess.run(["tmux", "set-option", "-t", session, "history-limit", "10000"], capture_output=True, timeout=2)
        subprocess.run(["tmux", "rename-window", "-t", session, agent_name], capture_output=True, timeout=2)

        # Set env var
        subprocess.run(
            ["tmux", "send-keys", "-t", session, f"export WARROOM_AGENT_NAME={agent_name}", "Enter"],
            capture_output=True, timeout=2,
        )
        await asyncio.sleep(0.5)

        # Start Claude Code
        model_flag = f"--model {model}" if model != "opus" else ""
        perms_flag = "--dangerously-skip-permissions" if skip_perms else ""
        cmd = f"cd {agent_dir} && claude {model_flag} {perms_flag}".strip()
        cmd = " ".join(cmd.split())
        subprocess.run(["tmux", "send-keys", "-t", session, cmd, "Enter"], capture_output=True, timeout=2)

        # Wait for ready
        for _ in range(15):
            await asyncio.sleep(2)
            if check_agent_ready(session):
                break

        # Inject recovery prompt
        injection = f"Read ~/coders-war-room/startup.md — you are {agent_name}, session recovered. Acknowledge with your name and role, then wait for instructions."
        send_to_tmux(session, injection)

        # Announce
        saved = await save_message("system", "all", f"{agent_name} session recovered (context lost — fresh start)", "system")
        await broadcast_ws({"type": "message", "message": saved})

        return {
            "status": "recovered",
            "agent": agent_name,
            "warning": "Conversation context was lost — agent starts fresh",
        }

    except subprocess.CalledProcessError as e:
        subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True)
        return JSONResponse({"error": f"Recovery failed: {e}"}, status_code=500)
```

- [ ] **Step 4: Add server health endpoints**

Add after the recovery endpoint:

```python
@app.get("/api/server/health")
async def server_health():
    """Return server health info."""
    uptime_s = int(_time.time() - SERVER_START_TIME)
    hours, remainder = divmod(uptime_s, 3600)
    minutes = remainder // 60
    uptime_human = f"{hours}h {minutes}m" if hours else f"{minutes}m"

    # Check LaunchAgent
    try:
        result = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=2,
        )
        la_active = "com.warroom.server" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        la_active = False

    alive = sum(1 for a in AGENTS if tmux_session_exists(a["tmux_session"]))
    in_room = sum(1 for a in AGENTS if agent_membership.get(a["name"], False))

    return {
        "uptime_seconds": uptime_s,
        "uptime_human": uptime_human,
        "port": PORT,
        "launchagent_active": la_active,
        "agent_count": len(AGENTS),
        "agents_in_room": in_room,
        "agents_alive": alive,
    }


@app.post("/api/server/restart")
async def server_restart():
    """Graceful restart — only works with LaunchAgent (KeepAlive restarts the process)."""
    try:
        result = subprocess.run(
            ["launchctl", "list"], capture_output=True, text=True, timeout=2,
        )
        if "com.warroom.server" not in result.stdout:
            return JSONResponse(
                {"error": "LaunchAgent not installed — run: ./install-service.sh install"},
                status_code=400,
            )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return JSONResponse({"error": "Cannot check LaunchAgent status"}, status_code=500)

    # Schedule shutdown in 1 second (so the response can be sent)
    async def delayed_exit():
        await asyncio.sleep(1)
        import sys
        sys.exit(0)
    asyncio.create_task(delayed_exit())
    return {"status": "restarting", "message": "Server will restart in 1 second"}


@app.get("/api/server/logs")
async def server_logs():
    """Serve the last 500 lines of the server log."""
    log_path = Path("/tmp/warroom-server.log")
    if not log_path.exists():
        return PlainTextResponse("No log file found", status_code=404)
    lines = log_path.read_text(errors="replace").split("\n")
    last_500 = "\n".join(lines[-500:])
    page = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8"><title>War Room — Server Logs</title>
<style>
  body {{ font-family: 'JetBrains Mono', monospace; font-size: 12px; background: #0d1117; color: #c9d1d9; padding: 20px; white-space: pre-wrap; word-break: break-all; line-height: 1.5; }}
  .path {{ color: #8b949e; margin-bottom: 16px; display: block; }}
</style>
</head><body>
<span class="path">/tmp/warroom-server.log (last 500 lines)</span>
{last_500}
</body></html>"""
    return HTMLResponse(page)
```

- [ ] **Step 5: Add server health to WebSocket push**

In `agent_status_loop`, add server health to the push. After building `agents_data`, before `json.dumps`:

```python
        # Server health for header
        uptime_s = int(_time.time() - SERVER_START_TIME)
        hours, remainder = divmod(uptime_s, 3600)
        minutes = remainder // 60
        uptime_human = f"{hours}h {minutes}m" if hours else f"{minutes}m"

        try:
            la_result = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=2)
            la_active = "com.warroom.server" in la_result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            la_active = False

        data = json.dumps({
            "type": "agent_status",
            "server": {"uptime": uptime_human, "launchagent": la_active},
            "agents": agents_data,
        })
```

- [ ] **Step 6: Store config for dynamic agents in create_agent()**

In the `create_agent()` endpoint, after adding to AGENTS/AGENT_NAMES/etc., add:

```python
        agent_config[req.name] = {
            "directory": agent_dir,
            "model": req.model,
            "skip_permissions": req.skip_permissions,
        }
```

- [ ] **Step 7: Write tests**

Add to `tests/test_api.py`:

```python
@pytest.mark.asyncio
async def test_server_health():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/server/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "uptime_seconds" in data
        assert "uptime_human" in data
        assert "launchagent_active" in data
        assert "agent_count" in data


@pytest.mark.asyncio
async def test_recover_deboarded_agent_refused():
    from server import app, agent_membership
    agent_membership["phase-1"] = False  # Simulate de-boarded
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/agents/phase-1/recover")
        assert resp.status_code == 400
        assert "de-boarded" in resp.json()["error"]
```

- [ ] **Step 8: Update conftest.py**

Add patches:

```python
    monkeypatch.setattr(server, "agent_config", {})
```

- [ ] **Step 9: Run all tests**

```bash
cd ~/coders-war-room
python3 -m pytest tests/test_api.py -v
```

- [ ] **Step 10: Commit**

```bash
cd ~/coders-war-room
git add server.py tests/test_api.py tests/conftest.py
git commit -m "feat: add recovery endpoint, server health API, session_alive tracking"
```

---

### Task 4: Frontend — Recovery Button + Server Management Header

**Files:**
- Modify: `~/coders-war-room/static/index.html`

- [ ] **Step 1: Add CSS for dead session state and server bar**

Add to the `<style>` block:

```css
/* ─── Dead session card ─── */
.ac.session-dead {
  border-color: rgba(255,82,82,0.4);
  background: rgba(255,82,82,0.03);
}

.ac-dead-warning {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  color: var(--red);
  margin-top: 4px;
  padding-left: 15px;
}

.abtn-recover {
  color: var(--red);
  border-color: rgba(255,82,82,0.3);
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 4px;
  background: transparent;
  cursor: pointer;
  transition: all 0.15s;
  animation: pulse-recover 2s infinite;
}
.abtn-recover:hover {
  background: var(--red-dim);
  border-color: var(--red);
}

@keyframes pulse-recover {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* ─── Server management bar ─── */
.server-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
}

.server-stat {
  color: var(--text-dim);
  letter-spacing: 0.5px;
}

.server-stat-value {
  color: var(--text-secondary);
}

.server-la-active {
  color: var(--green);
}

.server-la-inactive {
  color: var(--text-dim);
}

.server-btn {
  font-family: 'JetBrains Mono', monospace;
  font-size: 9px;
  padding: 2px 8px;
  border-radius: 3px;
  border: 1px solid var(--border-bright);
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.server-btn:hover {
  color: var(--text-primary);
  border-color: var(--text-secondary);
}
```

- [ ] **Step 2: Update the header HTML**

Replace the header contents with:

```html
<header>
  <div class="h-left">
    <span class="h-logo">War Room</span>
    <span class="h-sep"></span>
    <span class="h-sub">North Star Daemon</span>
  </div>
  <div class="server-bar">
    <span class="server-stat">uptime: <span id="srvUptime" class="server-stat-value">--</span></span>
    <span class="server-stat">LaunchAgent: <span id="srvLA" class="server-la-inactive">--</span></span>
    <button class="server-btn" id="srvRestart" title="Restart server (requires LaunchAgent)">Restart</button>
    <button class="server-btn" id="srvLogs" title="View server logs">Logs</button>
    <span id="connBadge" class="conn off">offline</span>
    <button id="rollCallBtn" class="conn on" style="cursor:pointer" title="Check who's alive">Roll Call</button>
  </div>
</header>
```

- [ ] **Step 3: Update WebSocket handler for server health**

In the `ws.onmessage` handler, where `d.type === 'agent_status'` is handled, add:

```javascript
      // Update server health in header
      if (d.server) {
        $('srvUptime').textContent = d.server.uptime || '--';
        const laEl = $('srvLA');
        if (d.server.launchagent) {
          laEl.textContent = 'active';
          laEl.className = 'server-la-active';
        } else {
          laEl.textContent = 'not installed';
          laEl.className = 'server-la-inactive';
        }
      }
```

- [ ] **Step 4: Add server button handlers**

Add to the JavaScript, near the Roll Call handler:

```javascript
// ═══════════ Server Management ═══════════
$('srvRestart').onclick = async () => {
  if (!confirm('Restart the server? Agents keep running but dispatch pauses briefly.')) return;
  try {
    await fetch('/api/server/restart', { method: 'POST' });
  } catch (e) { /* server died — expected */ }
  $('srvRestart').textContent = 'Restarting...';
  setTimeout(() => { $('srvRestart').textContent = 'Restart'; }, 5000);
};

$('srvLogs').onclick = () => { window.open('/api/server/logs', '_blank'); };
```

- [ ] **Step 5: Update renderAgents for dead session recovery**

In the `activeAgents.forEach` block, after computing `cardClass`, add a session-dead check:

```javascript
    // Check for dead session (in_room but tmux session gone)
    const sessionAlive = d.session_alive !== false;
    const sessionDead = !deboarded && !sessionAlive && presence === 'offline';

    if (sessionDead) cardClass = 'ac session-dead';
```

Replace the buttons logic for active agents:

```javascript
    let btns = '';
    if (sessionDead) {
      btns = `<button class="abtn abtn-recover" data-action="recover" data-agent="${a.name}" title="Recover dead session">Recover</button>`;
    } else {
      btns = `
        <button class="abtn abtn-cli" data-action="attach" data-agent="${a.name}" title="Open CLI in Terminal">cli</button>
        <button class="abtn abtn-msg" data-action="msg" data-agent="${a.name}" title="Direct message">@</button>
        <button class="abtn abtn-off" data-action="deboard" data-agent="${a.name}" title="De-board from room">x</button>
      `;
    }
```

Add a dead-session warning line after `commitHtml`:

```javascript
    let deadHtml = '';
    if (sessionDead) {
      deadHtml = '<div class="ac-dead-warning">⚠ Session lost — click Recover to restart</div>';
    }
```

Include it in the card innerHTML:

```javascript
      ${actLine}${progressHtml}${blockerHtml}${stalledHtml}${deadHtml}${ownsHtml}${commitHtml}
```

Add the recover action to the button handler:

```javascript
        else if (action === 'recover') {
          btn.textContent = 'Recovering...';
          btn.disabled = true;
          fetch(`/api/agents/${agent}/recover`, { method: 'POST' }).then(r => r.json()).then(d => {
            if (d.status === 'recovered') {
              btn.textContent = 'Recovered!';
            } else {
              btn.textContent = 'Failed';
              alert(d.error || 'Recovery failed');
            }
          }).catch(() => { btn.textContent = 'Failed'; });
        }
```

- [ ] **Step 6: Test manually**

```bash
cd ~/coders-war-room
pkill -f "python3.*server.py"; sleep 1
python3 server.py &
sleep 2
open http://localhost:5680
```

Verify:
1. Header shows uptime, LaunchAgent status, Restart, Logs buttons
2. Uptime increments every 2s
3. Logs button opens log in new tab
4. Kill a test tmux session: `tmux kill-session -t warroom-test-agent-4`
5. Within 2-4 seconds, that agent's card should show red "Session lost — Recover" button
6. Click Recover — agent should come back

- [ ] **Step 7: Commit**

```bash
cd ~/coders-war-room
git add static/index.html
git commit -m "feat: add recovery button for dead sessions and server management header"
```
