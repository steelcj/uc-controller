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

Comment lines are ignored. Exits 1 and lists file:line for each finding, or
exits 0 when the tree is clean. Runs on Linux, macOS, and Windows with the
standard library only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("root", nargs="?", type=Path, default=REPO / "converge",
                        help="directory to check (default: converge/)")
    args = parser.parse_args()
    if not args.root.is_dir():
        print(f"error: {args.root} is not a directory", file=sys.stderr)
        return 2
    findings = scan(args.root)
    for finding in findings:
        print(finding)
    if findings:
        print(f"converge boundary check failed: {len(findings)} finding(s)", file=sys.stderr)
        return 1
    print("converge boundary check passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
