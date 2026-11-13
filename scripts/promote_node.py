#!/usr/bin/env python3
"""Move a host entry between inventory stages.

Removes the host from whichever static inventory file in the source
inventory directory holds it (hosts.yml, discovered.yml, and so on; dynamic
plugin configs are skipped), adds it to the destination stage's file under
that stage's group, then commits the changed files to git.

Destinations: onboard and normalized use <env>/hosts.yml. Raw uses the
generated raw/discovered.yml under the discovered group, because
raw/hosts.yml is hand-maintained and no script writes to it.

Plugin-discovered hosts (Incus and similar) are in no static file. Promote
one by passing --address; the destination entry is then created rather than
moved, and marked uc_origin: plugin. A host listed by hand in raw/hosts.yml
is copied, not moved, and marked uc_origin: static.

A host promoted into the onboard stage carries the connection contract at
host level, so it wins over the raw inventory's group variables whichever
order the inventories are loaded in. On demotion to raw, a host marked
uc_origin: plugin or static is only removed, since raw still supplies it;
any other host moves to raw/discovered.yml with ansible_host kept and the
rest of the contract removed. Runs on Linux, macOS, and Windows. Requires PyYAML,
which is already present wherever Ansible is installed.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

# Lifecycle order.
STAGES = ["raw", "onboard", "normalized"]

# Where a host entry is written in each stage: (file, group). raw/hosts.yml
# is hand-maintained, so a host demoted to raw goes to the generated
# discovered.yml, the only raw source that holds static hosts.
DEST = {
    "raw": ("discovered.yml", "discovered"),
    "onboard": ("hosts.yml", "onboarded"),
    "normalized": ("hosts.yml", "normalized"),
}

# Header comments rewritten whenever the script writes these files.
HEADERS = {
    ("raw", "discovered.yml"):
        "# inventories/raw/discovered.yml\n#\n"
        "# Generated inventory, written by ingress/playbooks/00_discover.yml\n"
        "# (overwritten on every subnet scan) and by demote_node.py.\n"
        "# Names are provisional (disc-<ip>) until onboarding.\n",
}

# How an onboarded node is reached: SSH as the initial user, offering only
# the named key so agent keys cannot exhaust MaxAuthTries. ansible_host and
# ansible_ssh_private_key_file are filled in per host.
CONTRACT = {
    "ansible_connection": "ssh",
    "ansible_user": "initial",
    "ansible_ssh_common_args": "-o IdentitiesOnly=yes",
}
# Removed on demotion to raw. ansible_host is kept: for a static host it is
# still the raw address.
CONTRACT_STRIP = ("ansible_connection", "ansible_user",
                  "ansible_ssh_private_key_file", "ansible_ssh_common_args")

# Marks a host that raw keeps supplying after promotion, so demotion to raw
# removes it without writing it back:
#   plugin: created from --address; a dynamic inventory plugin supplies it
#   static: listed by hand in raw/hosts.yml, which scripts never write
ORIGIN_KEY, ORIGIN_PLUGIN, ORIGIN_STATIC = "uc_origin", "plugin", "static"
RAW_SUPPLIED = (ORIGIN_PLUGIN, ORIGIN_STATIC)

# Hand-maintained files that scripts read but never write.
READ_ONLY = {("raw", "hosts.yml")}


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


def dump(hosts_file: Path, data: dict, header: str | None = None) -> None:
    hosts_file.parent.mkdir(parents=True, exist_ok=True)
    with hosts_file.open("w", encoding="utf-8", newline="\n") as handle:
        if header:
            handle.write(header)
        yaml.safe_dump(data, handle, default_flow_style=False, sort_keys=False)


def static_files(inventory: Path) -> list[Path]:
    """Static YAML inventory files at the top of an inventory directory.

    hosts.yml comes first. Files that are dynamic plugin configs (a top-level
    plugin: key) and files that are not YAML mappings are skipped.
    """
    files = sorted(
        (p for p in inventory.iterdir()
         if p.is_file() and p.suffix in (".yml", ".yaml")),
        key=lambda p: (p.name != "hosts.yml", p.name),
    ) if inventory.is_dir() else []
    static = []
    for path in files:
        try:
            data = load(path)
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and "plugin" not in data:
            static.append(path)
    return static


def find_host(inventory: Path, host: str):
    """Pop host from the first static file holding it.

    Return (file, its data with the host removed, host vars), or
    (None, None, None) when no static file holds it.
    """
    for path in static_files(inventory):
        data = load(path)
        found, host_vars = pop_host(data, host)
        if found:
            return path, data, host_vars
    return None, None, None


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
    remaining = {k: v for k, v in host_vars.items() if k not in CONTRACT_STRIP}
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
                        help="management address; creates the entry when no static "
                             "file in the source holds the host (plugin-discovered hosts)")
    parser.add_argument("--key-file", metavar="PATH",
                        help="SSH private key path written as ansible_ssh_private_key_file "
                             "when the destination is the onboard stage")
    parser.add_argument("--no-commit", action="store_true", help="skip the git commit")
    args = parser.parse_args()

    from_stage, to_stage = stage_of(args.source), stage_of(args.dest)
    step = STAGES.index(to_stage) - STAGES.index(from_stage)
    if (direction == "promote" and step <= 0) or (direction == "demote" and step >= 0):
        raise SystemExit(f"error: cannot {direction} from {from_stage} to {to_stage}")

    dest_name, dest_group = DEST[to_stage]
    dest_file = args.dest / dest_name

    source_file, source_data, host_vars = find_host(args.source, args.host)
    found = source_file is not None
    if not found and not args.address:
        raise SystemExit(
            f"error: host {args.host} not found in any static inventory file in {args.source}"
        )

    read_only = found and (from_stage, source_file.name) in READ_ONLY
    if not found:
        host_vars = {ORIGIN_KEY: ORIGIN_PLUGIN}
    elif read_only:
        host_vars = dict(host_vars or {})
        host_vars[ORIGIN_KEY] = ORIGIN_STATIC
        print(f"note: {source_file} is hand-maintained; its entry for {args.host} is left in place")

    if to_stage == "raw" and isinstance(host_vars, dict) \
            and host_vars.get(ORIGIN_KEY) in RAW_SUPPLIED:
        # Raw still supplies this host, through its plugin or hosts.yml; a
        # second entry would only duplicate it. Remove it from the source and
        # write nothing to raw.
        dump(source_file, source_data, HEADERS.get((from_stage, source_file.name)))
        print(f"{direction.capitalize()}d {args.host}: removed from {args.source}; "
              f"{ORIGIN_KEY}: {host_vars[ORIGIN_KEY]}, so not written to {args.dest}")
        if not args.no_commit:
            git_commit([source_file], f"{direction} {args.host}: {from_stage} -> {to_stage}")
        return 0

    if to_stage == "onboard":
        host_vars = with_contract(host_vars, args.address, args.key_file, args.host)
    elif to_stage == "raw":
        # Back to raw: reached through the raw inventory again.
        host_vars = without_contract(host_vars)

    # pop_host clears every existing entry for the host, so a repeat
    # promotion replaces the entry instead of adding a second one.
    dest_data = load(dest_file)
    pop_host(dest_data, args.host)
    add_host(dest_data, dest_group, args.host, host_vars)
    if args.group:
        add_host(dest_data, args.group, args.host, None)

    written = [dest_file]
    if found and not read_only:
        dump(source_file, source_data, HEADERS.get((from_stage, source_file.name)))
        written.insert(0, source_file)
    elif not found:
        print(f"note: {args.host} was not in any static file in {args.source}; "
              "created from --address")
    dump(dest_file, dest_data, HEADERS.get((to_stage, dest_name)))
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
