#!/usr/bin/env python3
"""Check a raw node's confirmation against the raw node contract.

Reads /var/lib/raw-node/confirmation.yml, as a file or on standard input,
checks it against raw node contract 0.3.x (uc-contracts,
en/docs/node-onboarding-pipeline/1-raw-node-egress/uc-raw-node-contract.md),
and prints one JSON document:

    {
      "result": "pass" | "fail" | "error",
      "contract_supported": ["0.3.0", "0.3.1"],
      "findings": [
        {"severity": "fail" | "warning" | "note",
         "clause": "RN-ACC-07", "field": "sudo_nopasswd", "message": "..."}
      ],
      "values": {...}
    }

"values" holds the confirmation normalized for the admission play: every
field the checker could read, with booleans and ssh_port converted, MAC
addresses in lower case, and the MACs and addresses gathered in "macs" and
"addresses". A field that could not be read is null.

Severities: "fail" breaks the contract and fails the check. "warning" is
reported and does not fail it. "note" is information, such as a field this
checker does not know, which a later minor contract version may add.

Exit status: 0 pass, 1 contract failure, 2 unreadable input (no file, not
UTF-8, not YAML).

The YAML is read with PyYAML's BaseLoader, so every scalar stays a string,
as the contract's "Value types" section requires of a consumer. With the
safe loader a MAC such as 52:54:00:12:34:56 or an all-digit machine_id
would be read as a (base 60) integer. Booleans and ssh_port are converted
here.

Runs on Linux, macOS and Windows; requires PyYAML, which is present
wherever Ansible is installed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import re
import sys
from pathlib import Path

import yaml

# Contract versions this checker implements. 0.3.1 changed wording only.
SUPPORTED_CONTRACTS = ("0.3.0", "0.3.1")

# Names a hostname must not have (RN-NET-01): installer and image defaults,
# and uc-ventoy's names before first boot appends the MAC suffix.
INSTALLER_DEFAULTS = {
    "localhost", "localhost.localdomain", "unassigned-hostname",
    "debian", "debian-server", "ubuntu", "ubuntu-server",
    "rocky", "rockylinux", "localhost-live", "fedora",
    "deb13-vt", "ub2404-vt", "ub2604-vt",
}

# The contract's confirmation fields, in its order, with the clause each
# one evidences. Shape failures are reported against RN-REP-01.
FIELDS = {
    "contract": "Versioning",
    "baseline": "RN-REP-01",
    "timestamp": "RN-REP-01",
    "machine_id": "RN-REP-01",
    "user": "RN-ACC-01",
    "sudo": "RN-ACC-04",
    "sudo_nopasswd": "RN-ACC-07",
    "ssh_port": "RN-SSH-01",
    "ssh_password_auth": "RN-SSH-03",
    "ssh_host_keys": "Host keys",
    "firewall": "Firewall manager",
    "firewall_active": "Firewall",
    "python": "RN-REP-01",
    "interfaces": "RN-SSH-02",
}
HOST_KEY_FIELDS = ("type", "fingerprint")
INTERFACE_FIELDS = ("name", "type", "mac", "state", "default_route4", "default_route6",
                    "ip", "ip6")

LABEL = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
HOSTNAME_RE = re.compile(rf"^{LABEL}(?:\.{LABEL})*$", re.IGNORECASE)
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
MACHINE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
MAC_RE = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$")
# A SHA256 fingerprint as ssh-keygen -l prints it: 32 bytes, base64, no padding.
FINGERPRINT_RE = re.compile(r"^SHA256:[A-Za-z0-9+/]{43}$")
KEY_TYPE_RE = re.compile(r"^[a-z0-9][a-z0-9@.-]*$")
PORT_RE = re.compile(r"^[0-9]{1,5}$")

# YAML 1.1 booleans, which is how Ansible and PyYAML's safe loader read them.
TRUE = {"y", "yes", "true", "on"}
FALSE = {"n", "no", "false", "off"}


class StringLoader(yaml.BaseLoader):
    """BaseLoader that also records duplicate mapping keys.

    A YAML loader keeps the last of two equal keys and says nothing. A
    confirmation with two entries for one field, or two hostnames, would
    then be read as something the node did not report.
    """

    def __init__(self, stream):
        super().__init__(stream)
        self.duplicates: list[str] = []

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = key_node.value if isinstance(key_node, yaml.ScalarNode) else None
            if key in seen:
                self.duplicates.append(key)
            seen.add(key)
        return super().construct_mapping(node, deep=deep)


class Unreadable(Exception):
    pass


def load(text: str):
    loader = StringLoader(text)
    try:
        data = loader.get_single_data()
    except yaml.YAMLError as exc:
        raise Unreadable(f"not valid YAML: {exc}") from None
    finally:
        loader.dispose()
    return data, loader.duplicates


class Checker:
    def __init__(self, user: str, port: int, installer_defaults: set[str]):
        self.user = user
        self.port = port
        self.installer_defaults = {name.lower() for name in installer_defaults}
        self.findings: list[dict] = []
        self.values: dict = {}

    def add(self, severity: str, clause: str, field: str, message: str) -> None:
        self.findings.append(
            {"severity": severity, "clause": clause, "field": field, "message": message}
        )

    def fail(self, clause: str, field: str, message: str) -> None:
        self.add("fail", clause, field, message)

    # --- shapes -------------------------------------------------------------

    def string(self, field: str, value, clause: str = "RN-REP-01", empty: bool = True):
        if not isinstance(value, str):
            self.fail(clause, field, f"must be a string, found {kind(value)}")
            return None
        if not empty and not value:
            self.fail(clause, field, "must not be empty")
            return None
        return value

    def boolean(self, field: str, value, clause: str = "RN-REP-01"):
        if isinstance(value, str):
            lowered = value.lower()
            if lowered in TRUE:
                return True
            if lowered in FALSE:
                return False
        self.fail(clause, field, f"must be true or false, found {kind(value)}")
        return None

    def string_list(self, field: str, value, clause: str = "RN-REP-01"):
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            self.fail(clause, field, f"must be a list of strings, found {kind(value)}")
            return None
        return value

    def unknown(self, field_prefix: str, mapping: dict, known) -> None:
        for name in mapping:
            if name not in known:
                self.add("note", "RN-REP-01", f"{field_prefix}{name}",
                         "not a field of the supported contract versions; ignored")

    # --- the confirmation ---------------------------------------------------

    def check(self, data, duplicates: list[str]) -> None:
        for key in sorted(set(duplicates)):
            self.fail("RN-REP-01", key or "(empty key)",
                      "appears more than once in one mapping; a reader keeps only the last")

        if not isinstance(data, dict):
            self.fail("RN-REP-01", "top-level key",
                      f"the confirmation must be a mapping keyed by the hostname, found {kind(data)}")
            return
        if len(data) != 1:
            self.fail("RN-REP-01", "top-level key",
                      f"must be exactly one, the hostname; found {len(data)}")
            return
        hostname, body = next(iter(data.items()))
        self.check_hostname(hostname)
        if not isinstance(body, dict):
            self.fail("RN-REP-01", hostname, f"must hold the fields as a mapping, found {kind(body)}")
            return

        for field in FIELDS:
            if field not in body:
                self.fail("RN-REP-01", field, "missing")
                self.values[field] = None
        self.unknown("", body, FIELDS)

        get = body.get
        if "contract" in body:
            self.values["contract"] = self.check_contract(get("contract"))
        if "baseline" in body:
            baseline = self.string("baseline", get("baseline"), empty=False)
            self.values["baseline"] = baseline
        if "timestamp" in body:
            self.values["timestamp"] = self.check_timestamp(get("timestamp"))
        if "machine_id" in body:
            self.values["machine_id"] = self.check_machine_id(get("machine_id"))
        if "user" in body:
            user = self.string("user", get("user"))
            if user is not None and user != self.user:
                self.fail("RN-ACC-01", "user",
                          f"is {user!r}; expected {self.user!r}" if user
                          else f"is empty: the account {self.user!r} does not exist")
            self.values["user"] = user
        self.expect_bool(body, "sudo", True, "RN-ACC-04",
                         "the initial user cannot use sudo")
        self.expect_bool(body, "sudo_nopasswd", False, "RN-ACC-07",
                         "a sudoers rule contains NOPASSWD or !authenticate")
        self.expect_bool(body, "ssh_password_auth", False, "RN-SSH-03",
                         "the SSH server accepts password or keyboard-interactive login")
        if "ssh_port" in body:
            self.values["ssh_port"] = self.check_port(get("ssh_port"))
        if "ssh_host_keys" in body:
            self.values["ssh_host_keys"] = self.check_host_keys(get("ssh_host_keys"))
        if "firewall" in body:
            self.values["firewall"] = self.string("firewall", get("firewall"))
        if "firewall_active" in body:
            active = self.boolean("firewall_active", get("firewall_active"))
            if active is False:
                self.add("warning", "Firewall", "firewall_active",
                         "the firewall manager is not running; the firewall clauses "
                         "RN-FW-01 to RN-FW-04 may not hold")
            self.values["firewall_active"] = active
        if "python" in body:
            self.values["python"] = self.string("python", get("python"))
        if "interfaces" in body:
            self.values["interfaces"] = self.check_interfaces(get("interfaces"))

        interfaces = self.values.get("interfaces") or []
        self.values["macs"] = sorted({i["mac"] for i in interfaces if i.get("mac")})
        self.values["addresses"] = {
            "ipv4": [a for i in interfaces for a in i.get("ip") or []],
            "ipv6": [a for i in interfaces for a in i.get("ip6") or []],
        }
        if self.values["interfaces"] is not None and not (
                self.values["addresses"]["ipv4"] or self.values["addresses"]["ipv6"]):
            self.fail("RN-SSH-02", "interfaces",
                      "no interface has an address, so SSH cannot be reachable on one")

    def check_hostname(self, hostname) -> None:
        self.values["hostname"] = None
        if not isinstance(hostname, str) or not hostname:
            self.fail("RN-NET-01", "top-level key", "the hostname is empty")
            return
        if len(hostname) > 253 or not HOSTNAME_RE.match(hostname):
            self.fail("RN-NET-01", "top-level key", f"{hostname!r} is not a valid hostname")
            return
        if hostname.lower() in self.installer_defaults:
            self.fail("RN-NET-01", "top-level key",
                      f"{hostname!r} is an installer or image default hostname")
            return
        self.values["hostname"] = hostname

    def check_contract(self, value):
        value = self.string("contract", value, clause="Versioning", empty=False)
        if value is None:
            return None
        if not VERSION_RE.match(value):
            self.fail("Versioning", "contract", f"{value!r} is not a version such as 0.3.0")
            return None
        if value not in SUPPORTED_CONTRACTS:
            self.fail("Versioning", "contract",
                      f"contract {value} is not supported; supported: "
                      f"{', '.join(SUPPORTED_CONTRACTS)}")
        return value

    def check_timestamp(self, value):
        value = self.string("timestamp", value, empty=False)
        if value is None:
            return None
        try:
            parsed = dt.datetime.fromisoformat(value)
        except ValueError:
            self.fail("RN-REP-01", "timestamp", f"{value!r} is not an ISO 8601 date and time")
            return None
        if parsed.tzinfo is None:
            self.fail("RN-REP-01", "timestamp", f"{value!r} has no UTC offset")
            return None
        return value

    def check_machine_id(self, value):
        value = self.string("machine_id", value, empty=False)
        if value is None:
            return None
        if not MACHINE_ID_RE.match(value):
            self.fail("RN-REP-01", "machine_id",
                      f"{value!r} is not 32 lower-case hexadecimal digits")
            return None
        return value

    def expect_bool(self, body: dict, field: str, expected: bool, clause: str,
                    message: str) -> None:
        if field not in body:
            return
        value = self.boolean(field, body[field], clause=clause)
        if value is not None and value is not expected:
            self.fail(clause, field, f"is {str(value).lower()}: {message}")
        self.values[field] = value

    def check_port(self, value):
        if not isinstance(value, str) or not PORT_RE.match(value) or not 1 <= int(value) <= 65535:
            self.fail("RN-SSH-01", "ssh_port", f"must be a port number, found {kind(value)}")
            return None
        port = int(value)
        if port != self.port:
            self.fail("RN-SSH-01", "ssh_port", f"is {port}; expected {self.port}")
        return port

    def check_host_keys(self, value):
        if not isinstance(value, list):
            self.fail("Host keys", "ssh_host_keys", f"must be a list, found {kind(value)}")
            return None
        keys = []
        for number, entry in enumerate(value):
            where = f"ssh_host_keys[{number}]"
            if not isinstance(entry, dict):
                self.fail("Host keys", where, f"must be a mapping, found {kind(entry)}")
                continue
            self.unknown(f"{where}.", entry, HOST_KEY_FIELDS)
            key_type, fingerprint = entry.get("type"), entry.get("fingerprint")
            good = True
            if not isinstance(key_type, str) or not KEY_TYPE_RE.match(key_type):
                self.fail("Host keys", f"{where}.type",
                          f"must be a key type such as ssh-ed25519, found {kind(key_type)}")
                good = False
            if not isinstance(fingerprint, str) or not FINGERPRINT_RE.match(fingerprint):
                self.fail("Host keys", f"{where}.fingerprint",
                          f"must be a SHA256 fingerprint as ssh-keygen -l prints it, "
                          f"found {kind(fingerprint)}")
                good = False
            if good:
                keys.append({"type": key_type, "fingerprint": fingerprint})
        if not keys:
            self.fail("Host keys", "ssh_host_keys",
                      "no usable host key, so the connection cannot be checked against it")
        return keys

    def check_interfaces(self, value):
        if not isinstance(value, list):
            self.fail("RN-REP-01", "interfaces", f"must be a list, found {kind(value)}")
            return None
        interfaces = []
        for number, entry in enumerate(value):
            where = f"interfaces[{number}]"
            if not isinstance(entry, dict):
                self.fail("RN-REP-01", where, f"must be a mapping, found {kind(entry)}")
                continue
            self.unknown(f"{where}.", entry, INTERFACE_FIELDS)
            for name in INTERFACE_FIELDS:
                if name not in entry:
                    self.fail("RN-REP-01", f"{where}.{name}", "missing")
            item = {
                "name": self.string(f"{where}.name", entry.get("name"), empty=False)
                if "name" in entry else None,
            }
            kind_ = entry.get("type")
            if "type" in entry and kind_ not in ("ethernet", "wireless", "other"):
                self.fail("RN-REP-01", f"{where}.type",
                          f"must be ethernet, wireless or other, found {kind(kind_)}")
                kind_ = None
            item["type"] = kind_ if "type" in entry else None
            mac = entry.get("mac")
            if "mac" in entry:
                if isinstance(mac, str) and MAC_RE.match(mac.lower()):
                    mac = mac.lower()
                else:
                    self.fail("RN-REP-01", f"{where}.mac",
                              f"must be a MAC address such as 52:54:00:12:34:56, found {kind(mac)}")
                    mac = None
            item["mac"] = mac
            state = entry.get("state")
            if "state" in entry and state not in ("up", "down"):
                self.fail("RN-REP-01", f"{where}.state", f"must be up or down, found {kind(state)}")
                state = None
            item["state"] = state if "state" in entry else None
            for name in ("default_route4", "default_route6"):
                item[name] = (self.boolean(f"{where}.{name}", entry[name])
                              if name in entry else None)
            item["ip"] = self.addresses(f"{where}.ip", entry, "ip", ipaddress.IPv4Address)
            item["ip6"] = self.addresses(f"{where}.ip6", entry, "ip6", ipaddress.IPv6Address)
            interfaces.append(item)
        return interfaces

    def addresses(self, where: str, entry: dict, name: str, kind_):
        if name not in entry:
            return []
        values = self.string_list(where, entry[name])
        if values is None:
            return []
        good = []
        for value in values:
            try:
                good.append(str(kind_(value)))
            except ValueError:
                self.fail("RN-REP-01", where,
                          f"{value!r} is not an {'IPv4' if name == 'ip' else 'IPv6'} address")
        return good


def kind(value) -> str:
    if isinstance(value, dict):
        return "a mapping"
    if isinstance(value, list):
        return "a list"
    if value is None:
        return "nothing"
    return f"{value!r}"


def run(text: str, user: str, port: int, installer_defaults: set[str]) -> tuple[int, dict]:
    checker = Checker(user, port, installer_defaults)
    try:
        data, duplicates = load(text)
    except Unreadable as exc:
        return 2, {"result": "error", "error": str(exc),
                   "contract_supported": list(SUPPORTED_CONTRACTS),
                   "findings": [], "values": {}}
    checker.check(data, duplicates)
    failed = any(f["severity"] == "fail" for f in checker.findings)
    return (1 if failed else 0), {
        "result": "fail" if failed else "pass",
        "contract_supported": list(SUPPORTED_CONTRACTS),
        "findings": checker.findings,
        "values": checker.values,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check a raw node confirmation against the raw node contract and "
                    "print the result as JSON. Exit 0 pass, 1 contract failure, "
                    "2 unreadable input."
    )
    parser.add_argument("file", nargs="?", default="-",
                        help="the confirmation file, or - for standard input (default)")
    parser.add_argument("--user", default="initial",
                        help="the expected initial_username (default initial)")
    parser.add_argument("--port", type=int, default=22,
                        help="the expected ssh_port (default 22)")
    parser.add_argument("--installer-default", action="append", default=[], metavar="NAME",
                        help="another hostname to refuse as a default (repeatable)")
    parser.add_argument("--compact", action="store_true", help="print the JSON on one line")
    args = parser.parse_args()

    try:
        if args.file == "-":
            raw = sys.stdin.buffer.read()
        else:
            raw = Path(args.file).read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        status, result = 2, {"result": "error", "error": f"cannot read {args.file}: {exc}",
                             "contract_supported": list(SUPPORTED_CONTRACTS),
                             "findings": [], "values": {}}
    else:
        status, result = run(text, args.user, args.port,
                             INSTALLER_DEFAULTS | set(args.installer_default))
    print(json.dumps(result, indent=None if args.compact else 2))
    return status


if __name__ == "__main__":
    sys.exit(main())
