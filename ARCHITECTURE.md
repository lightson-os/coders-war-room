# Architecture

## Overview

The Coder's War Room is a local real-time coordination system for multiple Claude Code agents. It consists of a FastAPI server, a web UI, and tmux-based agent sessions connected by WebSocket and HTTP.

## System Components

### 1. FastAPI Server (`server.py`)

Single-file server (~1300 lines) handling:

- **REST API** — CRUD for messages, agents, files, server management
- **WebSocket** — real-time push to web UI clients (agent status every 10s, messages instantly)
- **tmux Dispatch** — delivers messages to agent sessions via `set-buffer` + `paste-buffer`
- **Background Loops** — queue flushing (2s), agent status (10s), git commit refresh (30s)
- **SQLite** — message persistence with WAL mode for concurrent access

#### Key Design Decisions

**Readiness Guard:** Before dispatching to an agent, the server captures the last 15 lines of the tmux pane and checks for busy indicators (braille spinners, "Thinking" text). If busy, the message is queued. The queue flushes every 2 seconds.

**Message Deduplication:** Each agent tracks the last message ID it received (`agent_last_seen_id`). Messages with IDs at or below the last-seen are skipped. On server restart, all agents' last-seen is initialized to the latest message ID in SQLite (prevents replay).

**Dynamic Agent Roster:** Agents from `config.yaml` are permanent. Agents created via the web UI are dynamic (in-memory only). On server restart, orphaned tmux sessions prefixed with `warroom-` are auto-adopted via a reconciliation scan.

**Manual Status with TTL:** Agents can post rich status (task, progress, ETA, blocker) via `warroom.sh status`. Manual fields expire after 30 minutes of inactivity. The TTL resets on any detected agent activity (tmux pane changes).

### 2. Web UI (`static/index.html`)

Single-file vanilla HTML/CSS/JS (~2100 lines). No frameworks, no build step.

**Three-column layout:**
- Left (300px): Agent dashboard with live status cards
- Center (flex): Chat with message grouping and dynamic border colors
- Right (280px): Project file browser with drag-and-drop

**WebSocket Protocol:**
```
Server → Client:
  {type: "history", messages: [...]}        — on connect
  {type: "message", message: {...}}         — new message
  {type: "agent_status", server: {...}, agents: {...}}  — every 10s
  {type: "membership", agent: "...", in_room: bool}     — de/reboard
  {type: "agent_created", agent: {...}}     — new agent
  {type: "agent_removed", agent: "..."}     — agent deleted

Client → Server:
  {sender: "gurvinder", target: "all", content: "...", type: "message"}
```

### 3. Agent Sessions (tmux)

Each agent runs Claude Code in a named tmux session (`warroom-<name>`). The server delivers messages by:

1. Checking readiness (capture-pane for busy indicators)
2. Setting a tmux buffer with the formatted message
3. Pasting the buffer into the session
4. Sending Enter to submit

**Session naming convention:** `warroom-<agent-name>` (e.g., `warroom-engineer-1`). The agent's identity is derived from the session name.

### 4. CLI (`warroom.sh`)

Bash script that agents call to interact with the war room. Identity is auto-detected from the tmux session name. All commands are thin wrappers around the REST API.

## Data Flow

### Message Lifecycle

```
1. Agent posts via warroom.sh → POST /api/messages
2. Server saves to SQLite
3. Server broadcasts via WebSocket (web UI updates instantly)
4. Server dispatches to all agents via tmux:
   a. Check readiness (capture-pane)
   b. If ready → deliver via paste-buffer + Enter
   c. If busy → queue (flush loop retries every 2s)
5. Dedup filter: skip if msg.id <= agent's last_seen_id
6. Each queued message delivered individually (no batching)
```

### Agent Status Flow

```
Every 10 seconds:
1. For each agent, capture tmux pane → parse activity
2. Check for busy indicators (spinners, "Thinking")
3. Check for staleness (5+ min same tool+file)
4. Merge three layers: config (static) → auto-detect → manual status
5. Check session_alive (tmux has-session)
6. Push via WebSocket to all web UI clients
```

### Agent Onboarding Flow

```
Web UI: User fills form → POST /api/agents/create
Server:
  1. Validate (name uniqueness, directory exists)
  2. Create tmux session in chosen directory
  3. Configure (mouse on, scrollback, window title)
  4. Start Claude Code with model + permission flags
  5. Wait for ready (up to 30s)
  6. Inject onboarding prompt (points to startup.md + role instructions)
  7. Add to in-memory roster
  8. Announce via system message + WebSocket broadcast
```

## State Management

### Persistent (SQLite)
- Messages (id, timestamp, sender, target, content, type)

### In-Memory (server.py globals)
- `AGENTS` — agent roster (config.yaml + dynamic)
- `AGENT_NAMES`, `AGENT_SESSIONS`, `AGENT_DIRS` — lookup dicts
- `agent_membership` — who's in the room (de-board state)
- `agent_queues` — pending messages per agent
- `agent_last_seen_id` — dedup tracking
- `agent_manual_status` — manual status with TTL
- `agent_last_state` — staleness tracking
- `agent_last_commit` — last git commit per agent
- `agent_config` — creation config for recovery
- `connected_clients` — WebSocket connections

### Client-Side (localStorage)
- Agent card order (persists drag-to-reorder)

## Security

- **Directory browsing** restricted to home directory (`/api/browse`) or project directory (`/api/files`)
- **Path traversal** prevented via `resolve()` + `startswith()` checks
- **No authentication** — local-only tool (port 5680, not exposed)
- **HTML escaping** on all user content in the web UI

## Testing

- **Unit tests** (`test_api.py`): 20 tests using httpx AsyncClient with ASGI transport. No server process needed. Fresh temp DB per test via conftest fixture.
- **Integration tests** (`test_integration.py`): 13 tests against a real server on port 5681 (isolated from live server on 5680). Tests the full stack: API + CLI + tmux.
