# Web-Based Agent Onboarding — Design Spec

**Date:** 2026-04-02
**Goal:** Create, configure, and launch new Claude Code agents directly from the War Room web UI
**Auth model:** Claude Max subscription (authentication-based, not per-token). All agents run via `claude` CLI.

---

## Problem

Agents are currently created via `onboard.sh` (command line) or `join.sh` (existing sessions). There's no way to spin up a new agent from the web UI. The user must SSH/terminal into the machine, edit config.yaml, and run scripts. This breaks the "single pane of glass" promise of the war room.

## Solution

A slide-out drawer in the web UI that lets the user create a fully configured Claude Code agent: pick a name, browse to a directory, write a role and initial prompt, choose a model, and launch — all from the browser.

---

## Onboarding Form

Triggered by a **+ New Agent** button in the sidebar header.

### Fields

| # | Field | Type | Details |
|---|-------|------|---------|
| 1 | Agent name | Text input | Lowercase, auto-hyphenated on spaces. Must be unique (validated against existing agents). Becomes the tmux session name `warroom-<name>`. |
| 2 | Working directory | Browse picker | `GET /api/browse?path=~` returns top-level directories from home. User clicks a folder to select (one level deep max). Selected path displayed as a pill. |
| 3 | Role | Text input | Short description of what this agent owns/does. Shown in the sidebar under the agent name. |
| 4 | Initial prompt | Textarea (multi-line) | The first task/instruction sent to the agent after it reads startup.md. Can be empty (agent just waits for instructions). |
| 5 | Model | Dropdown | Options: `opus` (Opus 4.6), `sonnet` (Sonnet 4.6), `haiku` (Haiku 4.5). Default: `opus`. |
| 6 | Skip permissions | Toggle switch | On = `--dangerously-skip-permissions`. Off = normal permission prompts. Default: on. |

### Validation

- Name: required, lowercase alphanumeric + hyphens only, 2-20 chars, unique
- Directory: required, must be a valid path returned by browse API
- Role: required, max 200 chars
- Initial prompt: optional
- Model: required (default pre-selected)

---

## UI: Slide-Out Drawer

- Slides in from the **right side**, overlaying the chat area
- Width: **420px**
- Dark card aesthetic matching existing War Room theme (bg-card, border, JetBrains Mono headings)
- Header: "New Agent" with an X close button
- Form fields stacked vertically
- Directory picker: shows folder grid/list on click, selected folder shown as a colored pill
- Create button at bottom: green accent, full-width, `LAUNCH AGENT` label
- Loading state after click: button shows spinner, "Creating..." text
- On success: drawer closes, agent appears in sidebar, system message posted
- On error: inline error message above the button

---

## Directory Browse API

### `GET /api/browse?path=<dir>`

Returns top-level contents of the given directory (directories only, no files).

**Request:** `GET /api/browse?path=/Users/gurvindersingh`

**Response:**
```json
{
  "current": "/Users/gurvindersingh",
  "parent": "/Users",
  "directories": [
    {"name": "contextualise", "path": "/Users/gurvindersingh/contextualise"},
    {"name": "coders-war-room", "path": "/Users/gurvindersingh/coders-war-room"},
    {"name": "Desktop", "path": "/Users/gurvindersingh/Desktop"},
    {"name": "Documents", "path": "/Users/gurvindersingh/Documents"},
    {"name": "hindsight", "path": "/Users/gurvindersingh/hindsight"}
  ]
}
```

**Rules:**
- Only returns directories (no files)
- Excludes hidden directories (starting with `.`) except `.claude`
- Excludes system directories (`Library`, `Applications`, etc.)
- Sorted alphabetically
- The `parent` field allows navigating up one level
- Clicking a directory in the list navigates INTO it (loads its children). The user can drill down as many levels as needed, one click at a time.
- A "Select this directory" button confirms the current `current` path as the chosen directory
- Path must be under the user's home directory (security boundary)

---

## Agent Creation API

### `POST /api/agents/create`

**Request body:**
```json
{
  "name": "refactor-agent",
  "directory": "/Users/gurvindersingh/contextualise",
  "role": "Refactoring specialist — cleans up code across all phases",
  "initial_prompt": "Review the northstar/ directory for code duplication and propose consolidation.",
  "model": "opus",
  "skip_permissions": true
}
```

**Server-side steps:**

1. **Validate** — name uniqueness (check BOTH in-memory roster AND config.yaml), directory exists, required fields
2. **Create tmux session** — `tmux new-session -d -s warroom-<name> -x 200 -y 50`
3. **Configure session** — `tmux set-option -t <session> mouse on`, history-limit 10000
4. **Start Claude Code** — `cd <directory> && claude --model <model> [--dangerously-skip-permissions]`
5. **Wait for ready** — poll tmux pane for Claude Code idle indicators (up to 30s). If timeout, still proceed but mark response with `"warning": "Agent may still be starting — startup injection sent to a potentially busy terminal"`
6. **Inject startup** — send: `Read ~/coders-war-room/startup.md then follow these instructions: <initial_prompt>`
7. **Add to runtime roster** — agent added to in-memory AGENTS list, AGENT_NAMES, AGENT_SESSIONS, agent_membership set to True. Marked as `dynamic: true`.
8. **Announce** — post system message: `<name> has joined the war room`
9. **Broadcast** — push agent_status update to all WebSocket clients

**Response:**
```json
{
  "status": "created",
  "agent": {
    "name": "refactor-agent",
    "role": "Refactoring specialist...",
    "tmux_session": "warroom-refactor-agent",
    "presence": "active",
    "in_room": true
  }
}
```

**Error responses:**
- 400: Name already taken, invalid name format, directory doesn't exist
- 500: tmux session creation failed, Claude Code didn't start

---

## Claude Code Startup Sequence

When a new agent is created, Claude Code starts with:

```bash
cd /Users/gurvindersingh/contextualise && claude --model opus --dangerously-skip-permissions
```

This means Claude Code automatically:
- Reads the project's `.claude/CLAUDE.md` (project instructions)
- Reads `~/.claude/CLAUDE.md` (global instructions)
- Loads all configured MCP servers from settings.json
- Loads all installed plugins
- Has access to all tools (Read, Edit, Bash, Agent, etc.)

The agent then receives the startup injection:
```
Read ~/coders-war-room/startup.md then follow these instructions:

[initial_prompt from the form]
```

If `initial_prompt` is empty, the injection is still sent as just:
```
Read ~/coders-war-room/startup.md — you are now in the War Room. Acknowledge with your name and role, then wait for instructions.
```

This ensures every agent reads the protocol even if no task is assigned yet.

The `startup.md` (to be drafted later) will contain:
- War room protocol (message prefixes, when to respond)
- Available warroom.sh commands
- MCP server inventory and plugin capabilities
- Git-agent protocol: all agents must know to post git requests to git-agent, never run destructive git commands directly, and wait for git-agent's plan+confirm workflow
- Shared conventions

---

## Runtime Agent Management

Dynamic agents (created via web UI) exist **in memory only**. They are NOT written to config.yaml.

### Reconciliation on Server Startup

On boot, the server runs a reconciliation scan:
1. Load permanent agents from `config.yaml` (as today)
2. Run `tmux list-sessions` and find all sessions prefixed with `warroom-`
3. For any session NOT in config.yaml, add it to the in-memory roster as a dynamic agent with:
   - `name`: derived from session name (strip `warroom-` prefix)
   - `role`: "Dynamic agent (recovered)"
   - `presence`: detected via `get_agent_activity()`
4. This means server restarts no longer orphan dynamic agents — they're automatically re-adopted

### Permanent vs Dynamic Distinction

Agents from config.yaml are **permanent** (survive server restarts, have full role descriptions). Agents created via the web UI are **dynamic** (recovered on restart but with minimal metadata).

The web UI sidebar distinguishes these visually:
- Permanent agents: normal display
- Dynamic agents: a small `~` indicator next to the name (meaning "ephemeral/dynamic")

**In-memory state changes:**
- `AGENTS` list gets a new entry appended
- `AGENT_NAMES` set gets the new name
- `AGENT_SESSIONS` dict gets the session mapping
- `agent_membership` dict gets True

---

## What This Does NOT Include

- No persistence of dynamic agents across server restarts
- No editing of existing agents from the web UI
- No file picker (directories only)
- No recursive directory tree (one level from home)
- No agent templates or presets
- No bulk onboarding
- No cost tracking (all agents use Claude Max subscription)

---

## Startup.md

A single global file at `~/coders-war-room/startup.md` read by every agent on creation. Contains shared context: war room protocol, available tools, conventions.

**Will be drafted separately.** Placeholder file created at build time with minimal content.
