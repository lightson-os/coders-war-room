# Pipeline Optimization Research — 2026-04-12

> Research synthesis that informed the War Room Governed Pipeline Hardening plan (14 tasks, 4 phases).

## Research Streams

### 1. Perplexity Pipeline Report

**Query:** Multi-agent software development pipeline optimization — academic findings, AgentCoder, MetaGPT, MAST taxonomy.

**Key findings:**
- **AgentCoder** (2024): Test-driven agent development reduces bug rates by 63% vs non-TDD agent workflows. The programmer-tester-executor triangle mirrors our Engineer-QA-Git Agent pattern.
- **MetaGPT** (2023): Role-specialized agents with structured communication protocols outperform generalist agents by 2-3x on complex tasks. Validates our six-role architecture.
- **MAST Taxonomy** (Multi-Agent System Threats): Four failure categories — Misalignment, Authority violation, Silent failure, Temporal drift. Each maps to specific War Room bugs we've seen.
- **ChatDev** (2024): Waterfall-inspired phase gating (design → code → test → review) with mandatory sign-offs between phases. Similar to our gate architecture but less flexible.

**Impact on plan:** MAST taxonomy directly informed the skill authoring guide. AgentCoder findings validated our TDD requirement. MetaGPT's structured communication principle reinforced file-based handoffs over chat-based coordination.

### 2. Gate Accountability Analysis (Five-Agent Parallel Investigation)

**Method:** Five parallel agents each analyzed one aspect of the gate system: tool coverage, failure handling, retry behavior, escalation chains, and cross-gate dependencies.

**Findings:**
- Gate 1 (Deterministic) has 7 tools but no JSON output standardization — each tool produces different output formats, making automated parsing fragile.
- Gate 2 (Integration) has no stall detection — a hung `flyctl deploy` blocks the pipeline indefinitely.
- Gate 3 (AI Review) has no budget tracking — Greptile and CodeRabbit have rate limits that aren't monitored.
- Retry ceilings are not enforced structurally — agents self-report retry counts. Need hook-verified enforcement.
- Escalation chains exist in documentation but not in code — no automated escalation from gate failure to supervisor notification.

**Impact on plan:** Added `json_flag` fields to gate-registry tools. Added `stall_detection` to Gate 2. Created tool-budget-registry.yaml. Hook scripts now POST events to the server for structural verification.

### 3. Skill Audit Results (9 Skills Scored)

**Method:** Evaluated all 9 agent skills against 5 dimensions (clarity, completeness, separation, enforcement, precedent), 0-10 each.

**Results summary:**
| Skill | Clarity | Completeness | Separation | Enforcement | Precedent | Total |
|-------|---------|-------------|------------|-------------|-----------|-------|
| supervisor-role | 7 | 6 | 8 | 3 | 5 | 29/50 |
| scout-role | 7 | 7 | 7 | 3 | 6 | 30/50 |
| engineer-role | 8 | 7 | 7 | 4 | 7 | 33/50 |
| qa-role | 8 | 8 | 8 | 5 | 7 | 36/50 |
| git-agent-role | 6 | 5 | 7 | 2 | 4 | 24/50 |
| chronicler-role | 5 | 4 | 6 | 2 | 3 | 20/50 |
| guardrails | 9 | 8 | 9 | 6 | 8 | 40/50 |
| persistence-protocol | 8 | 8 | 8 | 5 | 7 | 36/50 |
| war-room-protocol | 7 | 6 | 7 | 3 | 5 | 28/50 |

**Key gap:** Enforcement scores are universally low (2-6). Skills describe rules but don't verify compliance structurally. The hook system addresses this — enforcement should improve to 7+ after hardening.

**Impact on plan:** Led to the scaffold generator approach — auto-generated tables for gate/hook/tool information ensure skills always reflect current registry state. Collaborative sections can focus on behavioral instructions.

### 4. War Room Structural Analysis

**BUG-001: Context Isolation**
- Agents share the same `.claude/settings.json` (project-level). Role-specific settings require `.claude/settings.local.json` generated per agent at onboard time.
- Solution: Settings generator (Task 4) produces role-specific settings.local.json.

**Hook Gaps Identified:**
- No SessionStart hook to auto-invoke role skill (agents must remember to invoke manually).
- No PostToolUse hook for automatic linting feedback.
- No Stop hook for QA to verify qa-suite.sh was run.
- Existing Stop hook (stop-guard-warroom.sh) only checks for critical messages, not quality gates.

**Context Isolation:**
- `.claude/settings.local.json` overrides project-level settings when present.
- Settings generator writes to the agent's working directory, not the War Room directory.
- Each tmux session gets `WARROOM_ROLE_TYPE` env var for hook scripts to reference.

**Impact on plan:** Created session-start.sh, engineer-quality-gate.sh, qa-quality-gate.sh, post-edit-lint.sh hooks. Settings generator wired into agent creation flow.

### 5. Third-Party Review Findings

**Source:** CodeRabbit + manual review of hook infrastructure.

**Hook Failure Modes:**
- Hooks that crash (non-zero exit without proper JSON) can block agent workflow indefinitely.
- Solution: All hooks use `trap 'echo "Hook crashed: $0" >&2; exit 2' ERR` pattern.
- Hooks that hang: No timeout enforcement at the shell level.
- Solution: Claude Code hook config supports `timeout` field (already in hook-registry.yaml).

**Hash-Based Sync:**
- Registry changes without regenerating skills create drift.
- Solution: `save_generation_hashes()` in generate.py records SHA-256 of each registry. `validate_registry_sync()` in server.py checks at boot.

**Deploy Fragility:**
- Settings generation during agent creation could fail, leaving agent without proper hooks.
- Solution: Settings generation is wrapped in try/except — failure logs warning but doesn't block agent creation.

## Cross-Cutting Themes

1. **Structural enforcement > honor system** — Hooks verify what skills describe. Trust but verify.
2. **Registry-driven architecture** — Single source of truth in YAML, consumed by generators, hooks, UI.
3. **File-based handoffs** — Durable artifacts between roles, not ephemeral chat messages.
4. **Failure mode awareness** — MAST taxonomy provides vocabulary for categorizing and preventing agent failures.
5. **Incremental skill improvement** — Scaffold generator handles the mechanical parts; collaborative sessions handle the judgment parts.

## References

- AgentCoder: Multi-Agent-Based Code Generation with Iterative Testing and Optimisation (2024)
- MetaGPT: Meta Programming for a Multi-Agent Collaborative Framework (2023)
- ChatDev: Communicative Agents for Software Development (2024)
- MAST: Multi-Agent System Threats taxonomy (security research, 2024)
- War Room design spec: `docs/superpowers/specs/2026-04-12-war-room-hardening-design.md`
- Implementation plan: `docs/superpowers/plans/2026-04-12-war-room-hardening.md`
