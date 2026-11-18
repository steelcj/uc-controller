#!/usr/bin/env python3
"""Vault password client for ansible-vault, and its one-time setup.

ansible.cfg names this script in vault_identity_list, once per vault ID.
Ansible treats a password file whose name ends in "-client" (before the
extension) as a client script: it runs it as

    scripts/vault-client.py --vault-id <id>

and reads the vault password from its standard output.

The password for each vault ID is read from a file outside the repository:

    ~/.config/uc-controller/vault/<id>

UC_VAULT_DIR, when set, replaces the directory. On Linux and macOS the file
must not be readable by the group or by others; the client refuses it if it
is. No vault password is ever read from a file inside the repository.

With no password file, the client prints a random placeholder and exits 0.
Ansible loads every vault ID at the start of every run, and a client that
fails stops the run, even one that decrypts nothing (onboarding an Incus
instance, say). With the placeholder those runs go ahead, and a run that does
need the vault fails with "Decryption failed (no vault secrets were found that
could decrypt)". new_raw_batch.py checks for the file itself and says what is
missing.

Setting up a vault ID, once per operator and workstation:

    python3 scripts/vault-client.py --init --vault-id raw_batch
        generates a new vault password into the file. Only for the first
        operator, before anything has been encrypted with that ID.

    python3 scripts/vault-client.py --set --vault-id raw_batch
        stores an existing vault password, read from standard input or a
        prompt, never from the command line. For every other operator.

Neither prints the password. Keep a copy of it in the password manager: an
encrypted file cannot be read without it.

Runs on Linux, macOS and Windows using only the standard library. Ansible
itself runs the client only on Linux and macOS.
"""
from __future__ import annotations

import argparse
import getpass
import os
import re
import secrets
import stat
import string
import sys
from pathlib import Path

# Vault IDs this repository uses. raw_batch: the passwords of raw node build
# batches. node: secrets of one managed node, reserved for onboarding.
VAULT_IDS = ("raw_batch", "node")
VAULT_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
GENERATED_LENGTH = 40
MIN_LENGTH = 20


def vault_dir() -> Path:
    override = os.environ.get("UC_VAULT_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".config" / "uc-controller" / "vault"


def password_file(vault_id: str) -> Path:
    if not VAULT_ID_RE.match(vault_id):
        raise SystemExit(f"error: {vault_id!r} is not a valid vault ID")
    return vault_dir() / vault_id


def check_private(path: Path) -> None:
    """Refuse a password file that others can read, where modes mean that."""
    if os.name != "posix":
        return
    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise SystemExit(
            f"error: {path} is readable by others (mode {stat.S_IMODE(mode):o}); "
            f"run: chmod 600 {path}"
        )


def read_password(vault_id: str) -> str | None:
    """The vault password for vault_id, or None when it is not set up."""
    path = password_file(vault_id)
    if not path.is_file():
        return None
    check_private(path)
    value = path.read_text(encoding="utf-8").strip()
    return value or None


def write_password(vault_id: str, value: str) -> Path:
    path = password_file(vault_id)
    if path.exists():
        raise SystemExit(f"error: {path} already exists; remove it first to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(path.parent, 0o700)
    # Created with mode 600 from the start, so it is never readable by others.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(value + "\n")
    return path


def prompt_password() -> str:
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\r\n")
    first = getpass.getpass("Vault password: ")
    if getpass.getpass("Again: ") != first:
        raise SystemExit("error: the two entries differ")
    return first


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vault password client for ansible-vault (see the module docstring)."
    )
    parser.add_argument("--vault-id", default="raw_batch",
                        help=f"vault ID; this repository uses {', '.join(VAULT_IDS)}")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--init", action="store_true",
                        help="generate a new vault password into the password file")
    action.add_argument("--set", action="store_true",
                        help="store an existing vault password, read from standard "
                             "input or a prompt")
    action.add_argument("--status", action="store_true",
                        help="say whether the password file exists; prints no secret")
    args = parser.parse_args()
    path = password_file(args.vault_id)

    if args.init:
        alphabet = string.ascii_letters + string.digits
        value = "".join(secrets.choice(alphabet) for _ in range(GENERATED_LENGTH))
        print(f"Wrote a new vault password for {args.vault_id} to {write_password(args.vault_id, value)}")
        print("Copy it into the password manager; it is not shown here.")
        return 0
    if args.set:
        value = prompt_password()
        if len(value) < MIN_LENGTH:
            raise SystemExit(f"error: a vault password has at least {MIN_LENGTH} characters")
        print(f"Stored the vault password for {args.vault_id} in {write_password(args.vault_id, value)}")
        return 0
    if args.status:
        if path.is_file():
            check_private(path)
            print(f"{args.vault_id}: set up ({path})")
            return 0
        print(f"{args.vault_id}: not set up; expected {path}")
        return 1

    value = read_password(args.vault_id)
    if value is None:
        print(f"uc-controller: no vault password for {args.vault_id} in {path}",
              file=sys.stderr)
        value = secrets.token_hex(32)
    print(value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
