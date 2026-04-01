# Coder's War Room Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local real-time chat system where 8 Claude Code agents and the user share a single conversation, with autonomous message delivery via tmux.

**Architecture:** FastAPI server (single file) with SQLite (WAL mode) for storage, WebSocket for the web UI, and tmux send-keys with readiness guards for agent delivery. All local, no external services.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, aiosqlite, PyYAML, tmux, vanilla HTML/CSS/JS

**Design Spec:** `docs/superpowers/specs/2026-04-01-coders-war-room-design.md`

---

### Task 1: Project Setup & Dependencies

**Files:**
- Create: `~/coders-war-room/requirements.txt`
- Create: `~/coders-war-room/config.yaml`
- Create: `~/coders-war-room/static/` (directory)
- Create: `~/coders-war-room/tests/` (directory)

- [ ] **Step 1: Install tmux**

```bash
brew install tmux
```

Verify: `tmux -V` should print `tmux 3.x`

- [ ] **Step 2: Create requirements.txt**

Create `~/coders-war-room/requirements.txt`:

```
fastapi>=0.128.0
uvicorn>=0.35.0
aiosqlite>=0.20.0
pyyaml>=6.0
httpx>=0.27.0
```

- [ ] **Step 3: Install Python dependencies**

```bash
cd ~/coders-war-room
pip3 install -r requirements.txt
```

Verify: `python3 -c "import aiosqlite; print('OK')"` prints `OK`

- [ ] **Step 4: Create config.yaml**

Create `~/coders-war-room/config.yaml`:

```yaml
port: 5680
project_path: ~/contextualise

agents:
  - name: supervisor
    role: "Oversees all phases, coordinates cross-phase wiring, resolves conflicts"
    tmux_session: warroom-supervisor

  - name: phase-1
    role: "Phase 1 owner — responsible for Phase 1 code and wiring"
    tmux_session: warroom-phase-1

  - name: phase-2
    role: "Phase 2 owner — responsible for Phase 2 code and wiring"
    tmux_session: warroom-phase-2

  - name: phase-3
    role: "Phase 3 owner — responsible for Phase 3 code and wiring"
    tmux_session: warroom-phase-3

  - name: phase-4
    role: "Phase 4 owner — responsible for Phase 4 code and wiring"
    tmux_session: warroom-phase-4

  - name: phase-5
    role: "Phase 5 owner — responsible for Phase 5 code and wiring"
    tmux_session: warroom-phase-5

  - name: phase-6
    role: "Phase 6 owner — responsible for Phase 6 code and wiring"
    tmux_session: warroom-phase-6

  - name: git-agent
    role: "Handles all git operations: commits, branches, PRs, conflict resolution. NEVER execute git commands without posting plan and receiving confirmation from gurvinder or supervisor first."
    tmux_session: warroom-git-agent
```

- [ ] **Step 5: Create directory structure**

```bash
mkdir -p ~/coders-war-room/static ~/coders-war-room/tests
```

- [ ] **Step 6: Commit**

```bash
cd ~/coders-war-room
git add requirements.txt config.yaml
git commit -m "feat: add project setup — requirements and agent config"
```

---

### Task 2: Server — Database Layer & REST API

**Files:**
- Create: `~/coders-war-room/server.py`
- Create: `~/coders-war-room/tests/test_api.py`

- [ ] **Step 1: Write the failing test**

Create `~/coders-war-room/tests/test_api.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.mark.asyncio
async def test_post_message():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/messages", json={
            "sender": "phase-1",
            "target": "all",
            "content": "Hello war room",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["sender"] == "phase-1"
        assert data["target"] == "all"
        assert data["content"] == "Hello war room"
        assert data["id"] is not None
        assert data["timestamp"] is not None


@pytest.mark.asyncio
async def test_get_messages():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Post two messages
        await client.post("/api/messages", json={
            "sender": "phase-1", "content": "First message",
        })
        await client.post("/api/messages", json={
            "sender": "phase-2", "content": "Second message",
        })
        resp = await client.get("/api/messages?limit=10")
        assert resp.status_code == 200
        messages = resp.json()
        assert len(messages) >= 2
        # Messages should be in chronological order
        contents = [m["content"] for m in messages]
        assert "First message" in contents
        assert "Second message" in contents


@pytest.mark.asyncio
async def test_get_single_message():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/messages", json={
            "sender": "supervisor", "content": "A long message for retrieval",
        })
        msg_id = resp.json()["id"]
        resp = await client.get(f"/message/{msg_id}")
        assert resp.status_code == 200
        assert "A long message for retrieval" in resp.text


@pytest.mark.asyncio
async def test_get_agents():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/agents")
        assert resp.status_code == 200
        agents = resp.json()
        names = [a["name"] for a in agents]
        assert "supervisor" in names
        assert "phase-1" in names
        assert "git-agent" in names
        assert len(agents) == 8


@pytest.mark.asyncio
async def test_direct_message():
    from server import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/messages", json={
            "sender": "supervisor",
            "target": "phase-1",
            "content": "Fix the state import",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["target"] == "phase-1"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/coders-war-room
python3 -m pytest tests/test_api.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'server'`

- [ ] **Step 3: Write the server implementation**

Create `~/coders-war-room/server.py`:

```python
import asyncio
import json
import subprocess
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite
import yaml
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
CONFIG_PATH = Path(__file__).parent / "config.yaml"
with open(CONFIG_PATH) as f:
    CONFIG = yaml.safe_load(f)

DB_PATH = Path(__file__).parent / "warroom.db"
PORT = CONFIG.get("port", 5680)
AGENTS = CONFIG.get("agents", [])
AGENT_NAMES = {a["name"] for a in AGENTS}
AGENT_SESSIONS = {a["name"]: a["tmux_session"] for a in AGENTS}

MAX_TMUX_MSG_LEN = 500

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
connected_clients: list[WebSocket] = []
agent_queues: dict[str, list[dict]] = {}


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                sender TEXT NOT NULL,
                target TEXT NOT NULL DEFAULT 'all',
                content TEXT NOT NULL,
                type TEXT NOT NULL DEFAULT 'message'
            )
        """)
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)"
        )
        await db.commit()


async def save_message(sender: str, target: str, content: str, msg_type: str = "message") -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "INSERT INTO messages (timestamp, sender, target, content, type) VALUES (?, ?, ?, ?, ?)",
            (ts, sender, target, content, msg_type),
        )
        await db.commit()
        msg_id = cursor.lastrowid
    return {
        "id": msg_id,
        "timestamp": ts,
        "sender": sender,
        "target": target,
        "content": content,
        "type": msg_type,
    }


async def get_messages(limit: int = 200) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM messages ORDER BY id DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in reversed(rows)]


async def get_message_by_id(msg_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM messages WHERE id = ?", (msg_id,))
        row = await cursor.fetchone()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# tmux dispatch
# ---------------------------------------------------------------------------
def tmux_session_exists(session_name: str) -> bool:
    try:
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            timeout=2,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_agent_ready(session_name: str) -> bool:
    """Check if Claude Code is at its input prompt by inspecting the tmux pane."""
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session_name, "-p", "-l", "5"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return False
        lines = result.stdout.strip().split("\n")
        # Claude Code's TUI shows a prompt area when idle.
        # Look for common idle indicators in the last few lines:
        #   - a line ending with ">" (the input prompt)
        #   - an empty line at the very end (cursor waiting)
        # This heuristic may need calibration after first real run.
        for line in reversed(lines[-3:]):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.endswith(">") or stripped == ">":
                return True
        # If the last non-empty line doesn't look like a spinner or tool output,
        # assume idle (fallback for V1).
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def format_message_for_tmux(msg: dict) -> str:
    sender = msg["sender"]
    target = msg["target"]
    content = msg["content"]
    msg_type = msg.get("type", "message")

    if msg_type == "system":
        return f"[WARROOM SYSTEM] {content}"

    if target != "all":
        prefix = f"[WARROOM @{target}] {sender}"
    else:
        prefix = f"[WARROOM] {sender}"

    full = f"{prefix}: {content}"

    if len(full) > MAX_TMUX_MSG_LEN:
        msg_id = msg.get("id", "?")
        truncated = full[: MAX_TMUX_MSG_LEN - 80]
        full = f"{truncated}... [Full message at http://localhost:{PORT}/message/{msg_id}]"

    return full


def format_batch_for_tmux(messages: list[dict]) -> str:
    lines = [f"[WARROOM] {len(messages)} messages while you were busy:\n"]
    for msg in messages:
        lines.append(format_message_for_tmux(msg))
    return "\n".join(lines)


def send_to_tmux(session_name: str, text: str):
    """Inject text into a tmux session. Uses a temp buffer to avoid shell escaping issues."""
    try:
        # Use tmux load-buffer + paste-buffer for reliable delivery of complex text
        subprocess.run(
            ["tmux", "set-buffer", "-b", "warroom", text],
            capture_output=True,
            timeout=5,
        )
        subprocess.run(
            ["tmux", "paste-buffer", "-b", "warroom", "-t", session_name],
            capture_output=True,
            timeout=5,
        )
        # Press Enter to submit
        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, "Enter"],
            capture_output=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


async def dispatch_to_agents(msg: dict):
    """Dispatch a message to all agents except the sender."""
    for agent in AGENTS:
        name = agent["name"]
        session = agent["tmux_session"]

        if name == msg["sender"]:
            continue

        if not tmux_session_exists(session):
            continue

        if check_agent_ready(session):
            # Flush any queued messages first, then deliver this one
            if name in agent_queues and agent_queues[name]:
                queued = agent_queues.pop(name)
                queued.append(msg)
                text = format_batch_for_tmux(queued)
            else:
                text = format_message_for_tmux(msg)
            send_to_tmux(session, text)
        else:
            # Agent is busy — queue the message
            if name not in agent_queues:
                agent_queues[name] = []
            agent_queues[name].append(msg)


async def flush_queues_loop():
    """Background: deliver queued messages to agents that become ready."""
    while True:
        await asyncio.sleep(2)
        for agent in AGENTS:
            name = agent["name"]
            session = agent["tmux_session"]

            if name not in agent_queues or not agent_queues[name]:
                continue
            if not tmux_session_exists(session):
                continue
            if not check_agent_ready(session):
                continue

            messages = agent_queues.pop(name)
            if len(messages) == 1:
                text = format_message_for_tmux(messages[0])
            else:
                text = format_batch_for_tmux(messages)
            send_to_tmux(session, text)


async def agent_status_loop():
    """Background: push agent online/offline status to web clients every 5s."""
    while True:
        await asyncio.sleep(5)
        status = {a["name"]: tmux_session_exists(a["tmux_session"]) for a in AGENTS}
        data = json.dumps({"type": "agent_status", "status": status})
        for client in connected_clients[:]:
            try:
                await client.send_text(data)
            except Exception:
                if client in connected_clients:
                    connected_clients.remove(client)


# ---------------------------------------------------------------------------
# WebSocket broadcast helper
# ---------------------------------------------------------------------------
async def broadcast_ws(data: dict, exclude: Optional[WebSocket] = None):
    payload = json.dumps(data)
    for client in connected_clients[:]:
        if client is exclude:
            continue
        try:
            await client.send_text(payload)
        except Exception:
            if client in connected_clients:
                connected_clients.remove(client)


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task1 = asyncio.create_task(flush_queues_loop())
    task2 = asyncio.create_task(agent_status_loop())
    yield
    task1.cancel()
    task2.cancel()


app = FastAPI(lifespan=lifespan)


class MessageCreate(BaseModel):
    sender: str
    target: str = "all"
    content: str
    type: str = "message"


@app.post("/api/messages")
async def create_message(msg: MessageCreate):
    saved = await save_message(msg.sender, msg.target, msg.content, msg.type)
    await broadcast_ws({"type": "message", "message": saved})
    await dispatch_to_agents(saved)
    return saved


@app.get("/api/messages")
async def list_messages(limit: int = 200):
    return await get_messages(limit)


@app.get("/message/{msg_id}")
async def get_single_message(msg_id: int):
    msg = await get_message_by_id(msg_id)
    if msg:
        return PlainTextResponse(msg["content"])
    return PlainTextResponse("Message not found", status_code=404)


@app.get("/api/agents")
async def list_agents():
    return [
        {
            "name": a["name"],
            "role": a["role"],
            "online": tmux_session_exists(a["tmux_session"]),
        }
        for a in AGENTS
    ]


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    try:
        # Send history on connect
        messages = await get_messages(200)
        await ws.send_text(json.dumps({"type": "history", "messages": messages}))

        # Send current agent status
        status = {a["name"]: tmux_session_exists(a["tmux_session"]) for a in AGENTS}
        await ws.send_text(json.dumps({"type": "agent_status", "status": status}))

        # Listen for messages from the web UI
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            saved = await save_message(
                sender=data.get("sender", "gurvinder"),
                target=data.get("target", "all"),
                content=data["content"],
                msg_type=data.get("type", "message"),
            )
            await broadcast_ws({"type": "message", "message": saved}, exclude=ws)
            await dispatch_to_agents(saved)
    except WebSocketDisconnect:
        if ws in connected_clients:
            connected_clients.remove(ws)


@app.get("/")
async def root():
    html_path = Path(__file__).parent / "static" / "index.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text())
    return HTMLResponse("<h1>War Room — static/index.html not found</h1>")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/coders-war-room
python3 -m pytest tests/test_api.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Quick manual smoke test**

```bash
cd ~/coders-war-room
python3 server.py &
SERVER_PID=$!
sleep 1

# Post a message
curl -s -X POST http://localhost:5680/api/messages \
  -H "Content-Type: application/json" \
  -d '{"sender":"test","content":"Hello war room"}'

# Get messages
curl -s http://localhost:5680/api/messages | python3 -m json.tool

# Get agents
curl -s http://localhost:5680/api/agents | python3 -m json.tool

# Cleanup
kill $SERVER_PID
```

Expected: POST returns JSON with message ID. GET returns array with the message. Agents endpoint returns 8 agents (all offline since no tmux sessions).

- [ ] **Step 6: Commit**

```bash
cd ~/coders-war-room
git add server.py tests/test_api.py
git commit -m "feat: add server with DB, REST API, WebSocket, and tmux dispatch"
```

---

### Task 3: Agent CLI — warroom.sh

**Files:**
- Create: `~/coders-war-room/warroom.sh`

- [ ] **Step 1: Write warroom.sh**

Create `~/coders-war-room/warroom.sh`:

```bash
#!/bin/bash
# Coder's War Room — Agent CLI
# Usage:
#   warroom.sh post "message"                    # broadcast
#   warroom.sh post --to <agent> "message"       # direct message
#   warroom.sh history                            # last 20 messages
#   warroom.sh history --count 50                 # last 50 messages

WARROOM_SERVER="${WARROOM_SERVER_URL:-http://localhost:5680}"
WARROOM_AGENT="${WARROOM_AGENT_NAME:-unknown}"

post_message() {
    local target="all"
    if [ "$1" = "--to" ]; then
        target="$2"
        shift 2
    fi
    local message="$*"

    if [ -z "$message" ]; then
        echo "Error: no message provided"
        echo "Usage: warroom.sh post [--to agent] message"
        return 1
    fi

    # Escape double quotes and backslashes in the message for JSON
    local escaped
    escaped=$(printf '%s' "$message" | python3 -c 'import sys,json; print(json.dumps(sys.stdin.read()))')

    local response
    response=$(curl -s -w "\n%{http_code}" -X POST "$WARROOM_SERVER/api/messages" \
        -H "Content-Type: application/json" \
        -d "{\"sender\": \"$WARROOM_AGENT\", \"target\": \"$target\", \"content\": $escaped}")

    local http_code
    http_code=$(echo "$response" | tail -1)
    local body
    body=$(echo "$response" | head -n -1)

    if [ "$http_code" = "200" ]; then
        echo "OK — message sent"
    else
        echo "Error ($http_code): $body"
        return 1
    fi
}

show_history() {
    local count=20
    if [ "$1" = "--count" ]; then
        count="$2"
    fi

    curl -s "$WARROOM_SERVER/api/messages?limit=$count" | python3 -c "
import sys, json
try:
    msgs = json.load(sys.stdin)
    for m in msgs:
        ts = m['timestamp'][:19].replace('T', ' ')
        tag = f' @{m[\"target\"]}' if m['target'] != 'all' else ''
        prefix = f'[{ts}]{tag} {m[\"sender\"]}'
        print(f'{prefix}: {m[\"content\"]}')
except Exception as e:
    print(f'Error reading messages: {e}', file=sys.stderr)
"
}

case "$1" in
    post)
        shift
        post_message "$@"
        ;;
    history)
        shift
        show_history "$@"
        ;;
    *)
        echo "Coder's War Room — Agent CLI"
        echo ""
        echo "Usage:"
        echo "  warroom.sh post [--to agent] message   Send a message"
        echo "  warroom.sh history [--count N]          Show recent messages"
        echo ""
        echo "Agent identity: $WARROOM_AGENT"
        echo "Server: $WARROOM_SERVER"
        ;;
esac
```

- [ ] **Step 2: Make executable**

```bash
chmod +x ~/coders-war-room/warroom.sh
```

- [ ] **Step 3: Test against running server**

```bash
cd ~/coders-war-room
python3 server.py &
SERVER_PID=$!
sleep 1

# Test post
WARROOM_AGENT_NAME=phase-1 ./warroom.sh post "Testing the CLI tool"
# Expected: "OK — message sent"

# Test direct message
WARROOM_AGENT_NAME=supervisor ./warroom.sh post --to phase-1 "Fix the import"
# Expected: "OK — message sent"

# Test history
./warroom.sh history
# Expected: two messages displayed with timestamps

kill $SERVER_PID
```

- [ ] **Step 4: Commit**

```bash
cd ~/coders-war-room
git add warroom.sh
git commit -m "feat: add warroom.sh agent CLI for posting and reading messages"
```

---

### Task 4: Web Chat UI

**Files:**
- Create: `~/coders-war-room/static/index.html`

- [ ] **Step 1: Write the complete web UI**

Create `~/coders-war-room/static/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Coder's War Room</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }

  body {
    font-family: 'SF Mono', 'Fira Code', 'Consolas', monospace;
    background: #0d1117;
    color: #c9d1d9;
    height: 100vh;
    display: flex;
    flex-direction: column;
  }

  header {
    background: #161b22;
    border-bottom: 1px solid #30363d;
    padding: 12px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  header h1 {
    font-size: 16px;
    font-weight: 600;
    color: #58a6ff;
  }

  .connection-status {
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 12px;
    background: #1a1e24;
  }

  .connection-status.connected { color: #3fb950; }
  .connection-status.disconnected { color: #f85149; }

  .main-layout {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  /* Agent sidebar */
  .sidebar {
    width: 220px;
    background: #161b22;
    border-right: 1px solid #30363d;
    padding: 16px;
    overflow-y: auto;
  }

  .sidebar h2 {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #8b949e;
    margin-bottom: 12px;
  }

  .agent-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 8px;
    border-radius: 6px;
    cursor: pointer;
    margin-bottom: 2px;
    font-size: 13px;
  }

  .agent-item:hover { background: #1f2937; }
  .agent-item.selected { background: #1f6feb33; }

  .agent-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .agent-dot.online { background: #3fb950; box-shadow: 0 0 4px #3fb95066; }
  .agent-dot.offline { background: #484f58; }

  .agent-name { color: #c9d1d9; }

  /* Chat area */
  .chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 16px 20px;
  }

  .message {
    margin-bottom: 12px;
    padding: 8px 12px;
    border-radius: 8px;
    background: #161b22;
    border-left: 3px solid #30363d;
  }

  .message.direct {
    background: #1c2333;
    border-left-color: #f0883e;
  }

  .message.system {
    background: transparent;
    border-left: none;
    color: #8b949e;
    font-style: italic;
    font-size: 12px;
    padding: 4px 12px;
  }

  .message-header {
    display: flex;
    align-items: baseline;
    gap: 8px;
    margin-bottom: 4px;
  }

  .message-sender {
    font-weight: 600;
    font-size: 13px;
  }

  .message-target {
    font-size: 11px;
    color: #f0883e;
    background: #f0883e22;
    padding: 1px 6px;
    border-radius: 4px;
  }

  .message-time {
    font-size: 11px;
    color: #484f58;
  }

  .message-content {
    font-size: 13px;
    line-height: 1.5;
    white-space: pre-wrap;
    word-break: break-word;
  }

  /* Input area */
  .input-area {
    background: #161b22;
    border-top: 1px solid #30363d;
    padding: 12px 20px;
    display: flex;
    gap: 10px;
    align-items: flex-end;
  }

  .target-selector {
    background: #0d1117;
    border: 1px solid #30363d;
    color: #c9d1d9;
    padding: 8px 12px;
    border-radius: 6px;
    font-family: inherit;
    font-size: 13px;
    cursor: pointer;
  }

  .target-selector:focus { border-color: #58a6ff; outline: none; }

  .message-input {
    flex: 1;
    background: #0d1117;
    border: 1px solid #30363d;
    color: #c9d1d9;
    padding: 8px 12px;
    border-radius: 6px;
    font-family: inherit;
    font-size: 13px;
    resize: none;
    min-height: 38px;
    max-height: 120px;
  }

  .message-input:focus { border-color: #58a6ff; outline: none; }

  .send-btn {
    background: #238636;
    color: #fff;
    border: none;
    padding: 8px 20px;
    border-radius: 6px;
    font-family: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    white-space: nowrap;
  }

  .send-btn:hover { background: #2ea043; }
  .send-btn:disabled { background: #21262d; color: #484f58; cursor: default; }
</style>
</head>
<body>

<header>
  <h1>CODER'S WAR ROOM</h1>
  <span id="connStatus" class="connection-status disconnected">disconnected</span>
</header>

<div class="main-layout">
  <aside class="sidebar">
    <h2>Agents</h2>
    <div id="agentList"></div>
  </aside>

  <div class="chat-container">
    <div id="messages" class="messages"></div>

    <div class="input-area">
      <select id="targetSelect" class="target-selector">
        <option value="all">@all</option>
      </select>
      <textarea id="msgInput" class="message-input" placeholder="Type a message..." rows="1"></textarea>
      <button id="sendBtn" class="send-btn" disabled>Send</button>
    </div>
  </div>
</div>

<script>
// Agent color map — deterministic colors per agent name
const COLORS = {
  'gurvinder':  '#f0883e',
  'supervisor': '#bc8cff',
  'phase-1':    '#58a6ff',
  'phase-2':    '#3fb950',
  'phase-3':    '#f778ba',
  'phase-4':    '#79c0ff',
  'phase-5':    '#d2a8ff',
  'phase-6':    '#7ee787',
  'git-agent':  '#ffa657',
};

function getColor(name) {
  return COLORS[name] || '#8b949e';
}

// State
let ws = null;
let agentStatus = {};

// DOM
const messagesEl = document.getElementById('messages');
const msgInput = document.getElementById('msgInput');
const sendBtn = document.getElementById('sendBtn');
const targetSelect = document.getElementById('targetSelect');
const connStatus = document.getElementById('connStatus');
const agentList = document.getElementById('agentList');

// WebSocket
function connect() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  ws = new WebSocket(`${protocol}//${location.host}/ws`);

  ws.onopen = () => {
    connStatus.textContent = 'connected';
    connStatus.className = 'connection-status connected';
    sendBtn.disabled = false;
  };

  ws.onclose = () => {
    connStatus.textContent = 'disconnected';
    connStatus.className = 'connection-status disconnected';
    sendBtn.disabled = true;
    setTimeout(connect, 2000);
  };

  ws.onerror = () => ws.close();

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'history') {
      messagesEl.innerHTML = '';
      data.messages.forEach(renderMessage);
      scrollToBottom();
    } else if (data.type === 'message') {
      renderMessage(data.message);
      scrollToBottom();
    } else if (data.type === 'agent_status') {
      agentStatus = data.status;
      renderAgentList();
    }
  };
}

function renderMessage(msg) {
  const div = document.createElement('div');
  const classes = ['message'];
  if (msg.type === 'system') classes.push('system');
  else if (msg.target !== 'all') classes.push('direct');
  div.className = classes.join(' ');

  if (msg.type === 'system') {
    div.textContent = msg.content;
  } else {
    const ts = msg.timestamp ? msg.timestamp.slice(11, 19) : '';
    const targetBadge = msg.target !== 'all'
      ? `<span class="message-target">@${msg.target}</span>`
      : '';

    div.innerHTML = `
      <div class="message-header">
        <span class="message-sender" style="color: ${getColor(msg.sender)}">${msg.sender}</span>
        ${targetBadge}
        <span class="message-time">${ts}</span>
      </div>
      <div class="message-content">${escapeHtml(msg.content)}</div>
    `;
  }

  messagesEl.appendChild(div);
}

function renderAgentList() {
  // Build agent list with gurvinder at top
  const allNames = ['gurvinder', 'supervisor', 'phase-1', 'phase-2', 'phase-3',
                     'phase-4', 'phase-5', 'phase-6', 'git-agent'];
  agentList.innerHTML = '';

  allNames.forEach(name => {
    const isOnline = name === 'gurvinder' ? true : !!agentStatus[name];
    const div = document.createElement('div');
    div.className = 'agent-item';
    div.innerHTML = `
      <span class="agent-dot ${isOnline ? 'online' : 'offline'}"></span>
      <span class="agent-name" style="color: ${getColor(name)}">${name}</span>
    `;
    div.onclick = () => {
      targetSelect.value = name === 'gurvinder' ? 'all' : name;
      msgInput.focus();
    };
    agentList.appendChild(div);
  });

  // Populate target dropdown
  const current = targetSelect.value;
  targetSelect.innerHTML = '<option value="all">@all</option>';
  allNames.filter(n => n !== 'gurvinder').forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = `@${name}`;
    targetSelect.appendChild(opt);
  });
  targetSelect.value = current || 'all';
}

function sendMessage() {
  const content = msgInput.value.trim();
  if (!content || !ws || ws.readyState !== WebSocket.OPEN) return;

  ws.send(JSON.stringify({
    sender: 'gurvinder',
    target: targetSelect.value,
    content: content,
    type: 'message',
  }));

  // Render locally immediately (server won't echo back to sender)
  renderMessage({
    sender: 'gurvinder',
    target: targetSelect.value,
    content: content,
    type: 'message',
    timestamp: new Date().toISOString(),
  });
  scrollToBottom();

  msgInput.value = '';
  msgInput.style.height = 'auto';
  targetSelect.value = 'all';
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Auto-resize textarea
msgInput.addEventListener('input', () => {
  msgInput.style.height = 'auto';
  msgInput.style.height = Math.min(msgInput.scrollHeight, 120) + 'px';
});

// Send on Enter (Shift+Enter for newline)
msgInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener('click', sendMessage);

// Init
connect();
renderAgentList();
</script>
</body>
</html>
```

- [ ] **Step 2: Test the web UI**

```bash
cd ~/coders-war-room
python3 server.py &
SERVER_PID=$!
sleep 1
open http://localhost:5680
```

Expected: Browser opens showing the War Room chat interface with:
- Agent sidebar on the left (all agents shown as offline/grey dots)
- Chat area in the center
- Input area at the bottom with @target dropdown and Send button
- "connected" status in green at top-right

Verify: Type "Hello from the web" and press Enter. The message should appear in the chat area immediately. Check the API:

```bash
curl -s http://localhost:5680/api/messages | python3 -m json.tool
# Should show the message with sender "gurvinder"
kill $SERVER_PID
```

- [ ] **Step 3: Commit**

```bash
cd ~/coders-war-room
git add static/index.html
git commit -m "feat: add web chat UI with WebSocket, agent status, and @-mentions"
```

---

### Task 5: Onboard Script

**Files:**
- Create: `~/coders-war-room/onboard.sh`

- [ ] **Step 1: Write onboard.sh**

Create `~/coders-war-room/onboard.sh`:

```bash
#!/bin/bash
# Coder's War Room — Agent Onboarding
# Creates tmux sessions, starts Claude Code, injects agent identity.
#
# Usage:
#   ./onboard.sh                  # Onboard all agents from config.yaml
#   ./onboard.sh phase-1 phase-2  # Onboard specific agents only

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"
WARROOM_SH="$SCRIPT_DIR/warroom.sh"
SERVER_URL="http://localhost:5680"

# Parse config with Python (reliable YAML parsing)
get_config() {
    python3 -c "
import yaml, json, sys
with open('$CONFIG_FILE') as f:
    config = yaml.safe_load(f)
print(json.dumps(config))
"
}

CONFIG_JSON=$(get_config)
PROJECT_PATH=$(echo "$CONFIG_JSON" | python3 -c "import sys,json,os; print(os.path.expanduser(json.load(sys.stdin)['project_path']))")

# Get list of agents to onboard
get_agents() {
    local filter="$1"
    echo "$CONFIG_JSON" | python3 -c "
import sys, json
config = json.load(sys.stdin)
agents = config.get('agents', [])
filter_names = '$filter'.split() if '$filter' else []
for a in agents:
    if not filter_names or a['name'] in filter_names:
        print(f\"{a['name']}|{a['tmux_session']}|{a['role']}\")
"
}

wait_for_prompt() {
    local session="$1"
    local max_wait=30
    local waited=0

    echo "  Waiting for Claude Code to start..."
    while [ $waited -lt $max_wait ]; do
        sleep 2
        waited=$((waited + 2))

        # Check if the pane has content indicating Claude Code is running
        local content
        content=$(tmux capture-pane -t "$session" -p -l 10 2>/dev/null || true)

        # Claude Code shows ">" or similar prompt when ready
        if echo "$content" | grep -qE '(>|Claude|\/help)'; then
            echo "  Claude Code is ready (${waited}s)"
            return 0
        fi
    done

    echo "  WARNING: Timed out waiting for Claude Code (${max_wait}s). Sending onboarding anyway."
    return 0
}

onboard_agent() {
    local name="$1"
    local session="$2"
    local role="$3"

    echo ""
    echo "=== Onboarding: $name ==="

    # Kill existing session if present
    if tmux has-session -t "$session" 2>/dev/null; then
        echo "  Killing existing session: $session"
        tmux kill-session -t "$session"
        sleep 1
    fi

    # Create new session
    echo "  Creating tmux session: $session"
    tmux new-session -d -s "$session" -x 200 -y 50

    # Set scrollback buffer (extra for supervisor)
    if [ "$name" = "supervisor" ]; then
        tmux set-option -t "$session" history-limit 50000
        echo "  Scrollback: 50000 (supervisor)"
    else
        tmux set-option -t "$session" history-limit 10000
    fi

    # Set environment variable for agent identity
    tmux send-keys -t "$session" "export WARROOM_AGENT_NAME=$name" Enter
    sleep 0.5

    # Start Claude Code
    echo "  Starting Claude Code..."
    tmux send-keys -t "$session" "cd $PROJECT_PATH && claude --dangerously-skip-permissions" Enter

    # Wait for Claude Code to become ready
    wait_for_prompt "$session"

    # Build onboarding prompt
    local onboarding
    read -r -d '' onboarding << ONBOARD_EOF || true
You are $name in the Coder's War Room — a real-time communication system for parallel Claude Code agents working on the same project.

YOUR IDENTITY: $name
YOUR ROLE: $role
PROJECT: $PROJECT_PATH

WAR ROOM PROTOCOL:
- Messages prefixed with [WARROOM @$name] are directed at you. You MUST respond and act on them.
- Messages prefixed with [WARROOM] (no specific tag) are broadcasts. Read them for context. Only respond if it directly impacts your current work. If not relevant, just say "Noted" and continue your work. Do NOT post acknowledgements to the war room.
- Messages prefixed with [WARROOM SYSTEM] are informational. Do not respond.
- To send a message to the war room, run: $WARROOM_SH post "your message"
- To send a direct message: $WARROOM_SH post --to <agent-name> "your message"
- To check recent messages: $WARROOM_SH history
- Keep war room messages concise. This is a chat, not a document.
- When you complete a task or hit a blocker, post it to the war room immediately.

Acknowledge with your name and role, then wait for instructions.
ONBOARD_EOF

    # Inject onboarding via tmux buffer (handles special chars safely)
    tmux set-buffer -b warroom-onboard "$onboarding"
    tmux paste-buffer -b warroom-onboard -t "$session"
    sleep 0.5
    tmux send-keys -t "$session" Enter

    echo "  Onboarded: $name"

    # Announce to war room
    curl -s -X POST "$SERVER_URL/api/messages" \
        -H "Content-Type: application/json" \
        -d "{\"sender\": \"system\", \"content\": \"$name has joined the war room\", \"type\": \"system\"}" \
        > /dev/null 2>&1 || true
}

# Main
echo "==========================================="
echo "  CODER'S WAR ROOM — Agent Onboarding"
echo "==========================================="
echo "Project: $PROJECT_PATH"
echo ""

# Check prerequisites
if ! command -v tmux &> /dev/null; then
    echo "ERROR: tmux is not installed. Run: brew install tmux"
    exit 1
fi

if ! curl -s "$SERVER_URL/api/agents" > /dev/null 2>&1; then
    echo "ERROR: War Room server not running at $SERVER_URL"
    echo "Start it first: python3 $SCRIPT_DIR/server.py &"
    exit 1
fi

FILTER="${*}"
while IFS='|' read -r name session role; do
    onboard_agent "$name" "$session" "$role"
done < <(get_agents "$FILTER")

echo ""
echo "==========================================="
echo "  All agents onboarded!"
echo "  Web UI: $SERVER_URL"
echo "  tmux sessions: tmux ls | grep warroom"
echo "==========================================="
```

- [ ] **Step 2: Make executable**

```bash
chmod +x ~/coders-war-room/onboard.sh
```

- [ ] **Step 3: Test with a single agent (dry run)**

```bash
cd ~/coders-war-room
python3 server.py &
SERVER_PID=$!
sleep 1

# Onboard just one agent for testing
./onboard.sh supervisor

# Verify the tmux session exists
tmux has-session -t warroom-supervisor && echo "Session exists" || echo "Session missing"

# Check the session content
tmux capture-pane -t warroom-supervisor -p -l 20

# Clean up
tmux kill-session -t warroom-supervisor 2>/dev/null || true
kill $SERVER_PID
```

Expected: Session created, Claude Code started, onboarding prompt injected. The capture-pane output should show Claude Code's interface with the onboarding prompt submitted.

- [ ] **Step 4: Commit**

```bash
cd ~/coders-war-room
git add onboard.sh
git commit -m "feat: add onboard.sh for creating agent tmux sessions with Claude Code"
```

---

### Task 6: Integration Smoke Test

**Files:**
- Create: `~/coders-war-room/tests/test_integration.py`

- [ ] **Step 1: Write integration test**

Create `~/coders-war-room/tests/test_integration.py`:

```python
"""
Integration smoke test for the War Room.
Tests the full flow: server + CLI + tmux dispatch.

Run with: python3 -m pytest tests/test_integration.py -v -s
Note: Requires tmux to be installed. Creates temporary tmux sessions.
"""
import json
import subprocess
import time
from pathlib import Path

import pytest
import httpx

SERVER_URL = "http://localhost:5680"
PROJECT_DIR = Path(__file__).parent.parent
TEST_SESSION = "warroom-test-agent"


@pytest.fixture(scope="module", autouse=True)
def server():
    """Start the war room server for the test suite."""
    proc = subprocess.Popen(
        ["python3", str(PROJECT_DIR / "server.py")],
        cwd=str(PROJECT_DIR),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(2)  # Wait for server to start
    yield proc
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(autouse=True)
def tmux_session():
    """Create and clean up a test tmux session."""
    # Kill if exists
    subprocess.run(["tmux", "kill-session", "-t", TEST_SESSION],
                    capture_output=True)
    # Create session
    subprocess.run(["tmux", "new-session", "-d", "-s", TEST_SESSION, "-x", "200", "-y", "50"],
                    check=True)
    # Start a simple shell prompt so we can verify send-keys
    time.sleep(0.5)
    yield
    subprocess.run(["tmux", "kill-session", "-t", TEST_SESSION],
                    capture_output=True)


def test_post_and_retrieve_message():
    """Post a message via API and retrieve it."""
    resp = httpx.post(f"{SERVER_URL}/api/messages", json={
        "sender": "phase-1",
        "target": "all",
        "content": "Integration test message",
    })
    assert resp.status_code == 200
    msg = resp.json()
    assert msg["content"] == "Integration test message"

    # Retrieve
    resp = httpx.get(f"{SERVER_URL}/api/messages?limit=5")
    assert resp.status_code == 200
    messages = resp.json()
    contents = [m["content"] for m in messages]
    assert "Integration test message" in contents


def test_cli_post():
    """Post a message via warroom.sh CLI."""
    result = subprocess.run(
        [str(PROJECT_DIR / "warroom.sh"), "post", "CLI test message"],
        capture_output=True,
        text=True,
        env={**dict(__import__('os').environ), "WARROOM_AGENT_NAME": "phase-2"},
    )
    assert "OK" in result.stdout

    # Verify it's in the API
    resp = httpx.get(f"{SERVER_URL}/api/messages?limit=5")
    messages = resp.json()
    found = [m for m in messages if m["content"] == "CLI test message"]
    assert len(found) == 1
    assert found[0]["sender"] == "phase-2"


def test_cli_history():
    """Retrieve message history via CLI."""
    # Post a known message first
    httpx.post(f"{SERVER_URL}/api/messages", json={
        "sender": "supervisor",
        "content": "History test marker",
    })

    result = subprocess.run(
        [str(PROJECT_DIR / "warroom.sh"), "history", "--count", "10"],
        capture_output=True,
        text=True,
        env={**dict(__import__('os').environ), "WARROOM_AGENT_NAME": "test"},
    )
    assert "History test marker" in result.stdout
    assert "supervisor" in result.stdout


def test_agent_list():
    """Verify agent roster is returned correctly."""
    resp = httpx.get(f"{SERVER_URL}/api/agents")
    assert resp.status_code == 200
    agents = resp.json()
    names = [a["name"] for a in agents]
    assert "supervisor" in names
    assert "phase-1" in names
    assert "git-agent" in names
    assert len(agents) == 8


def test_message_truncation_endpoint():
    """Verify the /message/<id> endpoint returns full content."""
    long_content = "A" * 1000
    resp = httpx.post(f"{SERVER_URL}/api/messages", json={
        "sender": "phase-3",
        "content": long_content,
    })
    msg_id = resp.json()["id"]

    resp = httpx.get(f"{SERVER_URL}/message/{msg_id}")
    assert resp.status_code == 200
    assert len(resp.text) == 1000


def test_direct_message():
    """Verify direct messages are stored with correct target."""
    resp = httpx.post(f"{SERVER_URL}/api/messages", json={
        "sender": "supervisor",
        "target": "phase-1",
        "content": "Direct message test",
    })
    assert resp.status_code == 200
    msg = resp.json()
    assert msg["target"] == "phase-1"
```

- [ ] **Step 2: Run integration tests**

```bash
cd ~/coders-war-room
python3 -m pytest tests/test_integration.py -v -s
```

Expected: All 6 tests PASS. The server starts, messages flow through the API and CLI, agent roster is correct.

- [ ] **Step 3: Full manual smoke test**

Start everything and test the full flow:

```bash
cd ~/coders-war-room

# 1. Start server
python3 server.py &
sleep 1

# 2. Open web UI
open http://localhost:5680

# 3. Create a test tmux session to simulate an agent
tmux new-session -d -s warroom-phase-1

# 4. Post a message from CLI (simulating an agent)
WARROOM_AGENT_NAME=supervisor ./warroom.sh post "All agents report status"

# 5. Check if the message appears in the web UI (visually)
# 6. Check if the message was dispatched to the tmux session
sleep 3
tmux capture-pane -t warroom-phase-1 -p -l 5
# Should show: [WARROOM] supervisor: All agents report status

# 7. Send a message from the web UI, verify it appears in history
./warroom.sh history

# Cleanup
tmux kill-session -t warroom-phase-1
pkill -f "python3 server.py"
```

- [ ] **Step 4: Commit**

```bash
cd ~/coders-war-room
git add tests/test_integration.py
git commit -m "test: add integration smoke tests for full message flow"
```

---

### Task 7: Startup & Shutdown Scripts

**Files:**
- Create: `~/coders-war-room/start.sh`
- Create: `~/coders-war-room/stop.sh`

- [ ] **Step 1: Write start.sh**

Create `~/coders-war-room/start.sh`:

```bash
#!/bin/bash
# Coder's War Room — Start Everything
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT=5680

echo "==========================================="
echo "  CODER'S WAR ROOM — Starting Up"
echo "==========================================="

# Check if server is already running
if curl -s "http://localhost:$PORT/api/agents" > /dev/null 2>&1; then
    echo "Server already running on port $PORT"
else
    echo "Starting server on port $PORT..."
    cd "$SCRIPT_DIR"
    nohup python3 server.py > /tmp/warroom-server.log 2>&1 &
    echo $! > /tmp/warroom-server.pid
    sleep 2

    if curl -s "http://localhost:$PORT/api/agents" > /dev/null 2>&1; then
        echo "Server started (PID: $(cat /tmp/warroom-server.pid))"
    else
        echo "ERROR: Server failed to start. Check /tmp/warroom-server.log"
        exit 1
    fi
fi

# Onboard agents (pass through any arguments for selective onboarding)
echo ""
"$SCRIPT_DIR/onboard.sh" "$@"

# Open web UI
echo ""
echo "Opening web UI..."
open "http://localhost:$PORT"
```

- [ ] **Step 2: Write stop.sh**

Create `~/coders-war-room/stop.sh`:

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

# Kill server
if [ -f /tmp/warroom-server.pid ]; then
    PID=$(cat /tmp/warroom-server.pid)
    if kill -0 "$PID" 2>/dev/null; then
        echo "Stopping server (PID: $PID)..."
        kill "$PID"
        rm -f /tmp/warroom-server.pid
    fi
else
    # Fallback: find by process name
    pkill -f "python3.*server.py" 2>/dev/null && echo "Server stopped" || echo "Server was not running"
fi

echo ""
echo "War Room shut down."
```

- [ ] **Step 3: Make executable**

```bash
chmod +x ~/coders-war-room/start.sh ~/coders-war-room/stop.sh
```

- [ ] **Step 4: Commit**

```bash
cd ~/coders-war-room
git add start.sh stop.sh
git commit -m "feat: add start.sh and stop.sh for one-command startup/shutdown"
```

---

### Task 8: Gitignore & Final Verification

**Files:**
- Create: `~/coders-war-room/.gitignore`

- [ ] **Step 1: Create .gitignore**

Create `~/coders-war-room/.gitignore`:

```
warroom.db
warroom.db-wal
warroom.db-shm
__pycache__/
*.pyc
.pytest_cache/
/tmp/
*.log
.DS_Store
```

- [ ] **Step 2: Final full-stack verification**

Run the complete test suite:

```bash
cd ~/coders-war-room

# Unit/API tests
python3 -m pytest tests/test_api.py -v

# Integration tests (starts its own server)
python3 -m pytest tests/test_integration.py -v -s
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
cd ~/coders-war-room
git add .gitignore
git commit -m "chore: add .gitignore for database and cache files"
```

- [ ] **Step 4: Verify directory structure**

```bash
ls -la ~/coders-war-room/
# Should show:
# .git/
# .gitignore
# config.yaml
# docs/
# onboard.sh
# requirements.txt
# server.py
# start.sh
# static/
# stop.sh
# tests/
# warroom.sh
```
