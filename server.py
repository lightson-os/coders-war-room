import asyncio
import fnmatch
import glob as globmod
import json
import re
import subprocess
import time
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
COLORS = {
    'gurvinder': '#ff9100', 'supervisor': '#b388ff',
    'phase-1': '#448aff', 'phase-2': '#00e676', 'phase-3': '#ff80ab',
    'phase-4': '#18ffff', 'phase-5': '#ea80fc', 'phase-6': '#69f0ae',
    'git-agent': '#ffd740',
}
# Palette for dynamically created agents (cycles through these)
COLOR_PALETTE = ['#ff6e40', '#64ffda', '#ffd180', '#b9f6ca', '#84ffff', '#f48fb1', '#ce93d8', '#a5d6a7', '#80cbc4', '#ffcc80']


def get_agent_color(name: str) -> str:
    """Get color for an agent — static map for known agents, palette for dynamic ones."""
    if name in COLORS:
        return COLORS[name]
    # Assign a deterministic color from palette based on name hash
    idx = hash(name) % len(COLOR_PALETTE)
    color = COLOR_PALETTE[idx]
    COLORS[name] = color  # Cache it
    return color
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

# Status store (manual status per agent, 30min TTL)
agent_manual_status: dict[str, dict] = {}
agent_last_state: dict[str, dict] = {}
agent_owns_resolved: dict[str, list[str]] = {}
agent_last_commit: dict[str, dict] = {}

# Dedup: last message ID dispatched to each agent
agent_last_seen_id: dict[str, int] = {}

STATUS_TTL_SECONDS = 1800  # 30 minutes
STALE_THRESHOLD_SECONDS = 300  # 5 minutes
STALE_EXEMPT_TOOLS = {"Read", "Bash", "WebFetch", "WebSearch", "Agent"}


# ---------------------------------------------------------------------------
# Ownership, staleness, manual status helpers
# ---------------------------------------------------------------------------
def resolve_ownership():
    """Resolve glob patterns from config.yaml owns field into filenames."""
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


dir_has_owned: dict[str, bool] = {}


def precompute_dir_ownership():
    """Pre-compute which directories contain owned files."""
    dir_has_owned.clear()
    for agent in AGENTS:
        for pattern in agent.get("owns", []):
            full = str(Path(PROJECT_PATH) / pattern)
            matches = globmod.glob(full, recursive=True)
            for match in matches:
                if not Path(match).is_file():
                    continue
                rel = str(Path(match).relative_to(PROJECT_PATH))
                parts = Path(rel).parts
                for i in range(len(parts) - 1):
                    dir_path = str(Path(*parts[:i + 1]))
                    dir_has_owned[dir_path] = True


def get_file_owner(relative_path: str) -> tuple:
    """Return (agent_name, color) for a file, or (None, None)."""
    for agent in AGENTS:
        for pattern in agent.get("owns", []):
            if fnmatch.fnmatch(relative_path, pattern):
                return agent["name"], get_agent_color(agent["name"])
    return None, None


def update_staleness(agent_name: str, tool: str, file: str) -> bool:
    """Track how long an agent has been on the same tool+file. Returns True if stalled."""
    now = time.time()
    prev = agent_last_state.get(agent_name)
    if prev and prev.get("tool") == tool and prev.get("file") == file:
        return (now - prev["since"]) >= STALE_THRESHOLD_SECONDS and tool not in STALE_EXEMPT_TOOLS
    else:
        agent_last_state[agent_name] = {"tool": tool, "file": file, "since": now}
        return False


def get_stalled_minutes(agent_name: str) -> int:
    prev = agent_last_state.get(agent_name)
    if not prev:
        return 0
    return int((time.time() - prev["since"]) / 60)


def get_manual_status(agent_name: str) -> dict:
    """Get manual status respecting TTL. Blockers never auto-expire."""
    status = agent_manual_status.get(agent_name)
    if not status:
        return {}
    elapsed = time.time() - status.get("updated_at", 0)
    if elapsed > STATUS_TTL_SECONDS:
        result = {}
        if status.get("blocked_by"):
            result["blocked_by"] = status["blocked_by"]
            result["blocked_reason"] = status.get("blocked_reason")
        if not result:
            agent_manual_status.pop(agent_name, None)
        return result
    return {k: v for k, v in status.items() if k != "updated_at"}


def reset_manual_ttl(agent_name: str):
    """Reset TTL timer on any agent activity."""
    if agent_name in agent_manual_status:
        agent_manual_status[agent_name]["updated_at"] = time.time()


def refresh_last_commits():
    """Get latest commit touching each agent's owned files."""
    for agent in AGENTS:
        name = agent["name"]
        patterns = agent.get("owns", [])
        if not patterns:
            continue
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


async def init_dedup_ids():
    """On boot, set all agents' last-seen to the latest message ID (prevents replay)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT MAX(id) FROM messages")
        row = await cursor.fetchone()
        latest_id = row[0] or 0
    for a in AGENTS:
        agent_last_seen_id.setdefault(a["name"], latest_id)


async def dispatch_to_agents(msg: dict):
    """Dispatch a message to all agents that are in the war room, except the sender."""
    for agent in AGENTS:
        name = agent["name"]
        session = agent["tmux_session"]

        if name == msg["sender"]:
            continue

        if not agent_membership.get(name, False):
            continue

        # Dedup: skip if agent already saw this message
        msg_id = msg.get("id", 0)
        if msg_id and msg_id <= agent_last_seen_id.get(name, 0):
            continue

        if not tmux_session_exists(session):
            continue

        if check_agent_ready(session):
            # Flush any queued messages first, ONE AT A TIME
            if name in agent_queues and agent_queues[name]:
                queued = agent_queues.pop(name)
                for queued_msg in queued:
                    send_to_tmux(session, format_message_for_tmux(queued_msg))
                    agent_last_seen_id[name] = queued_msg.get("id", 0)
                    await asyncio.sleep(0.3)
            # Then deliver the current message
            send_to_tmux(session, format_message_for_tmux(msg))
            agent_last_seen_id[name] = msg.get("id", 0)
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
            # Dedup: filter already-seen messages
            messages = [m for m in messages if m.get("id", 0) > agent_last_seen_id.get(name, 0)]
            if not messages:
                continue
            for queued_msg in messages:
                send_to_tmux(session, format_message_for_tmux(queued_msg))
                agent_last_seen_id[name] = queued_msg.get("id", 0)
                await asyncio.sleep(0.3)


async def agent_status_loop():
    """Background: push rich agent status (config + auto + manual) every 2s."""
    commit_counter = 0
    while True:
        await asyncio.sleep(2)
        commit_counter += 1
        if commit_counter >= 15:  # Refresh git commits every 30s
            commit_counter = 0
            refresh_last_commits()

        agents_data = {}
        for a in AGENTS:
            name = a["name"]
            session = a["tmux_session"]
            activity = get_agent_activity(session)

            # Parse tool and file from activity string
            tool, file = None, None
            act_str = activity.get("activity") or ""
            if " \u2192 " in act_str:  # " → "
                parts = act_str.split(" \u2192 ", 1)
                tool = parts[0].strip()
                file = parts[1].split(":")[0].strip() if len(parts) > 1 else None

            # Staleness detection
            stalled = False
            stalled_minutes = 0
            if tool and file and activity["presence"] == "busy":
                stalled = update_staleness(name, tool, file)
                stalled_minutes = get_stalled_minutes(name)
                reset_manual_ttl(name)
            elif activity["presence"] == "busy":
                agent_last_state.pop(name, None)
                reset_manual_ttl(name)

            manual = get_manual_status(name)
            owns = agent_owns_resolved.get(name, [])
            last_commit = agent_last_commit.get(name)

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


def reconcile_tmux_sessions():
    """On boot, discover orphaned warroom-* tmux sessions and adopt them."""
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return

        for line in result.stdout.strip().split("\n"):
            session_name = line.strip()
            if not session_name.startswith("warroom-"):
                continue
            agent_name = session_name[len("warroom-"):]
            if agent_name in AGENT_NAMES:
                continue

            # Get the pane's working directory
            pane_dir = PROJECT_PATH
            try:
                dir_result = subprocess.run(
                    ["tmux", "display-message", "-t", session_name, "-p", "#{pane_current_path}"],
                    capture_output=True, text=True, timeout=2,
                )
                if dir_result.returncode == 0 and dir_result.stdout.strip():
                    pane_dir = dir_result.stdout.strip()
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            agent_entry = {
                "name": agent_name,
                "role": "Dynamic agent (recovered)",
                "tmux_session": session_name,
                "dynamic": True,
            }
            AGENTS.append(agent_entry)
            AGENT_NAMES.add(agent_name)
            AGENT_SESSIONS[agent_name] = session_name
            AGENT_DIRS[agent_name] = pane_dir
            agent_membership[agent_name] = True

    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


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
    await init_dedup_ids()
    reconcile_tmux_sessions()  # Adopt orphaned sessions on boot
    resolve_ownership()
    precompute_dir_ownership()
    refresh_last_commits()
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


class AgentCreate(BaseModel):
    name: str
    directory: str
    role: str
    initial_prompt: str = ""
    model: str = "opus"
    skip_permissions: bool = True


class AgentStatus(BaseModel):
    task: Optional[str] = None
    progress: Optional[int] = None
    eta: Optional[str] = None
    blocked_by: Optional[str] = None
    blocked_reason: Optional[str] = None
    clear: bool = False


NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-]{0,18}[a-z0-9]$")
VALID_MODELS = {"opus", "sonnet", "haiku"}
STARTUP_MD = Path(__file__).parent / "startup.md"


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
            "dynamic": a.get("dynamic", False),
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


@app.get("/api/files")
async def list_files(path: str = "."):
    """List directory contents with ownership info."""
    target = (Path(PROJECT_PATH) / path).resolve()
    project_resolved = Path(PROJECT_PATH).resolve()
    if not str(target).startswith(str(project_resolved)):
        return JSONResponse({"error": "Path must be under project directory"}, status_code=403)
    if not target.is_dir():
        return JSONResponse({"error": f"Not a directory: {path}"}, status_code=404)
    parent_rel = str(target.parent.relative_to(project_resolved)) if target != project_resolved else None
    entries = []
    try:
        items = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        for item in items:
            name = item.name
            if name.startswith(".") and name != ".claude":
                continue
            rel_path = str(item.relative_to(project_resolved))
            if item.is_dir():
                entries.append({"name": name, "type": "dir", "path": rel_path, "has_owned": dir_has_owned.get(rel_path, False)})
            elif item.is_file():
                owner, color = get_file_owner(rel_path)
                entries.append({"name": name, "type": "file", "path": rel_path, "owner": owner, "color": color})
    except PermissionError:
        return JSONResponse({"error": "Permission denied"}, status_code=403)
    return {"current": str(target.relative_to(project_resolved)) if target != project_resolved else ".", "parent": parent_rel, "entries": entries}


@app.post("/api/files/open")
async def open_file(data: dict):
    """Open a file — markdown renders in browser, others open in system default."""
    file_path = data.get("path", "")
    full_path = (Path(PROJECT_PATH) / file_path).resolve()
    project_resolved = Path(PROJECT_PATH).resolve()
    if not str(full_path).startswith(str(project_resolved)):
        return JSONResponse({"error": "Path must be under project directory"}, status_code=403)
    if not full_path.is_file():
        return JSONResponse({"error": "File not found"}, status_code=404)
    try:
        ext = full_path.suffix.lower()
        if ext in (".md", ".markdown"):
            # Markdown: return URL for browser preview
            rel = str(full_path.relative_to(project_resolved))
            return {"status": "preview", "url": f"/preview/{rel}", "path": file_path}
        else:
            subprocess.run(["open", str(full_path)], capture_output=True, timeout=5)
            return {"status": "opened", "path": file_path}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/preview/{file_path:path}")
async def preview_markdown(file_path: str):
    """Render a markdown file as styled HTML."""
    import markdown as md
    full_path = (Path(PROJECT_PATH) / file_path).resolve()
    project_resolved = Path(PROJECT_PATH).resolve()
    if not str(full_path).startswith(str(project_resolved)):
        return PlainTextResponse("Forbidden", status_code=403)
    if not full_path.is_file():
        return PlainTextResponse("Not found", status_code=404)
    raw = full_path.read_text(errors="replace")
    html_content = md.markdown(raw, extensions=["tables", "fenced_code", "codehilite"])
    page = f"""<!DOCTYPE html>
<html><head>
<meta charset="UTF-8">
<title>{full_path.name}</title>
<style>
  body {{ font-family: -apple-system, 'Helvetica Neue', sans-serif; max-width: 820px; margin: 40px auto; padding: 0 20px; background: #0d1117; color: #c9d1d9; line-height: 1.7; }}
  h1,h2,h3 {{ color: #e6edf3; border-bottom: 1px solid #21262d; padding-bottom: 8px; margin-top: 32px; }}
  h1 {{ font-size: 28px; }} h2 {{ font-size: 22px; }} h3 {{ font-size: 18px; }}
  code {{ font-family: 'JetBrains Mono', 'SF Mono', monospace; background: #161b22; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
  pre {{ background: #161b22; padding: 16px; border-radius: 8px; overflow-x: auto; border: 1px solid #21262d; }}
  pre code {{ background: none; padding: 0; }}
  a {{ color: #58a6ff; text-decoration: none; }} a:hover {{ text-decoration: underline; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
  th, td {{ border: 1px solid #21262d; padding: 8px 12px; text-align: left; }}
  th {{ background: #161b22; color: #e6edf3; }}
  blockquote {{ border-left: 3px solid #30363d; padding-left: 16px; color: #8b949e; margin: 16px 0; }}
  strong {{ color: #e6edf3; }}
  .breadcrumb {{ font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #8b949e; margin-bottom: 24px; }}
</style>
</head><body>
<div class="breadcrumb">{file_path}</div>
{html_content}
</body></html>"""
    return HTMLResponse(page)


@app.post("/api/roll-call")
async def roll_call():
    """Broadcast a roll call, wait 10s, report who responded."""
    before_ts = datetime.now(timezone.utc).isoformat()
    saved = await save_message("system", "all", "[ROLL CALL] All agents, report in.", "system")
    await broadcast_ws({"type": "message", "message": saved})
    await dispatch_to_agents(saved)

    in_room = [a["name"] for a in AGENTS if agent_membership.get(a["name"], False)]
    await asyncio.sleep(10)

    responded = set()
    messages = await get_messages(50)
    for m in messages:
        if m["timestamp"] >= before_ts and m["sender"] in in_room and m["type"] == "message":
            responded.add(m["sender"])

    missing = [name for name in in_room if name not in responded]
    responded_list = sorted(responded)
    missing_list = sorted(missing)

    summary = f"[ROLL CALL] {len(responded_list)}/{len(in_room)} responded"
    if responded_list:
        summary += f": {', '.join(responded_list)}"
    if missing_list:
        summary += f". Missing: {', '.join(missing_list)}"

    result_msg = await save_message("system", "all", summary, "system")
    await broadcast_ws({"type": "message", "message": result_msg})

    return {"responded": responded_list, "missing": missing_list, "total": len(in_room)}


@app.post("/api/agents/{agent_name}/status")
async def set_agent_status(agent_name: str, body: AgentStatus):
    """Set manual status for an agent."""
    if agent_name not in AGENT_NAMES:
        return JSONResponse({"error": f"Unknown agent: {agent_name}"}, status_code=404)

    if body.clear:
        agent_manual_status.pop(agent_name, None)
        return {"status": "cleared", "agent": agent_name}

    current = agent_manual_status.get(agent_name, {})

    if body.task is not None:
        current["task"] = body.task
    if body.progress is not None:
        current["progress"] = max(0, min(100, body.progress))
    if body.eta is not None:
        current["eta"] = body.eta
    if body.blocked_by is not None:
        current["blocked_by"] = body.blocked_by
        current["blocked_reason"] = body.blocked_reason
    if body.blocked_reason is not None and body.blocked_by is None:
        current["blocked_reason"] = body.blocked_reason

    current["updated_at"] = time.time()
    agent_manual_status[agent_name] = current

    # Auto-DM the blocking agent if blocked_by is set
    if body.blocked_by and body.blocked_by in AGENT_NAMES:
        reason_text = f" — {body.blocked_reason}" if body.blocked_reason else ""
        dm_content = f"{agent_name} is blocked by you{reason_text}"
        saved = await save_message("system", body.blocked_by, dm_content, "system")
        await broadcast_ws({"type": "message", "message": saved})
        await dispatch_to_agents(saved)

    return {"status": "updated", "agent": agent_name}


@app.get("/api/agents/{agent_name}/status")
async def get_agent_status(agent_name: str):
    """Get full computed status card for an agent."""
    if agent_name not in AGENT_NAMES:
        return JSONResponse({"error": f"Unknown agent: {agent_name}"}, status_code=404)

    # Find agent config
    agent_cfg = next((a for a in AGENTS if a["name"] == agent_name), None)
    session = agent_cfg["tmux_session"] if agent_cfg else None

    # Auto-detected activity
    activity = get_agent_activity(session) if session else {"presence": "offline", "activity": None}

    # Manual status (respects TTL)
    manual = get_manual_status(agent_name)

    # Staleness
    stalled_minutes = get_stalled_minutes(agent_name)

    # Ownership and last commit
    owns = agent_owns_resolved.get(agent_name, [])
    last_commit = agent_last_commit.get(agent_name)

    return {
        "agent": agent_name,
        "presence": "blocked" if manual.get("blocked_by") else activity["presence"],
        "activity": activity.get("activity"),
        "in_room": agent_membership.get(agent_name, False),
        "dynamic": agent_cfg.get("dynamic", False) if agent_cfg else False,
        "task": manual.get("task"),
        "progress": manual.get("progress"),
        "eta": manual.get("eta"),
        "blocked_by": manual.get("blocked_by"),
        "blocked_reason": manual.get("blocked_reason"),
        "stalled_minutes": stalled_minutes,
        "owns": owns,
        "last_commit": last_commit,
    }


@app.get("/api/agents/{agent_name}/owns")
async def get_agent_owns(agent_name: str):
    """Get ownership patterns and resolved filenames for an agent."""
    if agent_name not in AGENT_NAMES:
        return JSONResponse({"error": f"Unknown agent: {agent_name}"}, status_code=404)

    agent_cfg = next((a for a in AGENTS if a["name"] == agent_name), None)
    patterns = agent_cfg.get("owns", []) if agent_cfg else []
    resolved = agent_owns_resolved.get(agent_name, [])

    return {
        "agent": agent_name,
        "patterns": patterns,
        "resolved": resolved,
    }


@app.delete("/api/agents/{agent_name}/remove")
async def agent_remove(agent_name: str):
    """Permanently remove an agent: kill tmux session, remove from roster, free the name."""
    if agent_name not in AGENT_NAMES:
        return JSONResponse({"error": f"Unknown agent: {agent_name}"}, status_code=404)

    session = AGENT_SESSIONS.get(agent_name, f"warroom-{agent_name}")

    # Kill tmux session
    subprocess.run(["tmux", "kill-session", "-t", session], capture_output=True, timeout=5)

    # Remove from all in-memory stores
    AGENT_NAMES.discard(agent_name)
    AGENT_SESSIONS.pop(agent_name, None)
    AGENT_DIRS.pop(agent_name, None)
    agent_membership.pop(agent_name, None)
    agent_manual_status.pop(agent_name, None)
    agent_last_state.pop(agent_name, None)
    agent_last_commit.pop(agent_name, None)
    agent_owns_resolved.pop(agent_name, None)
    agent_queues.pop(agent_name, None)

    # Remove from AGENTS list
    for i, a in enumerate(AGENTS):
        if a["name"] == agent_name:
            AGENTS.pop(i)
            break

    # Announce
    saved = await save_message("system", "all", f"{agent_name} has been permanently removed", "system")
    await broadcast_ws({"type": "message", "message": saved})
    await broadcast_ws({"type": "agent_removed", "agent": agent_name})

    return {"status": "removed", "agent": agent_name}


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


@app.post("/api/agents/create")
async def create_agent(req: AgentCreate):
    # Validate name format
    if not NAME_PATTERN.match(req.name):
        return JSONResponse(
            {"error": "Name must be 2-20 chars, lowercase alphanumeric + hyphens"},
            status_code=400,
        )

    # Validate uniqueness
    if req.name in AGENT_NAMES:
        return JSONResponse(
            {"error": f"Agent '{req.name}' already exists"},
            status_code=400,
        )

    # Validate directory
    dir_path = Path(req.directory)
    if not dir_path.is_dir():
        return JSONResponse(
            {"error": f"Directory not found: {req.directory}"},
            status_code=400,
        )

    # Validate model
    if req.model not in VALID_MODELS:
        return JSONResponse(
            {"error": "Invalid model"},
            status_code=400,
        )

    session = f"warroom-{req.name}"
    agent_dir = str(dir_path.resolve())

    try:
        # Create tmux session
        subprocess.run(
            ["tmux", "new-session", "-d", "-s", session, "-x", "200", "-y", "50", "-c", agent_dir],
            check=True,
            capture_output=True,
            timeout=5,
        )

        # Configure tmux session
        subprocess.run(
            ["tmux", "set-option", "-t", session, "mouse", "on"],
            capture_output=True,
            timeout=2,
        )
        subprocess.run(
            ["tmux", "set-option", "-t", session, "history-limit", "10000"],
            capture_output=True,
            timeout=2,
        )
        subprocess.run(
            ["tmux", "rename-window", "-t", session, req.name],
            capture_output=True,
            timeout=2,
        )

        # Set env var so Claude Code knows its agent name
        subprocess.run(
            ["tmux", "send-keys", "-t", session, f"export WARROOM_AGENT_NAME={req.name}", "Enter"],
            capture_output=True,
            timeout=2,
        )
        await asyncio.sleep(0.5)

        # Start Claude Code
        model_flag = f"--model {req.model}" if req.model != "opus" else ""
        perms_flag = "--dangerously-skip-permissions" if req.skip_permissions else ""
        cmd = f"cd {agent_dir} && claude {model_flag} {perms_flag}".strip()
        cmd = " ".join(cmd.split())
        subprocess.run(
            ["tmux", "send-keys", "-t", session, cmd, "Enter"],
            capture_output=True,
            timeout=2,
        )

        # Wait for Claude Code to be ready (up to 30s)
        warning = None
        ready = False
        for _ in range(15):
            await asyncio.sleep(2)
            if check_agent_ready(session):
                ready = True
                break
        if not ready:
            warning = "Agent may still be starting"

        # Inject startup prompt
        if req.initial_prompt.strip():
            injection = f"Read ~/coders-war-room/startup.md then follow these instructions:\n\n{req.initial_prompt}"
        else:
            injection = "Read ~/coders-war-room/startup.md — you are now in the War Room. Acknowledge with your name and role, then wait for instructions."
        send_to_tmux(session, injection)

        # Add to in-memory roster
        agent_entry = {
            "name": req.name,
            "role": req.role,
            "tmux_session": session,
            "dynamic": True,
        }
        AGENTS.append(agent_entry)
        AGENT_NAMES.add(req.name)
        AGENT_SESSIONS[req.name] = session
        AGENT_DIRS[req.name] = agent_dir
        agent_membership[req.name] = True

        # Announce creation
        saved = await save_message(
            "system", "all", f"{req.name} has joined the war room", "system"
        )
        await broadcast_ws({"type": "message", "message": saved})

        activity = get_agent_activity(session)
        activity["in_room"] = True
        await broadcast_ws({
            "type": "agent_created",
            "agent": {
                "name": req.name,
                "role": req.role,
                "presence": activity["presence"],
                "activity": activity["activity"],
                "in_room": True,
                "dynamic": True,
            },
        })

        result = {
            "status": "created",
            "agent": {
                "name": req.name,
                "role": req.role,
                "tmux_session": session,
                "presence": activity["presence"],
                "in_room": True,
                "dynamic": True,
            },
        }
        if warning:
            result["warning"] = warning
        return result

    except subprocess.CalledProcessError as e:
        # Clean up on failure
        subprocess.run(
            ["tmux", "kill-session", "-t", session],
            capture_output=True,
        )
        return JSONResponse(
            {"error": f"Failed to create tmux session: {e}"},
            status_code=500,
        )


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
