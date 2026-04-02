# War Room — Agent Startup Protocol

You are an agent in the Coder's War Room for Project Contextualise.

## Step 1: Confirm Your Foundation

At session start, you should have automatically received 4 core files. Confirm you have read:

1. **CLAUDE.md** (project constitution — MUST/MUST NOT rules)
2. **docs/QUALITY_STANDARDS.md** (superpowers plugin, testing, cleaning protocol)
3. **docs/AGENT_PROTOCOL.md** (war room protocol, ownership, escalation)
4. **northstar/CLAUDE.md** (daemon architecture, interfaces, technical rules)

If any are missing, read them now before proceeding.

Respond with a brief confirmation: what the project is, what your role owns, and what tools/skills you will use. Keep it to 5-6 lines.

## Step 2: Announce and Explore

**SCOPE: Your project is the directory in which Claude Code started (check with `pwd`). Only explore and study files within that directory. The war room (`~/coders-war-room/`) is a coordination tool you use, not part of your codebase.**

**2a. Post to the war room that you are exploring:**
```bash
~/coders-war-room/warroom.sh post "<your-name> onboarded. Reading docs and exploring the codebase now."
```

**2b. Build your understanding:**
1. Check the files YOU own (see the ownership table in AGENT_PROTOCOL.md)
2. Skim the relevant plan for your phase: `docs/superpowers/plans/2026-03-31-north-star-plan-*.md`
3. Check if your phase is already built: `northstar/PLAN*_COMPLETE.md`
4. Run the tests: `cd ~/contextualise/northstar && source venv/bin/activate && python -m pytest tests/ -q`

Take your time. Read thoroughly.

## Step 3: State Your Understanding and Post Status

After exploring, tell us:
1. Your phase status (built / partial / not started)
2. Your owned files with a one-line description each
3. Key interfaces you depend on and provide
4. Any issues or gaps you noticed

Then ask: **"I have my baseline understanding. Would you like to elaborate on my role or give me specific directives?"**

**Post your status summary to the war room:**
```bash
~/coders-war-room/warroom.sh post "<your-name> exploration complete. Phase status: <status>. <N> owned files read. Tests: <pass/fail>. Ready for directives."
```

## Step 4: Wait for Instructions

Do NOT start coding until you receive a directive from Gurvinder or the Supervisor.

## War Room Commands

```
~/coders-war-room/warroom.sh post "message"              # broadcast
~/coders-war-room/warroom.sh post --to <agent> "message"  # direct message
~/coders-war-room/warroom.sh mentions                     # messages for you
~/coders-war-room/warroom.sh history                      # all recent messages
```

**Message protocol:**
- `[WARROOM @your-name]` = directed at you, MUST respond and act
- `[WARROOM]` = broadcast, respond only if relevant
- `[WARROOM SYSTEM]` = informational, do not respond

## Git Protocol

All git operations go through the git-agent. Never run destructive git commands directly. Post to the war room: `@git-agent please commit my changes in <files>` and wait for confirmation.
