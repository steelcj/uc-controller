#!/usr/bin/env python3
"""Move a host entry between inventory stages.

Removes the host from whichever static inventory file in the source
inventory directory holds it (hosts.yml, discovered.yml, admitted.yml; dynamic
plugin configs are skipped), adds it to the destination stage's hosts.yml
under that stage's group, then commits the changed files to git.

Raw is what the sources report, and no script adds a host to any file under
inventories/raw/:
- Plugin-discovered hosts (Incus and similar) are in no static file. Promote
  one by passing --address; the destination entry is created and marked
  uc_origin: plugin.
- A host listed by hand in raw/hosts.yml is copied, not moved, and marked
  uc_origin: static. Scripts never write raw/hosts.yml.
- A scanned host is removed from raw/discovered.yml when promoted, and an
  admitted host from raw/admitted.yml, so it is not listed in two stages.
  These are the only cases where a script changes a raw file. An admitted
  host's keys stay in ssh/known_hosts.
- Between onboard and normalized, in either direction, the host keeps its
  connection settings and every group it was in other than the stage group.
- Demotion to raw removes the host's entry from the source stage and writes
  nothing. The node reappears in raw through its source: the plugin lists a
  running instance, a hand-entered host never left hosts.yml, a scanned
  host is found by the next scan, and an admitted host by the next run of
  05_admit.yml. Demotion is inventory bookkeeping that
  lets the inventory follow a node after a snapshot restore.

A host promoted into the onboard stage carries the connection contract at
host level, so it wins over the raw inventory's group variables whichever
order the inventories are loaded in. Runs on Linux, macOS, and Windows. Requires PyYAML,
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

# The group a host entry is written under in each stage's hosts.yml. Raw is
# absent: no script adds a host to raw.
STAGE_GROUP = {"onboard": "onboarded", "normalized": "normalized"}

# Header comments rewritten whenever the script rewrites these files.
HEADERS = {
    ("raw", "discovered.yml"):
        "# inventories/raw/discovered.yml\n#\n"
        "# Generated inventory, written by ingress/playbooks/00_discover.yml and\n"
        "# overwritten on every subnet scan. promote_node.py removes a host from it\n"
        "# when promoting that host. Not committed. Do not edit by hand.\n"
        "# Names are provisional (disc-<ip>) until onboarding.\n",
    # The same header ingress/playbooks/05_admit.yml writes.
    ("raw", "admitted.yml"):
        "# inventories/raw/admitted.yml\n#\n"
        "# Generated inventory, written only by ingress/playbooks/05_admit.yml,\n"
        "# which adds each raw node it admits and keeps the ones already here.\n"
        "# promote_node.py removes a host from it when promoting that host. Not\n"
        "# committed. Do not edit by hand. Connection settings come from\n"
        "# group_vars/admitted.yml; host keys are in ssh/known_hosts.\n",
}

# How an onboarded node is reached: SSH as the initial user, offering only
# the named key so agent keys cannot exhaust MaxAuthTries. ansible_host and
# ansible_ssh_private_key_file are filled in per host.
CONTRACT = {
    "ansible_connection": "ssh",
    "ansible_user": "initial",
    "ansible_ssh_common_args": "-o IdentitiesOnly=yes",
}
# Records where a promoted host came from, for the operator:
#   plugin: created from --address; a dynamic inventory plugin supplies it
#   static: listed by hand in raw/hosts.yml, which scripts never write
# A scanned or admitted host carries no marker; it came from
# raw/discovered.yml or raw/admitted.yml.
ORIGIN_KEY, ORIGIN_PLUGIN, ORIGIN_STATIC = "uc_origin", "plugin", "static"

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

    Return (file, its data with the host removed, host vars, the groups that
    listed it), or (None, None, None, []) when no static file holds it.
    """
    for path in static_files(inventory):
        data = load(path)
        groups = host_groups(data, host)
        found, host_vars = pop_host(data, host)
        if found:
            return path, data, host_vars, groups
    return None, None, None, []


def pop_host(groups: dict, host: str):
    """Remove host from every group in the tree. Return (found, its vars).

    The host's vars live under one group (normally the stage group); the other
    groups list it with no vars. Prefer the entry that carries vars.
    """
    found, host_vars = False, None
    for group in groups.values():
        if not isinstance(group, dict):
            continue
        hosts = group.get("hosts")
        if isinstance(hosts, dict) and host in hosts:
            removed = hosts.pop(host)
            if not found or (host_vars is None and removed is not None):
                found, host_vars = True, removed
        children = group.get("children")
        if isinstance(children, dict):
            child_found, child_vars = pop_host(children, host)
            if child_found and (not found or (host_vars is None and child_vars is not None)):
                found, host_vars = True, child_vars
    return found, host_vars


def host_groups(groups: dict, host: str) -> list[str]:
    """Names of every group in the tree that lists host, in file order."""
    names = []
    for name, group in groups.items():
        if not isinstance(group, dict):
            continue
        hosts = group.get("hosts")
        if isinstance(hosts, dict) and host in hosts:
            names.append(name)
        children = group.get("children")
        if isinstance(children, dict):
            names.extend(host_groups(children, host))
    return names


def add_host(data: dict, group: str, host: str, host_vars) -> None:
    section = data.get(group)
    if not isinstance(section, dict):
        section = data[group] = {}
    hosts = section.get("hosts")
    if not isinstance(hosts, dict):
        hosts = section["hosts"] = {}
    hosts[host] = host_vars


# Settings that make a host's SSH connection check host keys strictly. A
# host promoted out of raw keeps them when it already has them, from its own
# vars or from its source's group_vars (group_vars/admitted.yml sets them for
# every admitted raw contract node); the connection contract would otherwise
# replace ansible_ssh_common_args and drop them.
STRICT_KEYS = ("ansible_host_key_checking", "ansible_ssh_host_key_checking",
               "ansible_ssh_common_args")


def is_true(value) -> bool:
    return value is True or str(value).strip().lower() in ("true", "yes", "on", "1")


def vars_files(directory: Path, name: str) -> list[Path]:
    """<name>.yml or .yaml in directory, or every YAML file in <name>/."""
    files = [directory / f"{name}{suffix}" for suffix in (".yml", ".yaml")]
    folder = directory / name
    if folder.is_dir():
        files += sorted(p for p in folder.iterdir() if p.suffix in (".yml", ".yaml"))
    return [f for f in files if f.is_file()]


def strict_settings(inventory: Path, groups: list[str], host: str, host_vars) -> dict:
    """The host's strict host key settings, as Ansible would resolve them.

    Merges group_vars for all, raw and the groups that list the host, then
    host_vars/<host>, then the host's own entry. Returns {} unless host key
    checking is on.
    """
    merged: dict = {}
    # An ansible-vault encrypted file reads as a string, not a mapping, and is
    # skipped: host key settings are never secret.
    for path in [p for group in ["all", "raw", *groups]
                 for p in vars_files(inventory / "group_vars", group)] \
            + vars_files(inventory / "host_vars", host):
        data = load(path)
        if isinstance(data, dict):
            merged.update(data)
    merged.update(host_vars or {})
    if not any(is_true(merged.get(key)) for key in STRICT_KEYS[:2]):
        return {}
    strict = {key: merged[key] for key in STRICT_KEYS if key in merged}
    args = str(strict.get("ansible_ssh_common_args", ""))
    if "IdentitiesOnly=yes" not in args:
        args = f"{CONTRACT['ansible_ssh_common_args']} {args}".strip()
    strict["ansible_ssh_common_args"] = args
    return strict


def with_contract(host_vars, address: str | None, key_file: str | None,
                  host: str, strict: dict | None = None) -> dict:
    """Return host_vars with the onboard connection contract applied.

    strict, from strict_settings(), is applied over the contract, so a host
    that checked host keys strictly keeps doing so.
    """
    host_vars = dict(host_vars or {})
    address = address or host_vars.get("ansible_host")
    key_file = key_file or host_vars.get("ansible_ssh_private_key_file")
    if not address:
        raise SystemExit(f"error: no address for {host}; pass --address")
    if not key_file:
        raise SystemExit(f"error: no key file for {host}; pass --key-file")
    host_vars.update(CONTRACT)
    host_vars.update(strict or {})
    host_vars["ansible_host"] = address
    host_vars["ansible_ssh_private_key_file"] = key_file
    return host_vars




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

    source_file, source_data, host_vars, source_groups = find_host(args.source, args.host)
    found = source_file is not None
    if not found and (to_stage == "raw" or not args.address):
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

    if to_stage == "raw":
        # Raw is what the sources report. Remove the entry and write nothing;
        # the node reappears in raw through its source.
        dump(source_file, source_data, HEADERS.get((from_stage, source_file.name)))
        print(f"{direction.capitalize()}d {args.host}: removed from {source_file}; "
              f"nothing written to {args.dest}")
        if not args.no_commit:
            git_commit([source_file], f"{direction} {args.host}: {from_stage} -> {to_stage}")
        return 0

    dest_file = args.dest / "hosts.yml"
    # The connection contract is written once, on promotion out of raw. Moves
    # between onboard and normalized carry the entry over unchanged.
    if from_stage == "raw":
        strict = (strict_settings(args.source, source_groups, args.host, host_vars)
                  if found else {})
        host_vars = with_contract(host_vars, args.address, args.key_file, args.host, strict)
        if strict:
            print(f"note: {args.host} keeps its strict host key settings "
                  f"({', '.join(sorted(strict))})")

    # pop_host clears every existing entry for the host, so a repeat
    # promotion replaces the entry instead of adding a second one.
    dest_data = load(dest_file)
    pop_host(dest_data, args.host)
    add_host(dest_data, STAGE_GROUP[to_stage], args.host, host_vars)
    # Between onboard and normalized, in either direction, the host keeps
    # every group it was in other than the stage group itself (webservers and
    # the like). Raw's groups are source groups and do not carry over.
    extra = [] if from_stage == "raw" else [
        g for g in source_groups if g not in STAGE_GROUP.values()
    ]
    if args.group and args.group not in extra:
        extra.append(args.group)
    for group in extra:
        add_host(dest_data, group, args.host, None)

    written = [dest_file]
    if found and not read_only:
        dump(source_file, source_data, HEADERS.get((from_stage, source_file.name)))
        written.insert(0, source_file)
    elif not found:
        print(f"note: {args.host} was not in any static file in {args.source}; "
              "created from --address")
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
