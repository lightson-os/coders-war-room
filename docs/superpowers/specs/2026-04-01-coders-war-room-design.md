# Coder's War Room — Design Spec

**Date:** 2026-04-01
**Goal:** Production-ready inter-agent communication tool for 8 concurrent Claude Code sessions
**Constraint:** Must work today. Stability over polish.

---

## Problem

When running 7+ Claude Code sessions in parallel (6 phase owners, 1 supervisor, 1 git agent), there is no way for agents to communicate with each other or for the user to observe and direct the swarm from a single interface. The user must manually switch between terminal windows, copy-paste context, and relay messages — defeating the purpose of parallel work.

## Solution

A local real-time chat system where all agents and the user share a single conversation. Agents receive messages autonomously (without user activating each terminal) and respond when relevant.

---

## Architecture

### Components

| Component | File | Purpose |
|-----------|------|---------|
| Server | `server.py` | FastAPI app: REST API, WebSocket, tmux dispatch, serves web UI |
| Database | `warroom.db` | SQLite message store (auto-created on first run) |
| Web UI | `static/index.html` | Single-page chat interface (HTML + vanilla JS + CSS) |
| Agent CLI | `warroom.sh` | Shell script agents call to post messages |
| Onboard script | `onboard.sh` | Creates tmux sessions with agent identities |
| Config | `config.yaml` | Agent roster, port, project path |

### Port

**5680** — clear of all existing services (n8n: 5678, Hindsight: 8888/9999, Open-WebUI: 3001).

### Directory Structure

```
~/coders-war-room/
  server.py           # FastAPI server (single file)
  config.yaml         # Agent roster and settings
  warroom.sh          # Agent CLI tool
  onboard.sh          # tmux session creator
  static/
    index.html        # Chat web UI
  warroom.db          # SQLite (auto-created at runtime)
```

---

## Message Schema (SQLite)

```sql
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,          -- ISO 8601
    sender TEXT NOT NULL,             -- agent name or "gurvinder"
    target TEXT NOT NULL DEFAULT 'all', -- @tag: "all", "phase-1", "supervisor", etc.
    content TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'message' -- "message", "status", "system"
);

CREATE INDEX idx_messages_timestamp ON messages(timestamp);
```

## Agent Roster

Defined in `config.yaml`:

```yaml
port: 5680
project_path: ~/contextualise  # or whatever project the agents work on

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
    role: "Handles all git operations: commits, branches, PRs, conflict resolution"
    tmux_session: warroom-git-agent
```

---

## Message Flow

### Agent posts a message

1. Agent calls: `warroom post "I've finished wiring the state module"` or `warroom post --to phase-2 "Need your output schema"`
2. `warroom.sh` sends HTTP POST to `http://localhost:5680/api/messages`
3. Server writes to SQLite
4. Server broadcasts to all WebSocket clients (web UI updates in real-time)
5. Server dispatches to tmux sessions (see Dispatch Protocol below)

### User posts from web UI

1. User types in web chat, optionally @-tags an agent
2. WebSocket sends message to server
3. Server writes to SQLite
4. Server broadcasts to all other WebSocket clients
5. Server dispatches to tmux sessions

### Dispatch Protocol (tmux injection)

The server formats messages differently based on targeting:

**Direct message** (agent is @tagged):
```
[WARROOM @phase-1] supervisor: Need you to fix the state import in config.py
```
Agent sees this as user input. Onboarding instructions tell it: "Messages prefixed with [WARROOM @your-name] require your response and action."

**Broadcast** (target is "all"):
```
[WARROOM] phase-3: Finished wiring the event bus to the health monitor
```
Agent sees this as user input. Onboarding instructions tell it: "Broadcast messages are for your context. Only respond if it directly impacts your current work. If not relevant, simply say 'Noted' in the terminal (do NOT post to the war room) and continue your work."

**System message** (type is "system"):
```
[WARROOM SYSTEM] phase-5 has joined the war room
```
Informational only. Agent should not respond.

### Dispatch Rules

- A message is dispatched to ALL agents except the sender (everyone maintains context)
- The @tag controls the expected behavior, not the delivery
- Messages are delivered via `tmux send-keys -t <session-name> "<formatted-message>" Enter`
- If a tmux session doesn't exist (agent not yet onboarded), the message is stored in SQLite but not dispatched — the agent will see message history when it joins

---

## Agent Onboarding

`onboard.sh` does the following for each agent:

1. Creates a tmux session: `tmux new-session -d -s warroom-<name>` (supervisor gets extended scrollback: `tmux set-option -t warroom-supervisor history-limit 50000`)
2. Sends the initial Claude Code command with the project directory: `claude --dangerously-skip-permissions -p "<project_path>"`
3. Waits for Claude Code to become ready (polls for the input prompt indicator with a 10-second timeout)
4. Injects the onboarding prompt via `tmux send-keys`:

```
You are <name> in the Coder's War Room — a real-time communication system for parallel Claude Code agents working on the same project.

YOUR IDENTITY: <name>
YOUR ROLE: <role>
PROJECT: <project_path>

WAR ROOM PROTOCOL:
- Messages prefixed with [WARROOM @<your-name>] are directed at you. You MUST respond and act on them.
- Messages prefixed with [WARROOM] (no specific tag) are broadcasts. Read them for context. Only respond if it directly impacts your current work. If not relevant, just say "Noted" in the terminal and continue your work. Do NOT post acknowledgements to the war room — it creates noise.
- Messages prefixed with [WARROOM SYSTEM] are informational. Do not respond.
- To send a message to the war room, run: ~/coders-war-room/warroom.sh post "your message"
- To send a direct message: ~/coders-war-room/warroom.sh post --to <agent-name> "your message"
- Keep responses concise. This is a chat, not a document.
- When you complete a task or hit a blocker, post it to the war room immediately.
- You can check recent messages anytime: ~/coders-war-room/warroom.sh history
```

### Agent naming convention

All agent names are lowercase, hyphenated: `supervisor`, `phase-1` through `phase-6`, `git-agent`. These names are used everywhere: tmux session names, message sender/target fields, @tags in the chat UI.

---

## Web UI

Single-page HTML served by FastAPI at `http://localhost:5680`.

### Features

- Real-time message display via WebSocket (no polling)
- Messages color-coded by sender (each agent gets a consistent color)
- @-mention dropdown: type `@` and select from agent roster
- Send as "gurvinder" (the user's identity in the chat)
- Auto-scroll to latest message
- Message history loaded on connect (last 200 messages)
- Visual distinction between direct messages, broadcasts, and system messages
- Timestamp on each message
- **Activity pulse** per agent — green dot if `tmux has-session -t warroom-<name>` returns 0, grey if session is dead. Server polls session status every 5 seconds and pushes to web UI via WebSocket.

### Non-features (YAGNI)

- No message editing or deletion
- No file uploads
- No threads or replies
- No read receipts
- No authentication (local-only tool)
- No message search (SQLite CLI is available if needed)

---

## warroom.sh — Agent CLI

```bash
#!/bin/bash
# Usage:
#   warroom.sh post "message"                    # broadcast
#   warroom.sh post --to <agent> "message"       # direct message
#   warroom.sh history                            # last 20 messages
#   warroom.sh history --count 50                 # last 50 messages

WARROOM_SERVER="http://localhost:5680"
WARROOM_AGENT="${WARROOM_AGENT_NAME:-unknown}"
```

The agent's identity is set via the `WARROOM_AGENT_NAME` environment variable, injected during onboarding.

---

## Dispatch Safety — The Readiness Guard

tmux is blind — it has no idea whether Claude Code is mid-output, running a tool, or waiting for input. Injecting keys at the wrong moment causes garbled input or lost messages.

### Readiness Check (capture-pane)

Before dispatching to any agent, the server runs:
```bash
tmux capture-pane -t warroom-<name> -p -l 3
```
This grabs the last 3 lines of the terminal. If it contains Claude Code's input prompt indicator (the `>` character at start of line, or similar idle pattern), the agent is ready — send the message. If not, queue it.

### Per-Agent Message Queue

Each agent has a dispatch queue on the server. When a message arrives:
1. Check readiness via capture-pane
2. If ready → dispatch immediately via send-keys
3. If busy → enqueue the message
4. A background task polls every 2 seconds for busy agents, checking readiness

### Message Batching for Busy Agents

If multiple messages queue up while an agent is busy, they are combined into a single injection when the agent becomes ready:
```
[WARROOM] 3 messages while you were busy:

[WARROOM @phase-1] supervisor: Fix the import in config.py
[WARROOM] phase-3: Event bus is wired to health monitor
[WARROOM] git-agent: Committed phase-2 changes to feature branch
```
Agent gets full context in one shot, decides what to act on.

### Message Truncation

tmux send-keys has a buffer limit. Large messages choke the terminal buffer and can crash the agent session.

- Messages over **500 characters** are truncated in the tmux injection
- The truncated message includes a summary + pointer: `[Full message at http://localhost:5680/message/<id>]`
- The web UI always shows the full message
- The `/message/<id>` endpoint returns plain text (agent can curl it if needed)

---

## Git-Agent Protocol

The git-agent is the most cautious agent in the war room. It treats every incoming message as a **request to plan**, not a command to execute.

### Workflow

1. Receives a request (e.g., `@git-agent commit phase-2 changes`)
2. Posts its **plan** to the war room: "I will commit files X, Y, Z with message '...' to branch feature/phase-2. Confirm?"
3. **Waits for explicit confirmation** from gurvinder or supervisor before executing
4. Posts the result after execution: "Committed abc123 to feature/phase-2"

### Rules

- Never force-push without confirmation from gurvinder (not just supervisor)
- Never commit to main directly — always use feature branches
- Always post a diff summary before committing
- If a merge conflict is detected, post it to the war room and wait for guidance

---

## Concurrency & Safety

- **SQLite WAL mode** enabled for concurrent reads/writes from 8+ processes
- **Server is single-process** — all tmux dispatch happens sequentially per message (fast enough for chat-rate traffic)
- **tmux send-keys guarded by readiness check** — never injects into a busy terminal
- **No file locking needed** — SQLite handles it
- **Per-agent dispatch queues** — messages never lost, delivered in order when agent is ready

---

## Startup & Shutdown

### Start

```bash
cd ~/coders-war-room
# 1. Start the server
python3 server.py &

# 2. Onboard all agents (creates tmux sessions, starts Claude Code, injects identity)
./onboard.sh

# 3. Open web UI
open http://localhost:5680
```

### Stop

```bash
# Kill the server
pkill -f "python3 server.py"

# Kill all warroom tmux sessions
tmux kill-session -t warroom-supervisor
tmux kill-session -t warroom-phase-1
# ... etc, or:
tmux list-sessions | grep warroom | cut -d: -f1 | xargs -I{} tmux kill-session -t {}
```

### Dependencies

- Python 3.12 (already installed)
- FastAPI + uvicorn + aiosqlite (pip install)
- tmux (brew install if not present)
- No Docker, no Redis, no external services

---

## Edge Cases

| Scenario | Behavior |
|----------|----------|
| Agent tmux session dies | Messages accumulate in SQLite. Agent sees history when re-onboarded. |
| Server crashes | Agents can't post or receive. Restart server, no data lost (SQLite persists). |
| Two agents post simultaneously | SQLite WAL handles concurrent writes. Server processes sequentially. |
| Message sent to non-existent agent | Stored in DB, not dispatched. Warning shown in web UI. |
| Agent is mid-tool-call when message arrives | tmux queues input. Agent sees it when Claude Code next prompts for input. |
| Very long message | Messages over 500 chars truncated in tmux injection with link to full text at `/message/<id>`. Web UI always shows full message. |

---

## What This Is NOT

- Not a task manager — agents manage their own work
- Not a code review tool — use the git-agent for that
- Not persistent across projects — it's a disposable tool for the current sprint
- Not multi-user — it's Gurvinder + his agents, local only
