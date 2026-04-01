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
            ["tmux", "capture-pane", "-t", session_name, "-p", "-S", "-5"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.returncode != 0:
            return False
        lines = result.stdout.strip().split("\n")
        for line in reversed(lines[-3:]):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.endswith(">") or stripped == ">":
                return True
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
    """Dispatch a message to all agents except the sender."""
    for agent in AGENTS:
        name = agent["name"]
        session = agent["tmux_session"]

        if name == msg["sender"]:
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
        messages = await get_messages(200)
        await ws.send_text(json.dumps({"type": "history", "messages": messages}))

        status = {a["name"]: tmux_session_exists(a["tmux_session"]) for a in AGENTS}
        await ws.send_text(json.dumps({"type": "agent_status", "status": status}))

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
