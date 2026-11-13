#!/usr/bin/env python3
"""Clear node entries so the lifecycle can be rerun from scratch.

A development helper. Rewrites each onboard/<env> and normalized/<env>
hosts.yml back to an empty group, empties the generated raw inventory
(inventories/raw/discovered.yml) if it exists, and empties the Ansible fact
cache so a recreated node is not reached at a stale cached address.
inventories/raw/hosts.yml is hand-maintained and never touched. group_vars,
host_vars and plugin configs such as inventories/raw/incus.yml are left alone.

Nothing on the nodes themselves is touched; reset or delete those separately
(for Incus, restore the snapshot or delete the instance).

Runs on Linux, macOS, and Windows. Requires PyYAML, which is already present
wherever Ansible is installed.
"""
from __future__ import annotations

import argparse
import configparser
import shutil
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
INVENTORIES = REPO / "inventories"

# Stage directory -> (group its playbook targets, has per-environment dirs)
STAGES = {
    "onboard": ("onboarded", True),
    "normalized": ("normalized", True),
}

# Generated raw inventories, reset only if present: (file, group it holds).
# inventories/raw/hosts.yml is static and hand-maintained, so it is not here.
RAW_GENERATED = [("discovered.yml", "discovered")]


def hosts_files(envs: list[str] | None) -> list[tuple[Path, str, str]]:
    """Return (hosts.yml path, group, label) for every inventory to reset."""
    found = []
    for name, group in RAW_GENERATED:
        path = INVENTORIES / "raw" / name
        if path.exists():
            found.append((path, group, "raw"))
    for stage, (group, per_env) in STAGES.items():
        stage_dir = INVENTORIES / stage
        if not stage_dir.is_dir():
            continue
        if not per_env:
            found.append((stage_dir / "hosts.yml", group, stage))
            continue
        for env_dir in sorted(p for p in stage_dir.iterdir() if p.is_dir()):
            if envs and env_dir.name not in envs:
                continue
            found.append((env_dir / "hosts.yml", group, f"{stage}/{env_dir.name}"))
    return found


def host_names(hosts_file: Path) -> list[str]:
    """List every host named anywhere in an inventory file."""
    if not hosts_file.exists():
        return []
    with hosts_file.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    names: set[str] = set()

    def walk(groups) -> None:
        if not isinstance(groups, dict):
            return
        for group in groups.values():
            if not isinstance(group, dict):
                continue
            hosts = group.get("hosts")
            if isinstance(hosts, dict):
                names.update(hosts)
            walk(group.get("children"))

    walk(data)
    return sorted(names)


def fact_cache_dir() -> Path | None:
    """Return the jsonfile fact cache directory named in ansible.cfg, if any."""
    config = configparser.ConfigParser()
    config.read(REPO / "ansible.cfg", encoding="utf-8")
    if config.get("defaults", "fact_caching", fallback="") != "jsonfile":
        return None
    location = config.get("defaults", "fact_caching_connection", fallback="")
    if not location:
        return None
    path = Path(location).expanduser()
    return path if path.is_absolute() else REPO / path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clear node entries from the stage inventories and empty the fact cache."
    )
    parser.add_argument("--env", action="append", metavar="ENV",
                        help="only reset this environment (repeatable); default is all")
    parser.add_argument("--keep-raw", action="store_true",
                        help="leave the generated raw inventories as they are")
    parser.add_argument("--keep-facts", action="store_true",
                        help="leave the fact cache as it is")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="show what would be cleared without changing anything")
    args = parser.parse_args()

    verb = "Would clear" if args.dry_run else "Cleared"
    for hosts_file, group, label in hosts_files(args.env):
        if label == "raw" and args.keep_raw:
            continue
        names = host_names(hosts_file)
        if not args.dry_run:
            hosts_file.parent.mkdir(parents=True, exist_ok=True)
            with hosts_file.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    f"# {label} inventory. Reset by scripts/reset_inventories.py.\n"
                    f"{group}:\n  hosts: {{}}\n"
                )
        detail = ", ".join(names) if names else "already empty"
        shown = f"{label}/{hosts_file.name}" if label == "raw" else label
        print(f"{verb} {shown}: {detail}")

    if not args.keep_facts:
        cache = fact_cache_dir()
        if cache is None:
            print("Fact cache: none configured in ansible.cfg")
        elif not cache.is_dir():
            print(f"Fact cache: {cache} does not exist, nothing to clear")
        else:
            entries = [p for p in cache.iterdir() if p.is_file()]
            if not args.dry_run:
                for entry in entries:
                    entry.unlink()
            print(f"{verb} fact cache: {len(entries)} file(s) in {cache}")

    if not args.dry_run and shutil.which("git"):
        print("Inventory changes are left uncommitted; review with 'git status'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
