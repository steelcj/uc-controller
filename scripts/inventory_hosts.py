"""Read every host from the static inventory files under inventories/.

Shared by new_raw_batch.py (which batches hosts still use) and
match_raw_identity.py (which hosts a raw node may already be). Read-only.

Covered: the raw source files that list hosts (admitted.yml,
discovered.yml, hand entries in hosts.yml), each stage's hosts.yml, and
every host_vars file. Not covered: dynamic plugin configs such as
inventories/raw/incus.yml, which list no hosts themselves, and group_vars.

Runs on Linux, macOS and Windows; requires PyYAML.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import yaml

REPO = Path(__file__).resolve().parent.parent
INVENTORIES = REPO / "inventories"


def hosts_in(data, host_vars_file: Path | None = None) -> Iterator[tuple[str, dict]]:
    """Yield (host, vars) for every host in an inventory file's data.

    For a host_vars file, the whole mapping is the vars of the host the file
    is named after.
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
                yield str(host), host_vars if isinstance(host_vars, dict) else {}
        yield from hosts_in(group.get("children"))


def inventory_hosts(inventories: Path = INVENTORIES) -> Iterator[tuple[Path, str, dict]]:
    """Yield (file, host, vars) for every host in every static inventory file."""
    for path in sorted(inventories.rglob("*.y*ml")):
        if "group_vars" in path.parts:
            continue
        try:
            with path.open(encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
        except (OSError, UnicodeDecodeError, yaml.YAMLError):
            continue
        host_vars_file = path if path.parent.name == "host_vars" else None
        for host, host_vars in hosts_in(data, host_vars_file):
            yield path, host, host_vars
