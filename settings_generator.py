#!/usr/bin/env python3
"""settings_generator.py — Reads registries, produces .claude/settings.local.json for an agent role."""

import json
import os
import yaml
import sys

REGISTRY_DIR = os.path.join(os.path.dirname(__file__), "registries")
HOOKS_DIR = os.path.join(os.path.dirname(__file__), "hooks")


def load_registry(name: str) -> dict:
    path = os.path.join(REGISTRY_DIR, f"{name}.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


def resolve_hook_templates(template_names: list[str], hook_reg: dict) -> dict:
    """Merge hook templates into a single hooks config for settings.json."""
    merged: dict[str, list] = {}
    templates = hook_reg.get("templates", {})

    for tname_entry in template_names:
        tname = tname_entry.get("template") if isinstance(tname_entry, dict) else tname_entry
        template = templates.get(tname)
        if not template:
            print(f"WARNING: hook template '{tname}' not found in hook-registry.yaml", file=sys.stderr)
            continue

        for event_name, hook_list in template.get("hooks", {}).items():
            if event_name not in merged:
                merged[event_name] = []
            for hook in hook_list:
                hook_def = {}
                hook_def["type"] = hook.get("type", "command")
                # Resolve command path to absolute
                cmd = hook.get("command", "")
                if cmd and not cmd.startswith("/"):
                    cmd = os.path.join(HOOKS_DIR, os.path.basename(cmd))
                hook_def["command"] = cmd
                if "timeout" in hook:
                    hook_def["timeout"] = hook["timeout"]
                if hook.get("async"):
                    hook_def["async"] = True

                entry_wrapper = {"hooks": [hook_def]}
                if "matcher" in hook:
                    entry_wrapper["matcher"] = hook["matcher"]
                merged[event_name].append(entry_wrapper)

    return merged


def extract_gate_timeouts(role_type: str) -> dict[str, int]:
    """Extract tool timeouts from gate-registry for this role's accountable gates.

    Matches role gates (e.g. 'gate-1') against gate-registry keys by prefix
    (e.g. 'gate-1-deterministic') so short IDs in role-registry resolve correctly.
    """
    gate_reg = load_registry("gate-registry")
    role_reg = load_registry("role-registry")
    role = role_reg.get("roles", {}).get(role_type, {})
    role_gates = role.get("gates_accountable_for", [])

    timeouts = {}
    for gate_id, gate in gate_reg.get("gates", {}).items():
        # Match if any role gate is a prefix of the full gate-registry key
        matched = any(gate_id == rg or gate_id.startswith(rg) for rg in role_gates)
        if not matched:
            continue
        for tool in gate.get("tools", []):
            if "timeout" in tool:
                # Convert to env var name: pytest -> WARROOM_PYTEST_TIMEOUT
                env_name = f"WARROOM_{tool['id'].upper().replace('-', '_')}_TIMEOUT"
                timeouts[env_name] = tool["timeout"]
    return timeouts


def generate_settings(role_type: str) -> dict:
    """Generate .claude/settings.local.json content for a given role."""
    role_reg = load_registry("role-registry")
    hook_reg = load_registry("hook-registry")

    role = role_reg.get("roles", {}).get(role_type)
    if not role:
        raise ValueError(f"Role '{role_type}' not found in role-registry.yaml")

    hooks = resolve_hook_templates(role.get("hooks", []), hook_reg)

    settings = {"hooks": hooks}

    # Add permissions if role has tool restrictions
    permissions = {}
    allowed = role.get("allowed_tools", "*")
    if allowed != "*":
        permissions["allow"] = allowed
    disallowed = role.get("disallowed_tools", [])
    if disallowed:
        permissions["deny"] = disallowed
    if permissions:
        settings["permissions"] = permissions

    # Extract gate tool timeouts as env vars for hook scripts
    # Hook scripts read these instead of hardcoding (e.g., WARROOM_PYTEST_TIMEOUT=120)
    timeouts = extract_gate_timeouts(role_type)
    if timeouts:
        settings["env"] = timeouts

    return settings


def write_settings(role_type: str, working_dir: str) -> str:
    """Generate and write .claude/settings.local.json to the working directory."""
    settings = generate_settings(role_type)
    claude_dir = os.path.join(os.path.expanduser(working_dir), ".claude")
    os.makedirs(claude_dir, exist_ok=True)
    out_path = os.path.join(claude_dir, "settings.local.json")
    with open(out_path, "w") as f:
        json.dump(settings, f, indent=2)
    return out_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python settings_generator.py <role-type> [working-dir]")
        print("  role-type: supervisor, scout, engineer, qa, git-agent, chronicler")
        print("  working-dir: defaults to ~/contextualise")
        sys.exit(1)

    role = sys.argv[1]
    wdir = sys.argv[2] if len(sys.argv) > 2 else "~/contextualise"
    path = write_settings(role, wdir)
    print(f"Generated: {path}")
