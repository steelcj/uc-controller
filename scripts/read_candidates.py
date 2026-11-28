#!/usr/bin/env python3
"""Read uc-node's candidates from a client inventory's candidates/.

    read_candidates.py --inventory <client inventory> --batch <batch> [--compact]

uc-node writes one candidate file per node it builds, candidates/<fqdn>.yml,
as the raw node handoff design in uc-contracts defines it:

    dev.example.org:
      address: "203.0.113.21"
      ssh_port: 22
      fingerprint: "SHA256:EXAMPLEexampleEXAMPLEexampleEXAMPLEexample0"
      raw_node_batch: "raw-1970-01-01-01"
      node_label: "dev"
      platform: "incus"
      producer: "uc-node"
      producer_version: "0.2.0"
      contract: "0.3.1"
      built: "2026-11-26T12:30:00-05:00"

Each file is read with PyYAML's BaseLoader, so every value is a string, as
the raw node contract asks of a confirmation's reader, and checked against
those fields before it is used: one top-level key, the node's fully
qualified domain name, which is also the file's name; every field present,
no other field, and each of its form. ssh_port is converted here.

Used by ingress/playbooks/05_admit.yml (admit_from_candidates=true), which
admits the candidates whose raw_node_batch is --batch, and by
check_inventory.py, which checks every candidate file before a commit.
Read-only: nothing under candidates/ is ever changed.

Prints one JSON document:

    {"candidates": [{"name", "address", "port", "fingerprint", "node_label",
                     "file"}],          the valid candidates of the batch
     "problems": ["candidates/<file>: ..."],   files that are not valid
     "other_batches": <n>}              valid candidates of other batches

Exit status 0 with a document, 2 on bad arguments. Runs on Linux, macOS and
Windows; requires PyYAML.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import yaml

# The candidate's fields, in the order uc-node writes them.
FIELDS = ("address", "ssh_port", "fingerprint", "raw_node_batch", "node_label", "platform",
          "producer", "producer_version", "contract", "built")

# uc-node's node labels, inventory/group_vars/all/labels.yml.
LABELS = ("raw", "dev", "stage", "prod")

# A DNS label, and a fully qualified domain name: a hostname label in front
# of a domain of at least two labels, at most 253 characters, by the rule
# uc-node's build.yml applies to client_domain. check_inventory.py and
# 05_admit.yml use the same rule.
LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
FQDN = re.compile(rf"^{LABEL}(?:\.{LABEL}){{2,}}$")
HOST = re.compile(rf"^{LABEL}(?:\.{LABEL})*$")
FINGERPRINT = re.compile(r"^SHA256:[A-Za-z0-9+/]{43}$")
# uc-node's raw_node_batch_pattern, inventory/group_vars/all/batches.yml.
BATCH = re.compile(r"^raw-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{2}$")
VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")


def is_fqdn(name: str) -> bool:
    return len(name) <= 253 and FQDN.match(name) is not None


def is_address(value: str) -> bool:
    """An IP address, or a host name to connect to."""
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return len(value) <= 253 and HOST.match(value) is not None


def is_timestamp(value: str) -> bool:
    """ISO 8601 with an offset, as uc-node writes built."""
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def field_problems(values: dict) -> list[str]:
    """What is wrong with a candidate's fields, if anything."""
    problems = []
    missing = [f for f in FIELDS if f not in values]
    extra = sorted(str(k) for k in values if k not in FIELDS)
    if missing:
        problems.append(f"lacks {', '.join(missing)}")
    if extra:
        problems.append(f"has fields the handoff design does not define: {', '.join(extra)}")
    checks = {
        "address": (is_address, "an IP address or host name"),
        "ssh_port": (lambda v: v.isdigit() and 1 <= int(v) <= 65535, "a port from 1 to 65535"),
        "fingerprint": (lambda v: FINGERPRINT.match(v) is not None,
                        "a SHA256 fingerprint as ssh-keygen -l prints it"),
        "raw_node_batch": (lambda v: BATCH.match(v) is not None, "a batch name, raw-YYYY-MM-DD-NN"),
        "node_label": (lambda v: v in LABELS, f"one of {', '.join(LABELS)}"),
        "platform": (lambda v: v != "", "not empty"),
        "producer": (lambda v: v != "", "not empty"),
        "producer_version": (lambda v: VERSION.match(v) is not None, "a version, such as 0.3.0"),
        "contract": (lambda v: VERSION.match(v) is not None, "a version, such as 0.3.1"),
        "built": (is_timestamp, "ISO 8601 with an offset"),
    }
    for field, (valid, form) in checks.items():
        if field not in values:
            continue
        value = values[field]
        if not isinstance(value, str):
            problems.append(f"{field} is not a single value")
        elif not valid(value):
            problems.append(f"{field} is {value!r}, not {form}")
    return problems


def read_candidate(path: Path) -> tuple[dict | None, list[str]]:
    """(the candidate, []) for a valid file, or (None, its problems)."""
    try:
        with path.open(encoding="utf-8") as handle:
            data = yaml.load(handle, Loader=yaml.BaseLoader)
    except (OSError, UnicodeDecodeError) as error:
        return None, [f"cannot be read: {error}"]
    except yaml.YAMLError as error:
        mark = getattr(error, "problem_mark", None)
        where = f" near line {mark.line + 1}" if mark is not None else ""
        return None, [f"is not valid YAML{where}"]
    if not isinstance(data, dict) or len(data) != 1:
        return None, ["must hold one node, keyed by its fully qualified domain name"]
    (name, values), = data.items()
    problems = []
    if not is_fqdn(name):
        problems.append(f"is keyed by {name!r}, not a fully qualified domain name")
    elif path.name != f"{name}.yml":
        problems.append(f"holds {name}, so it must be named {name}.yml")
    if not isinstance(values, dict):
        return None, problems + ["holds no fields"]
    problems += field_problems(values)
    if problems:
        return None, problems
    return {"name": name, "address": values["address"], "port": int(values["ssh_port"]),
            "fingerprint": values["fingerprint"], "raw_node_batch": values["raw_node_batch"],
            "node_label": values["node_label"]}, []


def candidate_files(root: Path) -> list[Path]:
    folder = root / "candidates"
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix in (".yml", ".yaml")) \
        if folder.is_dir() else []


def read(root: Path, batch: str) -> dict:
    chosen, problems, others, addresses = [], [], 0, {}
    for path in candidate_files(root):
        relative = path.relative_to(root).as_posix()
        candidate, found = read_candidate(path)
        if found:
            problems += [f"{relative}: {p}" for p in found]
            continue
        if candidate["raw_node_batch"] != batch:
            others += 1
            continue
        if candidate["address"] in addresses:
            problems.append(f"{relative}: has the address {candidate['address']}, as "
                            f"{addresses[candidate['address']]} does")
            continue
        addresses[candidate["address"]] = relative
        candidate["file"] = relative
        del candidate["raw_node_batch"]
        chosen.append(candidate)
    return {"candidates": chosen, "problems": problems, "other_batches": others}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read the candidates of one batch from a client inventory's candidates/, "
                    "and print them, and any file that is not a valid candidate, as JSON.")
    parser.add_argument("--inventory", required=True, type=Path, metavar="CLIENT",
                        help="the client inventory's root directory")
    parser.add_argument("--batch", required=True, help="the batch to admit, raw-YYYY-MM-DD-NN")
    parser.add_argument("--compact", action="store_true", help="print the JSON on one line")
    args = parser.parse_args()
    root = args.inventory.expanduser()
    if not root.is_dir():
        parser.error(f"{args.inventory} is not a directory")
    print(json.dumps(read(root.resolve(), args.batch), indent=None if args.compact else 2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
