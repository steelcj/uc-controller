#!/usr/bin/env python3
"""Fail when converge code knows how a node is connected.

Converge playbooks and roles must not depend on where a node came from. The
onboard inventory's host-level connection contract decides how a node is
reached; converge only reads it. This check scans every text file under
converge/ and reports each line that references:

- ansible_connection
- the raw module (raw:, ansible.builtin.raw:, ansible.legacy.raw:)
- a source-specific connection plugin, such as community.general.incus or
  community.libvirt.libvirt

Comment lines are ignored.

It also checks the role directories. Repository roles used by one concern
live in that concern's roles/ directory, and roles used by both live in
shared/roles/. The check fails when a playbook in ingress/playbooks/ uses a
role from converge/roles/, or a playbook in converge/playbooks/ uses a role
from ingress/roles/. Role references are read from roles: lists and from
include_role / import_role tasks; a role name built from a variable, such as
"{{ specialize_role }}", cannot be checked and is skipped.

Exits 1 and lists file:line for each finding, or exits 0 when the tree is
clean. Runs on Linux, macOS, and Windows. Requires PyYAML, which is already
present wherever Ansible is installed.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent

# Connection plugins that reach a node through its source rather than SSH.
CONNECTION_PLUGINS = (
    "community.general.incus",
    "community.general.lxd",
    "community.general.lxc",
    "community.general.chroot",
    "community.general.jail",
    "community.general.zone",
    "community.general.qubes",
    "community.general.saltstack",
    "community.general.iocage",
    "community.general.funcd",
    "community.libvirt.libvirt",
    "community.libvirt.libvirt_lxc",
    "community.libvirt.libvirt_qemu",
    "community.docker.docker",
    "community.docker.docker_api",
    "community.docker.nsenter",
    "containers.podman.podman",
    "containers.podman.buildah",
    "community.okd.oc",
    "kubernetes.core.kubectl",
    "amazon.aws.aws_ssm",
    "community.aws.aws_ssm",
)

RULES = (
    ("ansible_connection", re.compile(r"\bansible_connection\b")),
    ("raw module", re.compile(r"^\s*(?:-\s+)?(?:ansible\.(?:builtin|legacy)\.)?raw\s*:")),
    ("connection plugin", re.compile(
        r"(?<![\w.])(?:" + "|".join(re.escape(name) for name in CONNECTION_PLUGINS) + r")(?![\w.])"
    )),
)


def scan(root: Path) -> list[str]:
    findings = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # binary or unreadable, not code
        for number, line in enumerate(text.splitlines(), start=1):
            if line.lstrip().startswith("#"):
                continue
            for label, pattern in RULES:
                if pattern.search(line):
                    try:
                        shown = path.relative_to(REPO)
                    except ValueError:
                        shown = path
                    findings.append(f"{shown.as_posix()}:{number}: {label}: {line.strip()}")
    return findings


ROLE_TASK_KEYS = {
    "include_role", "import_role",
    "ansible.builtin.include_role", "ansible.builtin.import_role",
    "ansible.legacy.include_role", "ansible.legacy.import_role",
}
TASK_LISTS = ("pre_tasks", "tasks", "post_tasks", "handlers", "block", "rescue", "always")


def role_names_in(roles_dir: Path) -> set[str]:
    if not roles_dir.is_dir():
        return set()
    return {p.name for p in roles_dir.iterdir() if p.is_dir()}


def roles_in_tasks(tasks) -> list[str]:
    names = []
    for task in tasks or []:
        if not isinstance(task, dict):
            continue
        for key in ROLE_TASK_KEYS:
            ref = task.get(key)
            if isinstance(ref, dict) and isinstance(ref.get("name"), str):
                names.append(ref["name"])
        for key in ("block", "rescue", "always"):
            names.extend(roles_in_tasks(task.get(key)))
    return names


def roles_in_playbook(path: Path) -> list[str]:
    """Role names a playbook uses through roles: lists and role tasks."""
    try:
        plays = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError, UnicodeDecodeError):
        return []
    names = []
    for play in plays if isinstance(plays, list) else []:
        if not isinstance(play, dict):
            continue
        for entry in play.get("roles") or []:
            if isinstance(entry, str):
                names.append(entry)
            elif isinstance(entry, dict):
                ref = entry.get("role", entry.get("name"))
                if isinstance(ref, str):
                    names.append(ref)
        for key in TASK_LISTS:
            names.extend(roles_in_tasks(play.get(key)))
    return [n for n in names if "{{" not in n]


def line_of(path: Path, name: str) -> int:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.lstrip().startswith("#") and re.search(rf"(?<![\w.]){re.escape(name)}(?![\w.])", line):
            return number
    return 0


def check_role_directories(repo: Path) -> list[str]:
    """Playbooks of one concern must not use roles from the other's roles/."""
    findings = []
    pairs = (("ingress", "converge"), ("converge", "ingress"))
    for concern, other in pairs:
        foreign = role_names_in(repo / other / "roles")
        for path in sorted((repo / concern / "playbooks").glob("*.y*ml")):
            for name in roles_in_playbook(path):
                if name in foreign:
                    shown = path.relative_to(repo).as_posix()
                    findings.append(
                        f"{shown}:{line_of(path, name)}: role from {other}/roles: {name} "
                        f"(move it to shared/roles if both concerns use it)"
                    )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", type=Path, default=REPO / "converge",
                        help="directory to check (default: converge/)")
    args = parser.parse_args()
    if not args.root.is_dir():
        print(f"error: {args.root} is not a directory", file=sys.stderr)
        return 2
    findings = scan(args.root) + check_role_directories(REPO)
    for finding in findings:
        print(finding)
    if findings:
        print(f"converge boundary check failed: {len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("converge boundary check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
