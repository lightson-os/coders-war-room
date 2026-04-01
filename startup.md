# War Room — Agent Startup Protocol

You are an agent in the Coder's War Room. Follow these rules:

## Communication
- Messages prefixed with `[WARROOM @your-name]` are directed at you. You MUST respond and act.
- Messages prefixed with `[WARROOM]` are broadcasts. Respond only if it impacts your work. Otherwise say "Noted" in the terminal (do NOT post to the war room).
- Messages prefixed with `[WARROOM SYSTEM]` are informational. Do not respond.

## Commands
- Post a message: `~/coders-war-room/warroom.sh post "your message"`
- Direct message: `~/coders-war-room/warroom.sh post --to <agent> "message"`
- See messages for you: `~/coders-war-room/warroom.sh mentions`
- See all messages: `~/coders-war-room/warroom.sh history`

## Git Protocol
All git operations go through the git-agent. Never run destructive git commands (push, reset, rebase) directly. Instead:
1. Post to the war room: `@git-agent please commit my changes in <files>`
2. Wait for git-agent to post a plan
3. Wait for gurvinder or supervisor to confirm
4. git-agent executes

## Conventions
- Keep war room messages concise. This is a chat, not a document.
- When you complete a task or hit a blocker, post it to the war room immediately.
- You have access to all MCP servers and plugins configured in Claude Code.
