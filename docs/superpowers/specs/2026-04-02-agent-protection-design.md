# Package D: Agent Protection & Server Management — Design Spec

**Date:** 2026-04-02
**Goal:** Prevent accidental agent session death, detect dead sessions with one-click recovery, and add always-visible server management to the header.
**Principle:** Prevention over recovery. Agents are valuable — protect their sessions.

---

## 1. Session Protection (Test Isolation)

### Problem

Integration tests use `pkill -f "python3.*server.py"` which kills the live server on port 5680. This disrupts all agents mid-session. Tests then start their own server on the same port, further conflicting with live agents.

### Solution

Integration tests run on a **separate port (5681)** with a separate database. The live server on 5680 is never touched.

**Changes:**

- `tests/test_integration.py`: change `SERVER_URL` to `http://localhost:5681`
- The integration test `server` fixture:
  - Starts the server on port 5681: `PORT=5681 python3 server.py`
  - Uses a temp database (not `warroom.db`)
  - No `pkill` — starts its own isolated process, kills only that PID on teardown
- `start.sh`: remove any `pkill` patterns. Start by PID or LaunchAgent only.
- `stop.sh`: kill by PID file or `launchctl bootout` only. Never `pkill -f`.

**Result:** Running `pytest` while agents are active is completely safe. Tests hit port 5681, agents use port 5680. No interference.

---

## 2. Health Watchdog + One-Click Recovery

### Problem

Tmux sessions can die silently (macOS resource pressure, accidental kill, etc.). No one knows until they try to message that agent. Context is lost and the agent is offline.

### Solution

The existing `agent_status_loop` (runs every 2s) already checks tmux session existence via `get_agent_activity()`. Add a `session_alive` field to the WebSocket push. The frontend shows a red recovery prompt when `in_room=True` but `session_alive=False`.

### WebSocket Push (enhanced)

```json
{
  "type": "agent_status",
  "agents": {
    "phase-6": {
      "presence": "offline",
      "activity": null,
      "in_room": true,
      "session_alive": false,
      ...
    }
  }
}
```

### Agent Card — Dead Session State

When `in_room=True` and `session_alive=False`:

```
🔴 phase-6                         [Recover]
   Skill Framework
   ⚠ Session lost — click Recover to restart
```

- Red dot, red card border
- Only action button: `[Recover]`
- No cli/@/x buttons (session is dead, those don't work)

### Recovery Endpoint

`POST /api/agents/{name}/recover`

**Guard:** Refuses if agent is de-boarded (`agent_membership[name] == False`):
```json
{"error": "Agent was de-boarded — use reboard first"}
```

**Recovery steps:**
1. Validate: agent must be in_room=True and tmux session dead
2. Look up agent config (name, role, directory, model, permissions) from AGENTS list
3. Create fresh tmux session: `tmux new-session -d -s warroom-<name> -c <dir>`
4. Configure: mouse on, scrollback, window title
5. Start Claude Code with original model and permission flags
6. Wait for ready (up to 30s)
7. Inject: `Read ~/coders-war-room/startup.md — you are <name>, session recovered. Acknowledge and wait for instructions.`
8. Post system message: `<name> session recovered (context lost — fresh start)`
9. Update agent status in WebSocket push

**Response:**
```json
{
  "status": "recovered",
  "agent": "phase-6",
  "warning": "Conversation context was lost — agent starts fresh"
}
```

### Recovery Config Preservation

When an agent is created (via config.yaml or web UI), the server stores its creation config:
```python
agent_config: dict[str, dict] = {}
# Example: {"phase-6": {"directory": "/Users/.../contextualise", "model": "opus", "skip_permissions": true}}
```

For config.yaml agents: directory = `PROJECT_PATH`, model = default (opus), permissions = from config.
For dynamic agents: stored at creation time in `create_agent()`.

This config is used by the recover endpoint to recreate the session identically.

---

## 3. Server Management in Header

### Problem

No way to see server health or manage the LaunchAgent from the web UI. The header only shows LIVE/offline and Roll Call.

### Solution

Add a server info section to the left side of the header:

```
WAR ROOM | North Star Daemon    uptime: 2h 14m    LaunchAgent: active    [Restart]  [Logs]    LIVE    Roll Call
```

### Fields

| Field | Source | Display |
|-------|--------|---------|
| **Uptime** | Server tracks `startup_time = time.time()` at boot | `2h 14m` — pushed via WebSocket every 2s with agent_status |
| **LaunchAgent** | `launchctl list | grep com.warroom.server` | Green "active" / grey "not installed" |
| **Restart** | `POST /api/server/restart` | Button. Triggers `sys.exit(0)` — LaunchAgent restarts the process. If no LaunchAgent, returns error. |
| **Logs** | `GET /api/server/logs` | Button. Opens server log in new tab as styled text. |

### API

**`GET /api/server/health`**
```json
{
  "uptime_seconds": 8040,
  "uptime_human": "2h 14m",
  "port": 5680,
  "launchagent_active": true,
  "agent_count": 8,
  "agents_in_room": 6,
  "agents_alive": 5
}
```

**`POST /api/server/restart`**

If LaunchAgent is installed: calls `sys.exit(0)`. LaunchAgent's `KeepAlive` restarts the process within seconds. Returns `{"status": "restarting"}` (the response may not complete if the shutdown is fast).

If LaunchAgent is NOT installed: returns `{"error": "LaunchAgent not installed — install first: ./install-service.sh install"}`.

**`GET /api/server/logs`**

Reads the last 500 lines of `/tmp/warroom-server.log` and returns as styled HTML (dark theme, monospace, like the markdown preview).

### WebSocket Push (enhanced)

The agent_status push now includes server health:
```json
{
  "type": "agent_status",
  "server": {
    "uptime": "2h 14m",
    "launchagent": true
  },
  "agents": { ... }
}
```

The frontend updates the header from this data every 2 seconds.

---

## What This Does NOT Include

- No automatic recovery (user clicks Recover — stays in control)
- No context preservation on recovery (fundamental Claude Code limitation)
- No tmux session backup/snapshot
- No multi-server support
- No remote server management
