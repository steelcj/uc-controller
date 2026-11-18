#!/usr/bin/env python3
"""Create and keep the passwords of raw node build batches.

A producer such as uc-ventoy builds raw nodes before their hostnames exist,
so every node of one build batch shares the password of the initial user
(raw node contract, shared parameter initial_password). The controller makes
that password, keeps it encrypted with ansible-vault under the vault ID
raw_batch, and gives the producer only its SHA-512 crypt hash.

Store layout, committed to git (see "Secrets" in the design document):

    secrets/raw-batches/index.yml          batch IDs, status, the current batch;
                                           holds no secret
    secrets/raw-batches/<batch-id>.vault   one batch password, encrypted

Usage:

    new_raw_batch.py
        Create a batch: generate a password of 24 letters and digits, store
        it under a new batch ID such as raw-2026-11-17-01, and make that batch
        current. Prints the batch ID and the hash, as lines to paste into
        uc-ventoy's raw-node-input.yml. The password is not printed.

    new_raw_batch.py --import raw-2026-11-17-manual [--current]
        Store a batch made before this script existed. The password is read
        from standard input or a prompt, never from the command line.

    new_raw_batch.py --set-current ID     make an existing batch current
    new_raw_batch.py --hash ID            print a fresh hash of a batch's password
    new_raw_batch.py --retire ID          delete a batch's password; refused
                                          while a host's raw_node_batch names it
    new_raw_batch.py --list               list batches and check the store

Earlier batches stay in the store until retired, so a node built before the
current batch can still be admitted. No plain password is ever written to a
file: ansible-vault reads it on standard input and writes only the
encrypted file.

Needs ansible-vault on PATH (the controller's Ansible virtual environment)
and the raw_batch vault password set up with scripts/vault-client.py. Runs
on Linux, macOS and Windows; requires PyYAML, which is present wherever
Ansible is installed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import getpass
import importlib.util
import os
import re
import secrets
import shutil
import string
import subprocess
import sys
from pathlib import Path

import yaml

from sha512_crypt import sha512_crypt

REPO = Path(__file__).resolve().parent.parent
DEFAULT_STORE = REPO / "secrets" / "raw-batches"
CLIENT = REPO / "scripts" / "vault-client.py"
VAULT_ID = "raw_batch"
VAULT_HEADER = f"$ANSIBLE_VAULT;1.2;AES256;{VAULT_ID}"

# raw-YYYY-MM-DD-NN for generated batches; any short lower-case suffix for an
# imported one, such as raw-2026-11-17-manual. A subset of what uc-ventoy
# accepts as password_batch.
BATCH_ID_RE = re.compile(r"^raw-(\d{4}-\d{2}-\d{2})-([a-z0-9][a-z0-9-]{0,39})$")

ALPHABET = string.ascii_letters + string.digits
GENERATED_MIN_LENGTH = 24   # what this script generates
MIN_LENGTH = 15             # raw node contract RN-ACC-08

INDEX_HEADER = (
    "# secrets/raw-batches/index.yml\n"
    "#\n"
    "# Written by scripts/new_raw_batch.py. Do not edit by hand.\n"
    "# Raw node build batches: which exist, which is current, which are retired.\n"
    "# Holds no secret. Each active batch's password is in <batch-id>.vault,\n"
    "# encrypted with ansible-vault under the vault ID raw_batch.\n"
)

INVENTORIES = REPO / "inventories"


# --- the store --------------------------------------------------------------

def now() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def check_batch_id(batch_id: str) -> str:
    match = BATCH_ID_RE.match(batch_id)
    if not match:
        raise SystemExit(
            f"error: {batch_id!r} is not a batch ID; expected raw-YYYY-MM-DD-<suffix>, "
            "such as raw-2026-11-17-01, with a suffix of lower-case letters, digits "
            "and hyphens"
        )
    try:
        dt.date.fromisoformat(match.group(1))
    except ValueError:
        raise SystemExit(f"error: {batch_id!r} does not contain a valid date") from None
    return batch_id


def load_index(store: Path) -> dict:
    path = store / "index.yml"
    data = {}
    if path.exists():
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    data.setdefault("current", None)
    if not isinstance(data.get("batches"), dict):
        data["batches"] = {}
    return data


def save_index(store: Path, index: dict) -> None:
    store.mkdir(parents=True, exist_ok=True)
    with (store / "index.yml").open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(INDEX_HEADER)
        yaml.safe_dump(index, handle, default_flow_style=False, sort_keys=False)


def shown(path: Path) -> Path:
    """path relative to the repository when it is inside it."""
    return path.relative_to(REPO) if path.is_relative_to(REPO) else path


def vault_file(store: Path, batch_id: str) -> Path:
    return store / f"{batch_id}.vault"


def next_batch_id(store: Path, index: dict) -> str:
    """raw-<today>-NN, with NN the first number not used before, retired or not."""
    today = dt.date.today().isoformat()
    for number in range(1, 100):
        candidate = f"raw-{today}-{number:02d}"
        if candidate not in index["batches"] and not vault_file(store, candidate).exists():
            return candidate
    raise SystemExit(f"error: no free batch number left for {today}")


# --- ansible-vault ----------------------------------------------------------

def load_client():
    spec = importlib.util.spec_from_file_location("vault_client", CLIENT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def require_vault_password() -> None:
    # Ansible runs a password file only when it is executable. Otherwise it
    # reads the file's text as the vault password, which here would be the
    # client's source code, committed in the repository. Refuse that case
    # (a checkout that lost the executable bit) before anything is encrypted.
    if os.name == "posix" and not os.access(CLIENT, os.X_OK):
        raise SystemExit(
            f"error: {shown(CLIENT)} is not executable, so ansible-vault would use its "
            f"text as the vault password. Run: chmod +x {shown(CLIENT)}"
        )
    client = load_client()
    if client.read_password(VAULT_ID) is None:
        raise SystemExit(
            f"error: no vault password for {VAULT_ID} at {client.password_file(VAULT_ID)}.\n"
            f"The first operator runs: python3 scripts/vault-client.py --init --vault-id {VAULT_ID}\n"
            f"Every other operator: python3 scripts/vault-client.py --set --vault-id {VAULT_ID}"
        )


def ansible_vault() -> str:
    found = shutil.which("ansible-vault")
    if found:
        return found
    beside = Path(sys.executable).parent / ("ansible-vault.exe" if os.name == "nt" else "ansible-vault")
    if beside.exists():
        return str(beside)
    raise SystemExit(
        "error: ansible-vault not found; activate the controller's Ansible virtual "
        "environment (see scripts/make_ansible_venv.py)"
    )


def run_vault(args: list[str], stdin: str | None = None) -> str:
    """Run ansible-vault with only the raw_batch identity, from the repository."""
    env = dict(os.environ)
    # Name the client by absolute path, so the run does not depend on the
    # directory this script is started from (ansible.cfg's entry is relative).
    env["ANSIBLE_VAULT_IDENTITY_LIST"] = f"{VAULT_ID}@{CLIENT}"
    result = subprocess.run(
        [ansible_vault(), *args], input=stdin, capture_output=True, text=True,
        cwd=REPO, env=env,
    )
    if result.returncode != 0:
        # ansible-vault's own messages never contain the plaintext.
        raise SystemExit(f"error: ansible-vault {args[0]} failed: {result.stderr.strip()}")
    return result.stdout


def encrypt(password: str, dest: Path) -> None:
    if dest.exists():
        raise SystemExit(f"error: {dest} already exists")
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_vault(["encrypt", "--encrypt-vault-id", VAULT_ID, "--output", str(dest), "-"],
              stdin=password)
    if decrypt(dest) != password:
        dest.unlink()
        raise SystemExit(f"error: {dest} did not decrypt to the password; removed it")


def decrypt(src: Path) -> str:
    return run_vault(["decrypt", "--output", "-", str(src)])


# --- passwords --------------------------------------------------------------

def generate_password(length: int) -> str:
    """Letters and digits, at least one of each."""
    while True:
        value = "".join(secrets.choice(ALPHABET) for _ in range(length))
        if any(c.isdigit() for c in value) and any(c.isalpha() for c in value):
            return value


def read_import_password() -> str:
    """Read the password of an existing batch. Letters and digits only.

    A password under MIN_LENGTH is accepted, because nodes may already be
    built with it, and the caller records meets_min_length: false.
    """
    if sys.stdin.isatty():
        value = getpass.getpass("Batch password: ")
        if getpass.getpass("Again: ") != value:
            raise SystemExit("error: the two entries differ")
    else:
        value = sys.stdin.readline().rstrip("\r\n")
    if not value or any(c not in ALPHABET for c in value):
        raise SystemExit("error: a batch password is made of letters and digits only")
    if len(value) < MIN_LENGTH:
        print(f"warning: the password has {len(value)} characters, under the "
              f"{MIN_LENGTH} that the raw node contract requires (RN-ACC-08). Stored, "
              "and recorded as meets_min_length: false; admission reports the clause "
              "as failed for every node of this batch.", file=sys.stderr)
    if not (any(c.isdigit() for c in value) and any(c.isalpha() for c in value)):
        print("warning: the password lacks either letters or digits; the privileged "
              "access policy (PA-PWD-01) asks for both. Stored anyway, because a "
              "node may already have been built with it.", file=sys.stderr)
    return value


def print_for_producer(batch_id: str, password: str) -> None:
    """The two lines uc-ventoy's raw-node-input.yml takes."""
    print(f'password_batch: "{batch_id}"')
    print(f'initial_password_hash: "{sha512_crypt(password)}"')


# --- actions ----------------------------------------------------------------

def create(store: Path, batch_id: str | None, length: int, show: bool) -> int:
    require_vault_password()
    index = load_index(store)
    batch_id = check_batch_id(batch_id) if batch_id else next_batch_id(store, index)
    if batch_id in index["batches"]:
        raise SystemExit(f"error: {batch_id} has been used before; batch IDs are never reused")
    password = generate_password(length)
    encrypt(password, vault_file(store, batch_id))
    index["batches"][batch_id] = {"created": now(), "origin": "generated",
                                  "status": "active", "meets_min_length": True}
    index["current"] = batch_id
    save_index(store, index)
    print_for_producer(batch_id, password)
    if show:
        print(f"Password of {batch_id}, shown once: {password}", file=sys.stderr)
    print(f"note: {batch_id} is now current; commit {shown(store)}", file=sys.stderr)
    return 0


def import_batch(store: Path, batch_id: str, make_current: bool) -> int:
    check_batch_id(batch_id)
    require_vault_password()
    index = load_index(store)
    if batch_id in index["batches"]:
        raise SystemExit(f"error: {batch_id} has been used before; batch IDs are never reused")
    password = read_import_password()
    encrypt(password, vault_file(store, batch_id))
    index["batches"][batch_id] = {"created": now(), "origin": "imported", "status": "active",
                                  "meets_min_length": len(password) >= MIN_LENGTH}
    if make_current:
        index["current"] = batch_id
    save_index(store, index)
    print_for_producer(batch_id, password)
    state = "now current" if make_current else f"not current; current is {index['current']}"
    print(f"note: imported {batch_id}, {state}; commit {shown(store)}", file=sys.stderr)
    return 0


def active(index: dict, batch_id: str) -> dict:
    check_batch_id(batch_id)
    entry = index["batches"].get(batch_id)
    if not entry:
        raise SystemExit(f"error: no batch {batch_id}")
    if entry.get("status") != "active":
        raise SystemExit(f"error: {batch_id} is {entry.get('status')}")
    return entry


def set_current(store: Path, batch_id: str) -> int:
    index = load_index(store)
    active(index, batch_id)
    index["current"] = batch_id
    save_index(store, index)
    print(f"{batch_id} is now current")
    return 0


def rehash(store: Path, batch_id: str) -> int:
    require_vault_password()
    active(load_index(store), batch_id)
    print_for_producer(batch_id, decrypt(vault_file(store, batch_id)))
    return 0


def hosts_in(data, host_vars_file: Path | None = None):
    """Yield (host, vars) for every host in an inventory file's data.

    For a host_vars file, the whole mapping is the vars of the host the
    file is named after.
    """
    if host_vars_file is not None:
        if isinstance(data, dict):
            yield host_vars_file.stem, data
        return
    if not isinstance(data, dict) or "plugin" in data:
        return  # a dynamic plugin config lists no hosts itself
    for group in data.values():
        if not isinstance(group, dict):
            continue
        hosts = group.get("hosts")
        if isinstance(hosts, dict):
            for host, host_vars in hosts.items():
                yield host, host_vars if isinstance(host_vars, dict) else {}
        yield from hosts_in(group.get("children"))


def hosts_using(batch_id: str) -> list[tuple[Path, str]]:
    """(file, host) for every host whose raw_node_batch is batch_id.

    Looks at every stage inventory: the raw source files, such as
    admitted.yml, each stage's hosts.yml, and every host_vars file.
    """
    found = []
    for path in sorted(INVENTORIES.rglob("*.y*ml")):
        if "group_vars" in path.parts:
            continue
        try:
            with path.open(encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            continue
        host_vars_file = path if path.parent.name == "host_vars" else None
        for host, host_vars in hosts_in(data, host_vars_file):
            if str(host_vars.get("raw_node_batch", "")) == batch_id:
                found.append((path, host))
    return found


def retire(store: Path, batch_id: str, force: bool) -> int:
    index = load_index(store)
    entry = active(index, batch_id)
    if index["current"] == batch_id:
        raise SystemExit(f"error: {batch_id} is current; make another batch current first")
    used = hosts_using(batch_id)
    if used and not force:
        listed = "\n  ".join(f"{host} in {shown(path)}" for path, host in used)
        raise SystemExit(
            f"error: these hosts have raw_node_batch: {batch_id}:\n  {listed}\n"
            "They may still need its password. Use --force to retire it anyway."
        )
    for path, host in used:
        print(f"warning: retiring {batch_id} although {host} in {shown(path)} names it",
              file=sys.stderr)
    vault_file(store, batch_id).unlink(missing_ok=True)
    entry["status"] = "retired"
    entry["retired"] = now()
    save_index(store, index)
    print(f"Retired {batch_id}: its encrypted password is deleted. "
          "git history still holds the encrypted file until it is rewritten.")
    return 0


def list_batches(store: Path) -> int:
    index = load_index(store)
    problems = []
    width = max((len(b) for b in index["batches"]), default=0)
    for batch_id, entry in index["batches"].items():
        mark = "*" if batch_id == index["current"] else " "
        short = "  under 15 characters (RN-ACC-08)" if entry.get("meets_min_length") is False else ""
        print(f"{mark} {batch_id:{width}}  {entry.get('status', '?'):8}  {entry.get('origin', '?'):9}  "
              f"{entry.get('created', '')}{short}")
        exists = vault_file(store, batch_id).exists()
        if entry.get("status") == "active" and not exists:
            problems.append(f"{batch_id} is active but has no {batch_id}.vault")
        if entry.get("status") == "retired" and exists:
            problems.append(f"{batch_id} is retired but {batch_id}.vault is still there")
    if index["current"] and index["current"] not in index["batches"]:
        problems.append(f"current batch {index['current']} is not in the index")
    if store.is_dir():
        for path in sorted(store.iterdir()):
            if path.name == "index.yml":
                continue
            if path.suffix != ".vault" or path.stem not in index["batches"]:
                problems.append(f"{path.name} is not a batch in the index")
            with path.open(encoding="utf-8", errors="replace") as handle:
                if handle.readline().strip() != VAULT_HEADER:
                    problems.append(f"{path.name} is NOT encrypted with the {VAULT_ID} vault ID")
    if not index["batches"]:
        print("no batches")
    for problem in problems:
        print(f"problem: {problem}", file=sys.stderr)
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create and keep raw node build batch passwords. With no action, "
                    "create a new batch and make it current."
    )
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--import", dest="import_id", metavar="ID",
                        help="store an existing batch's password, read from standard "
                             "input or a prompt")
    action.add_argument("--set-current", metavar="ID", help="make an active batch current")
    action.add_argument("--hash", dest="hash_id", metavar="ID",
                        help="print a new SHA-512 crypt hash of an active batch's password")
    action.add_argument("--retire", metavar="ID",
                        help="delete a batch's password; refused for the current batch "
                             "and, without --force, while any host in any stage inventory "
                             "has raw_node_batch equal to it")
    action.add_argument("--list", action="store_true", help="list batches and check the store")
    parser.add_argument("--batch-id", metavar="ID",
                        help="ID for a new batch (default raw-<today>-NN)")
    parser.add_argument("--length", type=int, default=GENERATED_MIN_LENGTH,
                        help=f"length of a new password (at least {GENERATED_MIN_LENGTH})")
    parser.add_argument("--current", action="store_true",
                        help="with --import: make the imported batch current")
    parser.add_argument("--force", action="store_true",
                        help="with --retire: retire the batch even though hosts still "
                             "have raw_node_batch equal to it")
    parser.add_argument("--show-password", action="store_true",
                        help="when creating a batch, also print its password once, on "
                             "standard error, for an operator who needs it at a console. "
                             "It is never shown again; keep it in the password manager.")
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE, help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.length < GENERATED_MIN_LENGTH:
        parser.error(f"--length must be at least {GENERATED_MIN_LENGTH}")
    creating = not (args.import_id or args.set_current or args.hash_id or args.retire or args.list)
    if (args.batch_id or args.show_password) and not creating:
        parser.error("--batch-id and --show-password apply only when creating a batch")
    if args.current and not args.import_id:
        parser.error("--current applies only with --import")
    if args.force and not args.retire:
        parser.error("--force applies only with --retire")

    store = args.store.resolve()
    if args.import_id:
        return import_batch(store, args.import_id, args.current)
    if args.set_current:
        return set_current(store, args.set_current)
    if args.hash_id:
        return rehash(store, args.hash_id)
    if args.retire:
        return retire(store, args.retire, args.force)
    if args.list:
        return list_batches(store)
    return create(store, args.batch_id, args.length, args.show_password)


if __name__ == "__main__":
    sys.exit(main())
