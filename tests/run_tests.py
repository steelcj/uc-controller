#!/usr/bin/env python3
"""Run every test in tests/. Standard library and PyYAML only.

    python3 tests/run_tests.py          from the repository root, or anywhere

Before the tests, every role requirements.yml pins is looked for on
ansible.cfg's roles_path. If one is missing, the script names it and, on a
terminal, asks the operator whether to install it now, into the roles_path
entry outside the repository (~/.ansible/roles):

    ansible-galaxy role install -r <the missing entries> -p ~/.ansible/roles

Never into roles/, which is for roles developed in uc-controller, and which
ansible-galaxy would pick by default, being first on roles_path. A role left
missing, declined or with no terminal to ask on, fails the run. So does a
role installed at another version than its pin, by its
meta/.galaxy_install_info: the script names it and the command that
reinstalls it, with --force, and changes nothing itself.

The tests that run Ansible need it on PATH or importable (the controller's
Ansible virtual environment). A test whose tool or role is missing is
skipped by unittest, but this script counts a skip as a failure: it lists
each skipped test with its reason and exits 1, so a run that left tests out
never reads as a pass. Each test makes its own secrets in a temporary
directory, never reading the operator's.

Exit status 0 when every role is installed at its pin and every test ran and passed.
"""
import configparser
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent


def roles_path() -> list[Path]:
    """ansible.cfg's roles_path, each entry absolute."""
    config = configparser.ConfigParser()
    config.read(REPO / "ansible.cfg")
    entries = []
    for entry in config.get("defaults", "roles_path", fallback="").split(":"):
        base = Path(os.path.expanduser(entry.strip()))
        entries.append(base if base.is_absolute() else REPO / base)
    return entries


def missing_roles() -> list[dict]:
    """The requirements.yml role entries found on no roles_path entry."""
    roles = yaml.safe_load((REPO / "requirements.yml").read_text())["roles"]
    paths = roles_path()
    return [r for r in roles
            if not any((p / r["name"] / "meta/main.yml").is_file() for p in paths)]


def misversioned_roles() -> list[tuple[str, str, str]]:
    """(name, pinned, installed) for each role found at another version than its pin."""
    roles = yaml.safe_load((REPO / "requirements.yml").read_text())["roles"]
    paths = roles_path()
    wrong = []
    for role in roles:
        found = next((p / role["name"] for p in paths if (p / role["name"] / "meta/main.yml").is_file()), None)
        if found is None:
            continue
        info = found / "meta/.galaxy_install_info"
        installed = str(yaml.safe_load(info.read_text()).get("version")) if info.is_file() else "unknown"
        if installed != str(role["version"]):
            wrong.append((role["name"], str(role["version"]), installed))
    return wrong


def install_path() -> Path:
    """The first roles_path entry outside the repository: ~/.ansible/roles."""
    return next(p for p in roles_path() if REPO not in p.parents and p != REPO)


def offer_install(missing: list[dict]) -> bool:
    """Ask the operator to install the missing roles. True when all are installed."""
    target = install_path()
    print("Roles requirements.yml pins and roles_path does not have:", file=sys.stderr)
    for role in missing:
        print(f"  {role['name']} {role.get('version', '')}", file=sys.stderr)
    command = f"ansible-galaxy role install -r requirements.yml -p {target}"
    if not shutil.which("ansible-galaxy"):
        print(f"ansible-galaxy is not on PATH. Install them with: {command}", file=sys.stderr)
        return False
    if not sys.stdin.isatty():
        print(f"No terminal to ask on. Install them with: {command}", file=sys.stderr)
        return False
    answer = input(f"Install them into {target} now? [y/N] ").strip().lower()
    if answer not in ("y", "yes"):
        print(f"Not installed. Install them with: {command}", file=sys.stderr)
        return False
    with tempfile.TemporaryDirectory() as tmp:
        wanted = Path(tmp) / "requirements.yml"
        wanted.write_text(yaml.safe_dump({"roles": missing}, sort_keys=False))
        done = subprocess.run(["ansible-galaxy", "role", "install", "-r", str(wanted), "-p", str(target)],
                              cwd=tmp)
    if done.returncode != 0:
        print(f"ansible-galaxy exited {done.returncode}.", file=sys.stderr)
        return False
    still = missing_roles()
    for role in still:
        print(f"  still missing: {role['name']}", file=sys.stderr)
    return not still


if __name__ == "__main__":
    missing = missing_roles()
    roles_ok = not missing or offer_install(missing)
    wrong = misversioned_roles()
    if wrong:
        roles_ok = False
        print("Roles installed at another version than requirements.yml pins:", file=sys.stderr)
        for name, pinned, installed in wrong:
            print(f"  {name}: pinned {pinned}, installed {installed}", file=sys.stderr)
        print(f"Reinstall them with: ansible-galaxy role install -r requirements.yml -p {install_path()} --force",
              file=sys.stderr)
    suite = unittest.defaultTestLoader.discover(str(HERE), top_level_dir=str(HERE))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    if result.skipped:
        print(f"\nFAILED: {len(result.skipped)} test(s) skipped, which this script counts as failures:",
              file=sys.stderr)
        for test, reason in result.skipped:
            print(f"  {test.id()}: {reason}", file=sys.stderr)
    if not roles_ok:
        print("\nFAILED: roles requirements.yml pins are not installed at their pins, as listed above.",
              file=sys.stderr)
    sys.exit(0 if result.wasSuccessful() and not result.skipped and roles_ok else 1)
