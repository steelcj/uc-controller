#!/usr/bin/env python3
"""Move a host entry between inventory stages.

Removes the host from the source inventory's hosts.yml, adds it to the
destination inventory's hosts.yml under that stage's group, then commits
both files to git.

Plugin-discovered hosts (Incus and similar) are never written to a static
hosts.yml. Promote one by passing --address; the destination entry is then
created rather than moved.

A host promoted into the onboard stage carries the connection contract at
host level, so it wins over the raw inventory's group variables whichever
order the inventories are loaded in. A host demoted out of the onboard stage
has the contract removed. Runs on Linux, macOS, and Windows. Requires PyYAML,
which is already present wherever Ansible is installed.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

# Lifecycle order, and the group each stage's playbook targets.
STAGES = ["raw", "onboard", "normalized"]
STAGE_GROUP = {"raw": "raw", "onboard": "onboarded", "normalized": "normalized"}

# How an onboarded node is reached: SSH as the initial user. ansible_host and
# ansible_ssh_private_key_file are filled in per host.
CONTRACT = {"ansible_connection": "ssh", "ansible_user": "initial"}
CONTRACT_KEYS = ("ansible_host", "ansible_connection", "ansible_user",
                 "ansible_ssh_private_key_file")


def stage_of(inventory: Path) -> str:
    """Return the lifecycle stage an inventory directory belongs to."""
    parts = inventory.resolve().parts
    if "inventories" in parts:
        index = len(parts) - 1 - parts[::-1].index("inventories")
        if index + 1 < len(parts) and parts[index + 1] in STAGES:
            return parts[index + 1]
    raise SystemExit(
        f"error: {inventory} is not under inventories/<{'|'.join(STAGES)}>/"
    )


def load(hosts_file: Path) -> dict:
    if not hosts_file.exists():
        return {}
    with hosts_file.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def dump(hosts_file: Path, data: dict) -> None:
    hosts_file.parent.mkdir(parents=True, exist_ok=True)
    with hosts_file.open("w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(data, handle, default_flow_style=False, sort_keys=False)


def pop_host(groups: dict, host: str):
    """Remove host from every group in the tree. Return (found, its vars)."""
    found, host_vars = False, None
    for group in groups.values():
        if not isinstance(group, dict):
            continue
        hosts = group.get("hosts")
        if isinstance(hosts, dict) and host in hosts:
            removed = hosts.pop(host)
            if not found:
                found, host_vars = True, removed
        children = group.get("children")
        if isinstance(children, dict):
            child_found, child_vars = pop_host(children, host)
            if child_found and not found:
                found, host_vars = True, child_vars
    return found, host_vars


def add_host(data: dict, group: str, host: str, host_vars) -> None:
    section = data.get(group)
    if not isinstance(section, dict):
        section = data[group] = {}
    hosts = section.get("hosts")
    if not isinstance(hosts, dict):
        hosts = section["hosts"] = {}
    hosts[host] = host_vars


def with_contract(host_vars, address: str | None, key_file: str | None,
                  host: str) -> dict:
    """Return host_vars with the onboard connection contract applied."""
    host_vars = dict(host_vars or {})
    address = address or host_vars.get("ansible_host")
    key_file = key_file or host_vars.get("ansible_ssh_private_key_file")
    if not address:
        raise SystemExit(f"error: no address for {host}; pass --address")
    if not key_file:
        raise SystemExit(f"error: no key file for {host}; pass --key-file")
    host_vars.update(CONTRACT)
    host_vars["ansible_host"] = address
    host_vars["ansible_ssh_private_key_file"] = key_file
    return host_vars


def without_contract(host_vars):
    """Return host_vars with the onboard connection contract removed."""
    if not isinstance(host_vars, dict):
        return host_vars
    remaining = {k: v for k, v in host_vars.items() if k not in CONTRACT_KEYS}
    return remaining or None


def git_commit(files: list[Path], message: str) -> None:
    if shutil.which("git") is None:
        print("warning: git not found, changes left uncommitted", file=sys.stderr)
        return
    cwd = files[0].parent
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd, capture_output=True, text=True,
    )
    if top.returncode != 0:
        print("warning: not a git repository, changes left uncommitted", file=sys.stderr)
        return
    paths = [str(path.resolve()) for path in files]
    subprocess.run(["git", "add", "--", *paths], cwd=cwd, check=True)
    subprocess.run(["git", "commit", "-m", message, "--", *paths], cwd=cwd, check=True)


def main(direction: str = "promote") -> int:
    parser = argparse.ArgumentParser(
        description=f"{direction.capitalize()} a host between inventory stages."
    )
    parser.add_argument("--from", dest="source", required=True, type=Path,
                        metavar="INVENTORY", help="source inventory directory")
    parser.add_argument("--to", dest="dest", required=True, type=Path,
                        metavar="INVENTORY", help="destination inventory directory")
    parser.add_argument("--host", required=True, help="inventory hostname to move")
    parser.add_argument("--group", help="extra group to add the host to, e.g. webservers")
    parser.add_argument("--address", metavar="ADDRESS",
                        help="management address; creates the entry when the host is "
                             "not in the source hosts.yml (plugin-discovered hosts)")
    parser.add_argument("--key-file", metavar="PATH",
                        help="SSH private key path written as ansible_ssh_private_key_file "
                             "when the destination is the onboard stage")
    parser.add_argument("--no-commit", action="store_true", help="skip the git commit")
    args = parser.parse_args()

    from_stage, to_stage = stage_of(args.source), stage_of(args.dest)
    step = STAGES.index(to_stage) - STAGES.index(from_stage)
    if (direction == "promote" and step <= 0) or (direction == "demote" and step >= 0):
        raise SystemExit(f"error: cannot {direction} from {from_stage} to {to_stage}")

    source_file = args.source / "hosts.yml"
    dest_file = args.dest / "hosts.yml"

    source_data = load(source_file)
    found, host_vars = pop_host(source_data, args.host)
    if not found and not args.address:
        raise SystemExit(f"error: host {args.host} not found in {source_file}")

    if to_stage == "onboard":
        host_vars = with_contract(host_vars, args.address, args.key_file, args.host)
    elif STAGES.index(to_stage) < STAGES.index("onboard"):
        # Back before onboard: reached through the raw inventory again.
        host_vars = without_contract(host_vars)

    # pop_host clears every existing entry for the host, so a repeat
    # promotion replaces the entry instead of adding a second one.
    dest_data = load(dest_file)
    pop_host(dest_data, args.host)
    add_host(dest_data, STAGE_GROUP[to_stage], args.host, host_vars)
    if args.group:
        add_host(dest_data, args.group, args.host, None)

    written = [dest_file]
    if found:
        dump(source_file, source_data)
        written.insert(0, source_file)
    else:
        print(f"note: {args.host} was not in {source_file}; created from --address")
    dump(dest_file, dest_data)
    print(f"{direction.capitalize()}d {args.host}: {args.source} -> {args.dest}")

    if (args.source / "host_vars" / f"{args.host}.yml").exists():
        print(f"note: {args.source / 'host_vars'} still holds a file for {args.host}")

    if not args.no_commit:
        git_commit(
            written,
            f"{direction} {args.host}: {from_stage} -> {to_stage}",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main("promote"))
