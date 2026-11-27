#!/usr/bin/env python3
"""Refuse a client inventory that holds logic or secrets.

    scripts/check_inventory.py <client inventory>

A client inventory holds facts only. This script fails, listing every
problem it finds, when:

- a variable that only uc-controller's inventory-defaults/ may set (see
  FORBIDDEN_VARIABLES) is set anywhere under a group_vars/ or host_vars/
  directory, or on a group in a hosts file. Set per host, in the hosts files
  that admission, discovery and promote_node.py write, they are allowed;
- any file holds an ansible-vault header, a crypt hash ($6$, $y$, $2b$) or a
  private key block;
- a YAML file uses a lookup (lookup, query, q, or uc_secret) in a template;
- an admitted host in raw/admitted.yml has no raw_node_batch, or no entry in
  ssh/known_hosts under its inventory name;
- a host that came through admission is not named by a fully qualified
  domain name: every host in raw/admitted.yml, and every host in an
  onboard/<env>/ or normalized/<env>/ hosts.yml that carries raw_node_batch.
  Hosts from the Incus plugin or a subnet scan keep the names they arrive
  with, and are not checked.

The template's .githooks/pre-commit runs it before every commit. It checks
the working tree. Exit status 0 when the inventory is clean, 1 when it is
not, 2 on bad arguments. Requires PyYAML.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

# Variables that indicate logic leaked into a client inventory.
FORBIDDEN_VARIABLES = (
    "ansible_connection",
    "ansible_user",
    "ansible_ssh_common_args",
    "ansible_ssh_host_key_checking",
    "ansible_become_password",
)

VAULT_HEADER = re.compile(r"^\s*\$ANSIBLE_VAULT;", re.M)
CRYPT_HASH = re.compile(r"\$(?:6|y|2b)\$[./A-Za-z0-9$]{20,}")
PRIVATE_KEY = re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")
TEMPLATE = re.compile(r"\{\{.*?\}\}|\{%.*?%\}", re.S)
LOOKUP = re.compile(r"\b(?:lookup|query|q)\s*\(|\buc_secret\b")
YAML_SUFFIXES = (".yml", ".yaml")

# A fully qualified domain name, as 05_admit.yml names an admitted host: a
# hostname label in front of a domain, where the domain follows the rule
# uc-node's build.yml applies to client_domain: DNS labels of lowercase
# letters, digits and hyphens, at least two, at most 253 characters.
LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
FQDN = re.compile(rf"^{LABEL}(?:\.{LABEL}){{2,}}$")


def is_fqdn(name: str) -> bool:
    return len(name) <= 253 and FQDN.match(name) is not None


def files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*")
                  if p.is_file() and ".git" not in p.relative_to(root).parts)


def in_vars_dir(root: Path, path: Path) -> bool:
    parts = path.relative_to(root).parts
    return "group_vars" in parts or "host_vars" in parts


def groups_in(data) -> list[tuple[str, dict]]:
    """Every (group name, group mapping) in a hosts file, children included."""
    found = []
    if isinstance(data, dict):
        for name, group in data.items():
            if isinstance(group, dict):
                found.append((str(name), group))
                found.extend(groups_in(group.get("children")))
    return found


def known_host_names(known_hosts: Path) -> tuple[set[str], bool]:
    """Plain host names in a known hosts file, and whether any entry is hashed."""
    names, hashed = set(), False
    if not known_hosts.is_file():
        return names, hashed
    for line in known_hosts.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split()
        if not fields or fields[0].startswith("#"):
            continue
        if fields[0].startswith("@") and len(fields) > 1:
            fields = fields[1:]
        for name in fields[0].split(","):
            if name.startswith("|1|"):
                hashed = True
            else:
                names.add(re.sub(r"^\[(.*)\]:\d+$", r"\1", name))
    return names, hashed


def has_known_host(known_hosts: Path, host: str) -> bool:
    names, hashed = known_host_names(known_hosts)
    if host in names:
        return True
    if hashed and shutil.which("ssh-keygen"):
        result = subprocess.run(["ssh-keygen", "-F", host, "-f", str(known_hosts)],
                                capture_output=True, text=True)
        return result.returncode == 0 and bool(result.stdout.strip())
    return False


def check(root: Path) -> list[str]:
    problems: list[str] = []

    def problem(path: Path, message: str) -> None:
        problems.append(f"{path.relative_to(root)}: {message}")

    for path in files(root):
        text = path.read_text(encoding="utf-8", errors="replace")
        if VAULT_HEADER.search(text):
            problem(path, "holds an ansible-vault header; secrets belong in ~/.secrets/uc/fleet/")
        if CRYPT_HASH.search(text):
            problem(path, "holds a crypt hash; batch password hashes belong in ~/.secrets/uc/build/batches/")
        if PRIVATE_KEY.search(text):
            problem(path, "holds a private key block")
        if path.suffix not in YAML_SUFFIXES:
            continue
        if any(LOOKUP.search(block) for block in TEMPLATE.findall(text)):
            problem(path, "uses a lookup; secrets and logic belong in uc-controller")
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as error:
            mark = getattr(error, "problem_mark", None)
            where = f" near line {mark.line + 1}" if mark is not None else ""
            problem(path, f"is not valid YAML{where}")
            continue
        if in_vars_dir(root, path):
            if data is None:
                continue
            if not isinstance(data, dict):
                problem(path, "is not a mapping of variables")
                continue
            for name in FORBIDDEN_VARIABLES:
                if name in data:
                    problem(path, f"sets {name}, which only uc-controller's inventory-defaults/ may set")
        elif isinstance(data, dict) and "plugin" not in data:
            for group, body in groups_in(data):
                group_vars = body.get("vars")
                if isinstance(group_vars, dict):
                    for name in FORBIDDEN_VARIABLES:
                        if name in group_vars:
                            problem(path, f"sets {name} on group {group}; it may be set only per "
                                          "host, or by uc-controller's inventory-defaults/")

    admitted = root / "raw" / "admitted.yml"
    if admitted.is_file():
        try:
            data = yaml.safe_load(admitted.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            data = {}   # already reported above
        known_hosts = root / "ssh" / "known_hosts"
        for group, body in groups_in(data):
            hosts = body.get("hosts")
            if group != "admitted" or not isinstance(hosts, dict):
                continue
            for host, host_vars in hosts.items():
                batch = (host_vars or {}).get("raw_node_batch") if isinstance(host_vars, dict) else None
                if not isinstance(batch, str) or not batch.strip():
                    problem(admitted, f"admitted host {host} has no raw_node_batch")
                if not has_known_host(known_hosts, str(host)):
                    problem(admitted, f"admitted host {host} has no entry in ssh/known_hosts")
                if not is_fqdn(str(host)):
                    problem(admitted, f"admitted host {host} is not named by a fully qualified "
                                      "domain name, such as dev.example.org")

    # Promotion and demotion carry the admitted name unchanged, so a host
    # with raw_node_batch at a later stage keeps it too.
    for hosts_file in sorted([*root.glob("onboard/*/hosts.yml"), *root.glob("normalized/*/hosts.yml")]):
        try:
            data = yaml.safe_load(hosts_file.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue   # already reported above
        named = set()
        for _group, body in groups_in(data):
            hosts = body.get("hosts")
            if not isinstance(hosts, dict):
                continue
            for host, host_vars in hosts.items():
                if (isinstance(host_vars, dict) and "raw_node_batch" in host_vars
                        and not is_fqdn(str(host)) and host not in named):
                    named.add(host)
                    problem(hosts_file, f"host {host} came through admission, and is not named by "
                                        "a fully qualified domain name, such as dev.example.org")
    return problems


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] in ("-h", "--help"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    root = Path(argv[0]).expanduser()
    if not root.is_dir():
        print(f"check_inventory: {argv[0]} is not a directory", file=sys.stderr)
        return 2
    problems = check(root.resolve())
    for line in problems:
        print(f"check_inventory: {line}", file=sys.stderr)
    if problems:
        print(f"check_inventory: {len(problems)} problem(s); a client inventory holds facts only.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
