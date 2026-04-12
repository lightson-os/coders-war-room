# Skill Authoring Guide — War Room Agents

> How to write, test, and maintain agent SKILL.md files for the Coders War Room.

## Overview

Each War Room agent has a SKILL.md file at `~/.claude/skills/<role>-role/SKILL.md`. This file contains the agent's identity, behavioral rules, workflow instructions, and registry-derived tables. The skill file is invoked at session start via the SessionStart hook.

SKILL.md files have two sections:
1. **Auto-generated section** (above boundary line) — produced by `skill-engine/generate.py` from YAML registries. Never hand-edit.
2. **Collaborative section** (below boundary line) — authored by human + Claude Code. Contains role-specific behavior, workflow, and judgment rules.

The boundary line:
```
<!-- ═══ BELOW THIS LINE: Collaborative section — authored by human + Claude Code ═══ -->
```

## Skill Structure

### Frontmatter

```yaml
---
name: engineer-role
description: Execute implementation tasks with TDD and zero regressions.
user-invocable: false
requires:
  - guardrails-contextualise
  - persistence-protocol
  - war-room-protocol
version: "2.0"
---
```

- `user-invocable: false` — agents invoke their own skill at session start; users don't invoke directly
- `requires` — lists prerequisite skills loaded before this one
- `version` — tracks skill evolution; bump on major behavioral changes

### Auto-Generated Tables

Produced by `skill-engine/generate.py` from registries:

1. **Gate Accountability** — which gates this role runs, fixes, investigates, or routes
2. **Tool Assignments** — which gate tools this role operates, with dispositions and budgets
3. **Hook Enforcement** — structural hooks that fire automatically (not under agent control)
4. **War Room Signals** — gate failure/escalation signals this role should watch for

To regenerate: `python skill-engine/generate.py --role <name>` or `--all`

### Collaborative Section

This is where the skill's actual behavioral instructions live. Key sections:

- **Your Role** — identity, responsibilities, what you do and don't do
- **Session Startup** — checklist of actions at session start (read status, check Jira, etc.)
- **Your Workflow** — step-by-step process for your primary task type
- **Decision Rules** — confidence thresholds, escalation triggers, judgment guidelines
- **Communication** — how to post to War Room, when to tag others

## Writing Principles

### 1. Separation of Duties

Each skill has exactly one primary responsibility. If you find yourself writing "and also" frequently, the skill is too broad. The six roles exist because each has a distinct decision domain:

| Role | Decides | Never Decides |
|------|---------|---------------|
| Supervisor | What to build, who does it | How to build it |
| Scout | What the code does, what's risky | Whether to change it |
| Engineer | How to implement | Whether to ship |
| QA | Whether quality is sufficient | How to fix issues |
| Git Agent | When to commit/merge | What to commit |
| Chronicler | What patterns to flag | Whether to act on them |

### 2. File-Based Handoffs

Agents communicate through files, not conversation. Every handoff between roles produces a durable artifact:

- Scout → Engineer: `docs/research/<STORY-ID>_notes.md`
- Engineer → QA: Feature branch with code + tests
- QA → Git Agent: `docs/qa/<STORY-ID>_review.md`
- Git Agent → Supervisor: Merge confirmation
- Supervisor → All: `docs/PROJECT_STATUS.md`

Skills should reference these handoff files explicitly. Don't say "coordinate with QA" — say "QA reads `docs/qa/<STORY-ID>_review.md`."

### 3. Hook-Verified Truth

Skills should not rely on agent self-reporting for compliance. The hook system provides structural enforcement:

- **Engineer says tests pass** → `engineer-quality-gate.sh` verifies at Stop
- **QA says suite ran** → `qa-quality-gate.sh` checks for output files
- **Git Agent says QA passed** → `verify-qa-before-merge.sh` checks the report file

Write skills that assume hooks are enforcing the rules. Don't add redundant "make sure you..." instructions for things hooks already verify.

### 4. The Precedent Rule

When writing behavioral instructions, cite the origin. Every non-obvious rule exists because something went wrong:

- "Verify wiring points" → Protocol 8, origin: dead-wiring in NS-24 and NS-37
- "Runtime QA, not just code review" → Protocol 9, origin: Sprint 2 mock-tests-pass-but-app-broken
- "Verify external findings" → Protocol 11, origin: 4 CodeRabbit false positives in Sprint 3

## Failure Modes to Design Against (MAST Taxonomy)

When writing skills, design against these common multi-agent failure modes:

### M — Misalignment
Agent works on wrong task or misinterprets requirements. **Prevention:** Explicit acceptance criteria in task briefs. Skills reference specific file paths and field names, not vague descriptions.

### A — Authority Violation
Agent modifies files outside its scope or makes decisions above its level. **Prevention:** `files_writable` lists in task briefs. `disallowed_tools` in role-registry. `block-code-writes.sh` hook for non-coding roles.

### S — Silent Failure
Agent encounters an error but doesn't report it, or reports success when partially complete. **Prevention:** `verification-before-completion` skill mandatory before claiming done. Hook-verified gates catch unreported failures.

### T — Temporal Drift
Agent uses stale information (old branch, outdated status, cached knowledge). **Prevention:** Session startup checklists that read current state. Registry sync validation at server boot. Fresh sessions preferred over long-running ones.

## TDD for Skills (RED-GREEN-REFACTOR)

Skills benefit from the same TDD discipline as code:

### RED: Define the failure case first
Before writing a new skill instruction, identify what goes wrong without it. Document the specific failure: "Without this rule, the Engineer skips runtime wiring verification, leading to dead code paths (NS-24, NS-37)."

### GREEN: Write the minimum instruction
Write the simplest rule that prevents the failure. Don't over-specify. A good instruction is one sentence with a clear trigger and action.

### REFACTOR: Observe and tighten
After the skill has been used in 2-3 sprints, review the Chronicler's observations. Remove rules that hooks now enforce. Tighten vague rules into specific ones. Merge overlapping rules.

## Scoring Protocol

Use this rubric to evaluate skill quality (0-10 per dimension):

| Dimension | 0 | 5 | 10 |
|-----------|---|---|-----|
| Clarity | Ambiguous, multiple interpretations | Clear but verbose | Concise, one interpretation |
| Completeness | Missing critical workflows | Covers happy path | Covers happy path + edge cases |
| Separation | Overlaps with other roles | Minor boundary blur | Clean single-responsibility |
| Enforcement | All honor-system | Mix of hooks and trust | All critical rules hook-verified |
| Precedent | Rules without origin | Some rules cited | Every non-obvious rule has origin |

Target: 7+ on all dimensions before a skill ships.

## Collaborative Session Protocol

When writing or updating the collaborative section of a SKILL.md:

1. **Read the current SKILL.md** — understand what exists
2. **Read the auto-generated section** — know what registries provide (don't duplicate)
3. **Read the Chronicler's latest observations** — identify drift or gaps
4. **Draft changes in the War Room** — discuss with Supervisor before editing
5. **Edit below the boundary line only** — never touch auto-generated content
6. **Run the generator after editing** — `python skill-engine/generate.py --role <name>` to ensure auto section is current
7. **Commit via Git Agent** — standard persistence protocol

## Quick Reference

| Action | Command |
|--------|---------|
| Preview all skills | `python skill-engine/generate.py --all --diff` |
| Regenerate one skill | `python skill-engine/generate.py --role qa` |
| Regenerate all skills | `python skill-engine/generate.py --all` |
| Check registry sync | Server startup validates automatically |
| View registry hash | `head -1 <SKILL.md>` shows `<!-- REGISTRY VERSION: ... -->` |
