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
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
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
# Each agent's working directory (for Warp file browser)
PROJECT_PATH = str(Path(CONFIG.get("project_path", "~")).expanduser())
AGENT_DIRS: dict[str, str] = {a["name"]: PROJECT_PATH for a in AGENTS}

MAX_TMUX_MSG_LEN = 500

SYSTEM_DIRS = {"Library", "Applications", "Public", "Movies", "Music", "Pictures"}
HOME_DIR = str(Path.home())

# Braille spinner characters Claude Code uses when working
SPINNER_CHARS = set("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
connected_clients: list[WebSocket] = []
agent_queues: dict[str, list[dict]] = {}
# Tracks which agents are "in" the war room (True = in, False = de-boarded)
agent_membership: dict[str, bool] = {a["name"]: True for a in AGENTS}


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
# tmux helpers
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


def capture_tmux_lines(session_name: str, n: int = 10) -> Optional[str]:
    """Capture the last n lines from a tmux pane. Returns None if session doesn't exist."""
    try:
        result = subprocess.run(
            ["tmux", "capture-pane", "-t", session_name, "-p", "-S", f"-{n}"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def _has_busy_indicators(lines: list[str]) -> tuple[bool, Optional[str]]:
    """Check last few lines for Claude Code busy indicators.
    Returns (is_busy, activity_description_or_None).
    """
    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # Check for spinner char at start of line → busy with activity
        if stripped[0] in SPINNER_CHARS:
            activity = stripped[1:].strip().rstrip(".")
            if activity:
                return True, activity
            return True, "Working..."
        # Check for "Thinking" anywhere in recent lines
        if "Thinking" in stripped:
            return True, "Thinking..."
    return False, None


# ---------------------------------------------------------------------------
# Agent presence & readiness
# ---------------------------------------------------------------------------
def check_agent_ready(session_name: str) -> bool:
    """Check if Claude Code is idle (can receive messages).

    FLIPPED LOGIC: Instead of looking for a specific prompt character (which varies),
    we check if busy indicators are ABSENT. If no spinners and no "Thinking" text
    in the last 5 lines, the agent is ready.
    """
    content = capture_tmux_lines(session_name, 10)
    if content is None:
        return False
    last_lines = content.strip().split("\n")[-5:]
    is_busy, _ = _has_busy_indicators(last_lines)
    return not is_busy


def get_agent_activity(session_name: str) -> dict:
    """Returns rich presence info: {"presence": str, "activity": str|None}.

    Presence values:
      - "active"  — Claude Code idle, waiting for input
      - "busy"    — Claude Code running a tool or processing
      - "typing"  — Claude Code thinking/composing
      - "session" — tmux session exists but no Claude Code detected
      - "offline" — no tmux session
    """
    if not tmux_session_exists(session_name):
        return {"presence": "offline", "activity": None}

    content = capture_tmux_lines(session_name, 15)
    if content is None:
        return {"presence": "session", "activity": None}

    # Check if Claude Code is running at all
    has_claude = "Claude Code" in content or any(
        c in content for c in ["\u276f", "\u23f5", "\u2770", ">"]  # ❯ ⏵ ❰ >
    )
    if not has_claude:
        return {"presence": "session", "activity": None}

    # Check for busy indicators
    last_lines = content.strip().split("\n")[-5:]
    is_busy, activity = _has_busy_indicators(last_lines)

    if is_busy:
        if activity and "Thinking" in activity:
            return {"presence": "typing", "activity": activity}
        return {"presence": "busy", "activity": activity}

    return {"presence": "active", "activity": None}


# ---------------------------------------------------------------------------
# tmux dispatch
# ---------------------------------------------------------------------------
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
    """Inject text into a tmux session. Uses set-buffer + paste-buffer for reliable delivery."""
    try:
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
        subprocess.run(
            ["tmux", "send-keys", "-t", session_name, "Enter"],
            capture_output=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


async def dispatch_to_agents(msg: dict):
    """Dispatch a message to all agents that are in the war room, except the sender."""
    for agent in AGENTS:
        name = agent["name"]
        session = agent["tmux_session"]

        if name == msg["sender"]:
            continue

        if not agent_membership.get(name, False):
            continue

        if not tmux_session_exists(session):
            continue

        if check_agent_ready(session):
            if name in agent_queues and agent_queues[name]:
                queued = agent_queues.pop(name)
                queued.append(msg)
                text = format_batch_for_tmux(queued)
            else:
                text = format_message_for_tmux(msg)
            send_to_tmux(session, text)
        else:
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
            if not agent_membership.get(name, False):
                agent_queues.pop(name, None)
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
    """Background: push rich agent presence to web clients every 2s."""
    while True:
        await asyncio.sleep(2)
        agents_data = {}
        for a in AGENTS:
            activity = get_agent_activity(a["tmux_session"])
            activity["in_room"] = agent_membership.get(a["name"], False)
            agents_data[a["name"]] = activity
        data = json.dumps({"type": "agent_status", "agents": agents_data})
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
            "presence": get_agent_activity(a["tmux_session"])["presence"],
            "activity": get_agent_activity(a["tmux_session"])["activity"],
            "in_room": agent_membership.get(a["name"], False),
        }
        for a in AGENTS
    ]


@app.get("/api/browse")
async def browse_directory(path: str = "~"):
    """List directories in the given path for the directory picker."""
    expanded = str(Path(path).expanduser().resolve())
    if not expanded.startswith(HOME_DIR):
        return JSONResponse({"error": "Path must be under home directory"}, status_code=403)
    if not Path(expanded).is_dir():
        return JSONResponse({"error": f"Directory not found: {path}"}, status_code=404)
    parent = str(Path(expanded).parent)
    if not parent.startswith(HOME_DIR):
        parent = HOME_DIR
    directories = []
    try:
        for entry in sorted(Path(expanded).iterdir()):
            if not entry.is_dir():
                continue
            name = entry.name
            if name.startswith(".") and name != ".claude":
                continue
            if expanded == HOME_DIR and name in SYSTEM_DIRS:
                continue
            directories.append({"name": name, "path": str(entry)})
    except PermissionError:
        return JSONResponse({"error": "Permission denied"}, status_code=403)
    return {"current": expanded, "parent": parent, "directories": directories}


@app.post("/api/agents/{agent_name}/deboard")
async def agent_deboard(agent_name: str):
    """De-board: stop message delivery, keep session alive."""
    if agent_name not in AGENT_NAMES:
        return JSONResponse({"error": f"Unknown agent: {agent_name}"}, status_code=404)
    agent_membership[agent_name] = False
    agent_queues.pop(agent_name, None)
    saved = await save_message(
        "system", "all",
        f"{agent_name} has been de-boarded from the war room (session still active)",
        "system",
    )
    await broadcast_ws({"type": "message", "message": saved})
    await broadcast_ws({"type": "membership", "agent": agent_name, "in_room": False})
    return {"status": "deboarded", "agent": agent_name}


@app.post("/api/agents/{agent_name}/reboard")
async def agent_reboard(agent_name: str):
    """Re-board: resume message delivery."""
    if agent_name not in AGENT_NAMES:
        return JSONResponse({"error": f"Unknown agent: {agent_name}"}, status_code=404)
    was_in = agent_membership.get(agent_name, False)
    agent_membership[agent_name] = True
    if not was_in:
        saved = await save_message("system", "all", f"{agent_name} has re-joined the war room", "system")
        await broadcast_ws({"type": "message", "message": saved})
    await broadcast_ws({"type": "membership", "agent": agent_name, "in_room": True})
    return {"status": "reboarded", "agent": agent_name}


@app.post("/api/agents/{agent_name}/attach")
async def agent_attach(agent_name: str):
    """Pop out an agent's Claude Code session into a new terminal window."""
    if agent_name not in AGENT_NAMES:
        return JSONResponse({"error": f"Unknown agent: {agent_name}"}, status_code=404)
    session = AGENT_SESSIONS.get(agent_name)
    if not tmux_session_exists(session):
        return JSONResponse({"error": f"No tmux session for {agent_name}"}, status_code=404)

    # Get the agent's working directory for Warp's file browser
    agent_dir = AGENT_DIRS.get(agent_name, CONFIG.get("project_path", "~"))
    agent_dir = str(Path(agent_dir).expanduser())

    try:
        # Set tmux window title so Warp tab shows agent name
        subprocess.run(
            ["tmux", "rename-window", "-t", session, agent_name],
            capture_output=True, timeout=2,
        )

        # Create launcher script IN the project directory so Warp's
        # file browser opens there (Warp uses the script's location as CWD)
        launcher = Path(agent_dir) / f".warroom-attach.sh"
        launcher.write_text(
            f"#!/bin/bash\n"
            f"# War Room — {agent_name}\n"
            f"cd {agent_dir}\n"
            f"printf '\\033]0;{agent_name} — War Room\\007'\n"
            f"exec tmux attach -t {session}\n"
        )
        launcher.chmod(0o755)

        warp = Path("/Applications/Warp.app")
        if warp.exists():
            subprocess.run(["open", "-a", "Warp", str(launcher)], capture_output=True, timeout=5)
        else:
            subprocess.run(
                ["osascript", "-e",
                 f'tell application "Terminal"\n  activate\n  do script "cd {agent_dir} && tmux attach -t {session}"\nend tell'],
                capture_output=True, timeout=5,
            )
        return {"status": "attached", "agent": agent_name, "session": session}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# Keep old endpoints as aliases for backwards compat
@app.post("/api/agents/{agent_name}/leave")
async def agent_leave(agent_name: str):
    return await agent_deboard(agent_name)


@app.post("/api/agents/{agent_name}/join")
async def agent_join(agent_name: str):
    return await agent_reboard(agent_name)


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    connected_clients.append(ws)
    try:
        messages = await get_messages(200)
        await ws.send_text(json.dumps({"type": "history", "messages": messages}))

        # Send initial agent status with activity
        agents_data = {}
        for a in AGENTS:
            activity = get_agent_activity(a["tmux_session"])
            activity["in_room"] = agent_membership.get(a["name"], False)
            agents_data[a["name"]] = activity
        await ws.send_text(json.dumps({"type": "agent_status", "agents": agents_data}))

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
