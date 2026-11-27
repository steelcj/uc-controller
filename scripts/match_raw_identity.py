#!/usr/bin/env python3
"""Match a raw node's identity against every stage inventory.

Used by ingress/playbooks/05_admit.yml before it admits a node. Read-only.
Compares the name the node would be admitted under, its fully qualified
domain name, and its confirmed machine_id and MAC addresses (raw node
contract, "Identity") with every host in the static inventory files of the
client inventory given with --inventory (see inventory_hosts.py), and prints
one JSON document:

    {"decision": "new" | "known" | "reinstall" | "collision" | "conflict",
     "admit": true | false,
     "matches": [{"file": "...", "host": "...", "by": ["name", ...]}],
     "message": "..."}

Decisions, as the admission kickoff sets them:

    known      same name, same machine_id: already admitted; skip
    reinstall  same name, new machine_id, a known MAC: the node was
               reinstalled; stop, and say what to demote or remove first
    collision  same name, no identifier in common: another node has
               this name; stop
    conflict   a new name, but a known machine_id or MAC: the node is
               known under another name; stop (not in the kickoff's list,
               because it is not "new on every count")
    new        new on every count: admit

The name is compared whole, so dev.example.org and dev.example.net are two
names, and a node admitted earlier under its hostname alone, such as dev, is
another name too: its machine_id makes it a conflict.

machine_id and MACs are used to match nodes, never to trust them: anyone
with root on a node can change both.

Hosts supplied only by a dynamic plugin (raw/incus.yml) are not in any
file and are not compared.

Exit status 0 with a decision, 2 on bad arguments. Runs on Linux, macOS and
Windows; requires PyYAML.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from inventory_hosts import inventory_hosts


def removal_advice(path: Path, host: str, root: Path) -> str:
    """What to do with an existing entry before the node can be admitted."""
    keys = f"remove its keys with ssh-keygen -R {host} -f {root / 'ssh' / 'known_hosts'}"
    parts = path.relative_to(root).parts
    if parts[0] == "raw":
        return f"remove {host} from {path}, then {keys}"
    stage = "/".join(parts[:2])     # onboard/dev, normalized/stage, ...
    return (f"python3 scripts/demote_node.py --inventory {root} --from {stage} "
            f"--to raw --host {host}, then {keys}")


def match(name: str, machine_id: str, macs: list[str], root: Path) -> dict:
    macs = {mac.lower() for mac in macs}
    same_name, same_ids = [], []
    for path, host, host_vars in inventory_hosts(root):
        known_id = str(host_vars.get("raw_node_machine_id") or "")
        known_macs = {str(m).lower() for m in host_vars.get("raw_node_macs") or []}
        by = []
        if host == name:
            by.append("name")
        if known_id and known_id == machine_id:
            by.append("machine_id")
        if known_macs & macs:
            by.append("mac")
        if not by:
            continue
        entry = {"file": str(path.relative_to(root)), "host": host, "by": by, "path": path}
        (same_name if "name" in by else same_ids).append(entry)

    def result(decision: str, message: str, matches: list[dict]) -> dict:
        return {"decision": decision, "admit": decision == "new", "message": message,
                "matches": [{k: v for k, v in m.items() if k != "path"} for m in matches]}

    if same_name:
        if any("machine_id" in m["by"] for m in same_name):
            return result("known", f"{name} is already known with this machine_id; "
                                   "nothing to do", same_name)
        if any("mac" in m["by"] for m in same_name):
            advice = "; ".join(removal_advice(m["path"], m["host"], root) for m in same_name)
            return result("reinstall", f"{name} was reinstalled: new machine_id, known "
                                       f"MAC address. Before admitting it again: {advice}",
                          same_name)
        return result("collision", f"another node is already called {name} and shares "
                                   "no machine_id or MAC with this one; rename one of them",
                      same_name)
    if same_ids:
        names = ", ".join(f"{m['host']} ({' and '.join(m['by'])}, {m['file']})" for m in same_ids)
        return result("conflict", f"{name} is new, but its identity is known as: {names}. "
                                  "Resolve that entry first", same_ids)
    return result("new", f"{name} is new on every count", [])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Match a raw node's name, machine_id and MACs against every "
                    "stage of a client inventory, and print the decision as JSON."
    )
    parser.add_argument("--inventory", required=True, type=Path, metavar="CLIENT",
                        help="the client inventory's root directory")
    parser.add_argument("--name", required=True,
                        help="the fully qualified domain name the node would be admitted under")
    parser.add_argument("--machine-id", required=True)
    parser.add_argument("--mac", action="append", default=[], metavar="MAC")
    parser.add_argument("--compact", action="store_true", help="print the JSON on one line")
    args = parser.parse_args()
    root = args.inventory.expanduser()
    if not root.is_dir():
        parser.error(f"{args.inventory} is not a directory")
    outcome = match(args.name, args.machine_id, args.mac, root.resolve())
    print(json.dumps(outcome, indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
