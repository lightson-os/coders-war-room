#!/usr/bin/env python3
"""skill-engine/generate.py — Scaffold generator for agent SKILL.md files.

Reads the four YAML registries and produces the auto-generated portion of each
role's SKILL.md. The collaborative portion (below the boundary line) is never
overwritten.

Usage:
    python skill-engine/generate.py --role qa
    python skill-engine/generate.py --all
    python skill-engine/generate.py --diff
"""

import argparse
import hashlib
import json
import os
import sys

import yaml

WARROOM_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_DIR = os.path.join(WARROOM_DIR, "registries")
SKILLS_DIR = os.path.expanduser("~/contextualise/.claude/skills")
BOUNDARY = "<!-- ═══ BELOW THIS LINE: Collaborative section — authored by human + Claude Code ═══ -->"
AUTO_START = "<!-- AUTO-GENERATED from registries — do not hand-edit above the boundary line -->"


def load_reg(name: str) -> dict:
    with open(os.path.join(REGISTRY_DIR, f"{name}.yaml")) as f:
        return yaml.safe_load(f)


def registry_hash() -> str:
    """SHA-256 of all four registries concatenated."""
    h = hashlib.sha256()
    for name in ["gate-registry", "role-registry", "hook-registry", "tool-budget-registry"]:
        path = os.path.join(REGISTRY_DIR, f"{name}.yaml")
        with open(path, "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:12]


def generate_gate_table(role_name: str, gate_reg: dict, role: dict) -> str:
    """Generate the Gate Accountability table for a role."""
    gates_for = role.get("gates_accountable_for", [])
    gates_routes = role.get("gates_routes_on_fail", [])
    gates_investigates = role.get("gates_investigates_on_fail", [])

    all_gates = set(gates_for + gates_routes + gates_investigates)
    if not all_gates:
        return ""

    lines = [
        "## Gate Accountability",
        AUTO_START,
        "",
        "| Gate | Your Role | Tools | Retry Ceiling | On Fail Signal |",
        "|------|-----------|-------|---------------|----------------|",
    ]

    for gate_id, gate in gate_reg.get("gates", {}).items():
        # Match gate IDs: role-registry uses short form (gate-1), gate-registry uses full (gate-1-deterministic)
        matched = False
        role_desc = ""
        for g in all_gates:
            if gate_id.startswith(g) or gate_id == g:
                matched = True
                if g in gates_for:
                    role_desc = "**Run & Fix**"
                elif g in gates_investigates:
                    role_desc = "Investigate"
                elif g in gates_routes:
                    role_desc = "Route failures"
                break
        if not matched:
            continue

        tool_names = [t["id"] for t in gate.get("tools", [])
                      if role_name in t.get("agent", []) or role_desc == "Route failures"]
        tools_str = ", ".join(tool_names) if tool_names else "—"
        ceiling = gate.get("retry_ceiling", "—")
        signal = gate.get("failure_signal", "—")
        lines.append(f"| {gate.get('name', gate_id)} | {role_desc} | {tools_str} | {ceiling} | `{signal}` |")

    lines.append("")
    return "\n".join(lines)


def generate_tool_table(role_name: str, gate_reg: dict, role: dict, budget_reg: dict) -> str:
    """Generate the Tool Assignments table for a role."""
    review_tools = role.get("gate_tools_in_review", role.get("gate_tools_in_pre_commit", []))
    if not review_tools:
        return ""

    budgets = budget_reg.get("budgets", {})

    lines = [
        "## Tool Assignments",
        AUTO_START,
        "",
        "| Tool | Disposition | Budget |",
        "|------|-------------|--------|",
    ]

    for gate_id, gate in gate_reg.get("gates", {}).items():
        for tool in gate.get("tools", []):
            if tool["id"] in review_tools:
                budget_info = budgets.get(tool["id"], {})
                if budget_info and "limit" in budget_info:
                    budget_str = (
                        f"{budget_info['limit']} {budget_info['unit']}/{budget_info['period']}"
                    )
                else:
                    budget_str = "—"
                lines.append(
                    f"| {tool['id']} | {tool.get('disposition', '—')} | {budget_str} |"
                )

    lines.append("")
    return "\n".join(lines)


def generate_hook_table(role: dict, hook_reg: dict) -> str:
    """Generate the Hook Enforcement table for a role."""
    templates = hook_reg.get("templates", {})
    hook_entries = role.get("hooks", [])

    lines = [
        "## Hook Enforcement",
        AUTO_START,
        "",
        "These hooks are structural — you do not control them. They fire automatically.",
        "",
        "| Hook | Event | What It Does |",
        "|------|-------|-------------|",
    ]

    for entry in hook_entries:
        tname = entry.get("template") if isinstance(entry, dict) else entry
        template = templates.get(tname, {})
        desc = template.get("description", "")
        for event_name, hooks in template.get("hooks", {}).items():
            for hook in hooks:
                cmd = os.path.basename(hook.get("command", ""))
                lines.append(f"| {cmd} | {event_name} | {desc} |")

    lines.append("")
    return "\n".join(lines)


def generate_signal_table(role: dict, gate_reg: dict) -> str:
    """Generate the War Room Signals table for a role."""
    all_gates = set(
        role.get("gates_accountable_for", []) +
        role.get("gates_routes_on_fail", []) +
        role.get("gates_investigates_on_fail", [])
    )
    if not all_gates:
        return ""

    lines = [
        "## War Room Signals",
        AUTO_START,
        "",
        "| Signal | When |",
        "|--------|------|",
    ]

    for gate_id, gate in gate_reg.get("gates", {}).items():
        # Match gate IDs with prefix matching
        matched = any(gate_id.startswith(g) or gate_id == g for g in all_gates)
        if not matched:
            continue
        name = gate.get("name", gate_id)
        if gate.get("failure_signal"):
            lines.append(f"| `{gate['failure_signal']}` | Routine failure — {name} |")
        if gate.get("escalation_signal"):
            lines.append(f"| `{gate['escalation_signal']}` | Same file fails twice or 30+ min |")
        if gate.get("human_signal"):
            lines.append(f"| `{gate['human_signal']}` | Security, confidence <60% |")

    lines.append("")
    return "\n".join(lines)


def generate_scaffold(role_name: str) -> str:
    """Generate the complete auto-generated portion of a SKILL.md."""
    gate_reg = load_reg("gate-registry")
    role_reg = load_reg("role-registry")
    hook_reg = load_reg("hook-registry")
    budget_reg = load_reg("tool-budget-registry")

    role = role_reg.get("roles", {}).get(role_name)
    if not role:
        raise ValueError(f"Role '{role_name}' not found in role-registry.yaml")

    sections = [
        generate_gate_table(role_name, gate_reg, role),
        generate_tool_table(role_name, gate_reg, role, budget_reg),
        generate_hook_table(role, hook_reg),
        generate_signal_table(role, gate_reg),
    ]

    # Filter empty sections
    sections = [s for s in sections if s.strip()]

    reg_hash = registry_hash()
    header = f"<!-- REGISTRY VERSION: {reg_hash} -->"

    return "\n".join([header, ""] + sections + ["", BOUNDARY])


def update_skill(role_name: str, dry_run: bool = False) -> str:
    """Update a SKILL.md's auto-generated section, preserving the collaborative section."""
    skill_dir = os.path.join(
        SKILLS_DIR,
        f"{role_name}-role" if not role_name.endswith("-role") else role_name
    )
    skill_path = os.path.join(skill_dir, "SKILL.md")

    new_scaffold = generate_scaffold(role_name.replace("-role", ""))

    if not os.path.exists(skill_path):
        # New skill — scaffold only
        os.makedirs(skill_dir, exist_ok=True)
        role_reg = load_reg("role-registry")
        role = role_reg["roles"][role_name.replace("-role", "")]
        frontmatter = f"""---
name: {role_name if role_name.endswith('-role') else role_name + '-role'}
description: {role.get('description', '')}
user-invocable: false
requires:
  - guardrails-contextualise
  - persistence-protocol
  - war-room-protocol
version: "2.0"
---

# {role.get('display_name', role_name)} Instructions — Project Contextualise

"""
        content = (
            frontmatter + new_scaffold +
            "\n\n## Your Role\n<!-- SCAFFOLD: flesh out in collaborative session -->\n\n"
            "## Session Startup\n<!-- SCAFFOLD: flesh out in collaborative session -->\n\n"
            "## Your Workflow\n<!-- SCAFFOLD: flesh out in collaborative session -->\n"
        )

        if dry_run:
            return f"WOULD CREATE: {skill_path}\n{content[:200]}..."
        with open(skill_path, "w") as f:
            f.write(content)
        return f"CREATED: {skill_path}"

    # Existing skill — replace auto section, preserve collaborative section
    with open(skill_path) as f:
        existing = f.read()

    if BOUNDARY in existing:
        # Split at boundary, keep everything after
        parts = existing.split(BOUNDARY, 1)
        # Find where auto-generated section starts (after frontmatter + title)
        # Look for the first AUTO-GENERATED comment or REGISTRY VERSION comment
        pre_auto = parts[0]
        collaborative = parts[1]

        # Find where auto section begins
        auto_markers = ["<!-- REGISTRY VERSION:", "<!-- AUTO-GENERATED"]
        auto_start_pos = len(pre_auto)
        for marker in auto_markers:
            pos = pre_auto.find(marker)
            if pos != -1 and pos < auto_start_pos:
                auto_start_pos = pos

        before_auto = pre_auto[:auto_start_pos].rstrip() + "\n\n"
        new_content = before_auto + new_scaffold + collaborative

        if dry_run:
            return f"WOULD UPDATE auto section: {skill_path}"
        with open(skill_path, "w") as f:
            f.write(new_content)
        return f"UPDATED: {skill_path}"
    else:
        # No boundary marker — can't safely update. Warn.
        return (
            f"SKIPPED: {skill_path} — no boundary marker found. Manual update required."
        )


def save_generation_hashes():
    """Record current registry hashes for sync validation."""
    hashes = {}
    for name in ["gate-registry", "role-registry", "hook-registry", "tool-budget-registry"]:
        path = os.path.join(REGISTRY_DIR, f"{name}.yaml")
        with open(path, "rb") as f:
            hashes[name] = hashlib.sha256(f.read()).hexdigest()
    out_path = os.path.join(REGISTRY_DIR, ".last-generated.json")
    with open(out_path, "w") as f:
        json.dump(hashes, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Generate SKILL.md scaffolds from registries")
    parser.add_argument("--role", help="Generate for a specific role")
    parser.add_argument("--all", action="store_true", help="Generate for all roles")
    parser.add_argument("--diff", action="store_true", help="Preview changes without writing")
    args = parser.parse_args()

    if not args.role and not args.all and not args.diff:
        parser.print_help()
        sys.exit(1)

    role_reg = load_reg("role-registry")
    roles = list(role_reg.get("roles", {}).keys())

    if args.role:
        roles = [args.role]

    for role_name in roles:
        result = update_skill(role_name, dry_run=args.diff)
        print(result)

    if not args.diff:
        save_generation_hashes()
        print(f"\nRegistry hashes saved to registries/.last-generated.json")


if __name__ == "__main__":
    main()
