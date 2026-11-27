"""End-to-end test of ingress/playbooks/05_admit.yml, offline.

Copies the parts of the repository the play uses into a temporary
directory, makes a client inventory there with scripts/new-inventory (raw
stage empty, so the first run admits into a client inventory with no raw
hosts yet), gives it a secrets root of its own (UC_SECRETS_DIR) holding
batch files of made-up test passwords, and puts stand-in ssh and
ssh-keyscan programs first on PATH. They play the part of nodes with real,
freshly generated host keys, so nothing on the network is contacted. The
stand-in ssh enforces host key checking as ssh does: with
StrictHostKeyChecking=yes it refuses a host whose key is not in the named
known hosts file, under HostKeyAlias when one is given.

Needs ansible-playbook on PATH (the controller's Ansible virtual
environment) and ssh-keygen; skipped otherwise. Linux and macOS.

    python3 tests/run_tests.py
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent

FAKE_SSH = r'''#!/usr/bin/env python3
"""Stand-in ssh. Nodes are described in $FAKE_NODES (JSON)."""
import json, os, subprocess, sys

VALUE_FLAGS = set("bcDEeFIiJLlmOoPpQRSWw")
args, opts, rest = sys.argv[1:], {}, []
i = 0
while i < len(args):
    a = args[i]
    if a.startswith("-") and len(a) == 2 and a[1] in VALUE_FLAGS:
        if a == "-o":
            k, _, v = args[i + 1].partition("=")
            opts.setdefault(k, v.strip('"'))
        else:
            opts.setdefault(a, args[i + 1])
        i += 2
    elif a.startswith("-") and not rest:
        i += 1
    else:
        rest.append(a)
        i += 1
host, command = rest[0], " ".join(rest[1:])
nodes = json.load(open(os.environ["FAKE_NODES"]))
node = nodes.get(host)
if node is None or not node.get("keys"):
    sys.stderr.write(f"ssh: connect to host {host} port 22: Connection refused\n"); sys.exit(255)

# Host key checking, as ssh does it.
if opts.get("StrictHostKeyChecking") == "yes":
    alias = opts.get("HostKeyAlias", host)
    known = opts.get("UserKnownHostsFile", "")
    lines = open(known).read().splitlines() if known and os.path.exists(known) else []
    entries = {" ".join(l.split()[1:3]) for l in lines if l and not l.startswith("#") and l.split()[0] == alias}
    presented = {" ".join(open(k).read().split()[:2]) for k in node["keys"]}
    if not entries or not entries <= presented:
        sys.stderr.write("Host key verification failed.\n"); sys.exit(255)

if node.get("refuse_key"):
    sys.stderr.write(f"initial@{host}: Permission denied (publickey).\n"); sys.exit(255)

if command == "cat /var/lib/raw-node/confirmation.yml":
    sys.stdout.write(open(node["confirmation"]).read()); sys.exit(0)

# Ansible's own connection.
if os.environ.get("FAKE_ANSIBLE") == "fail":
    sys.stderr.write("fake: connection refused for this test\n"); sys.exit(255)
if "BECOME-SUCCESS-" in command:
    token = command.split("BECOME-SUCCESS-")[1].split()[0].strip("'\";")
    print(f"BECOME-SUCCESS-{token}"); print("0"); sys.exit(0)
sys.exit(subprocess.run(["/bin/sh", "-c", command]).returncode)
'''

FAKE_KEYSCAN = r'''#!/usr/bin/env python3
"""Stand-in ssh-keyscan: prints the keys of the node in $FAKE_NODES."""
import json, os, sys
host = sys.argv[-1]
node = json.load(open(os.environ["FAKE_NODES"])).get(host) or {}
for key in node.get("keys", []):
    print(host, " ".join(open(key).read().split()[:2]))
'''

CONFIRMATION = """\
{hostname}:
  contract: "0.3.0"
  baseline: "0.4.0"
  timestamp: "2026-11-18T01:00:00-05:00"
  machine_id: "{machine_id}"
  user: "initial"
  sudo: true
  sudo_nopasswd: {sudo_nopasswd}
  ssh_port: 22
  ssh_password_auth: false
  ssh_host_keys:
{host_keys}
  firewall: "foomuuri"
  firewall_active: true
  python: "{python}"
  interfaces:
    - name: "enp1s0"
      type: "ethernet"
      mac: "{mac}"
      state: "up"
      default_route4: true
      default_route6: false
      ip: ["{address}"]
      ip6: []
"""

# The domain the stand-in nodes are admitted in, unless a test says otherwise.
DOMAIN = "example.org"


def machine_id(number: int) -> str:
    """The register's machine ID for host number."""
    return f"19700101{'0' * 20}ab{number:02d}"


def mac(number: int) -> str:
    """The register's MAC address for host number."""
    return f"02:00:00:ab:00:{number:02d}"


COPY = ["ansible.cfg", "scripts", "shared", "ingress/playbooks/05_admit.yml", "ingress/playbooks/tasks",
        "inventory-defaults", "inventory-template"]


@unittest.skipUnless(shutil.which("ansible-playbook") and shutil.which("ssh-keygen"),
                     "Ansible or ssh-keygen not on PATH")
@unittest.skipUnless(os.name == "posix", "Ansible runs on Linux and macOS")
class AdmitPlaybook(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cls.repo = root / "repo"
        for item in COPY:
            source, dest = REPO / item, cls.repo / item
            dest.parent.mkdir(parents=True, exist_ok=True)
            (shutil.copytree if source.is_dir() else shutil.copy2)(source, dest)
        cls.client = root / "example.org"
        subprocess.run([sys.executable, str(cls.repo / "scripts/new-inventory"), str(cls.client)],
                       check=True, capture_output=True)
        (cls.client / "raw/incus.yml").unlink()
        cls.bin = root / "bin"
        cls.bin.mkdir()
        for name, body in (("ssh", FAKE_SSH), ("ssh-keyscan", FAKE_KEYSCAN)):
            path = cls.bin / name
            path.write_text(body)
            path.chmod(path.stat().st_mode | stat.S_IXUSR)
        cls.client_key = root / "client_key"
        cls.client_key.write_text("not used by the stand-in ssh\n")
        # A secrets root of the test's own, named through UC_SECRETS_DIR, so
        # the operator's ~/.secrets/uc is never read. Modes as uc_secret
        # requires them. The passwords are made up for this test.
        secrets = root / "secrets"
        (secrets / "batches").mkdir(parents=True)
        secrets.chmod(0o700)
        (secrets / "batches").chmod(0o700)
        # raw-1970-01-01-02 has a password under 15 characters, for RN-ACC-08.
        cls.batch = "raw-1970-01-01-01"
        for batch, password in ((cls.batch, "tannery unbiased pebble canopy mullets gutter 4"),
                                ("raw-1970-01-01-02", "abc123")):
            path = secrets / "batches" / f"{batch}.yml"
            path.write_text(yaml.safe_dump({"initial_password": password}))
            path.chmod(0o600)
        cls.env = dict(os.environ, UC_SECRETS_DIR=str(secrets),
                       PATH=f"{cls.bin}{os.pathsep}{os.environ['PATH']}",
                       FAKE_NODES=str(root / "nodes.json"), ANSIBLE_NOCOLOR="1")
        cls.env.pop("ANSIBLE_CONFIG", None)
        cls.raw_onboard = cls.inventory_args("raw", "onboard/dev")

        cls.root = root
        cls.nodes = {}
        cls.add_node("203.0.113.10", "deb13-vt-0001", 1, python="/usr/bin/python3")
        cls.nodes["203.0.113.11"] = cls.nodes["203.0.113.10"]   # the same node, a second address
        cls.add_node("203.0.113.20", "deb13-vt-0002", 2, refuse_key=True)
        cls.add_node("203.0.113.30", "deb13-vt-0003", 3, sudo_nopasswd="true")
        cls.add_node("203.0.113.40", "deb13-vt-0004", 4, wrong_fingerprint=True)
        cls.add_node("203.0.113.50", "deb13-vt-0005", 5, python="")
        cls.nodes["203.0.113.99"] = {}   # no SSH
        cls.save_nodes()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    @classmethod
    def run_cmd(cls, argv, check=True, extra_env=None, stdin=None):
        env = dict(cls.env, **(extra_env or {}))
        result = subprocess.run(argv, cwd=cls.repo, env=env, capture_output=True, text=True,
                                input=stdin)
        if check and result.returncode != 0:
            raise AssertionError(f"{argv} failed:\n{result.stdout}\n{result.stderr}")
        return result

    @classmethod
    def inventory_args(cls, *stages) -> list[str]:
        result = subprocess.run([sys.executable, str(cls.repo / "scripts/inventory-args"),
                                 str(cls.client), *stages], capture_output=True, text=True, check=True)
        return result.stdout.split()

    @classmethod
    def add_node(cls, address, hostname, number, python="/usr/bin/python3",
                 refuse_key=False, sudo_nopasswd="false", wrong_fingerprint=False):
        """A stand-in node. Its machine ID and MAC address are the register's
        for host number, 19700101...ab<number> and 02:00:00:ab:00:<number>."""
        keys, entries = [], []
        for kind in ("ed25519", "ecdsa"):
            path = cls.root / f"{hostname}_{address}_{kind}"
            subprocess.run(["ssh-keygen", "-q", "-t", kind, "-N", "", "-f", str(path)], check=True)
            pub = Path(f"{path}.pub")
            keys.append(str(pub))
            line = subprocess.run(["ssh-keygen", "-l", "-E", "sha256", "-f", str(pub)],
                                  capture_output=True, text=True, check=True).stdout.split()
            fingerprint = line[1]
            if wrong_fingerprint and kind == "ecdsa":
                fingerprint = "SHA256:" + "A" * 43
            key_type = pub.read_text().split()[0]
            entries.append(f'    - type: "{key_type}"\n      fingerprint: "{fingerprint}"')
        confirmation = cls.root / f"{hostname}_{address}.yml"
        confirmation.write_text(CONFIRMATION.format(
            hostname=hostname, machine_id=machine_id(number), sudo_nopasswd=sudo_nopasswd,
            host_keys="\n".join(entries), python=python, mac=mac(number), address=address))
        cls.nodes[address] = {"keys": keys, "confirmation": str(confirmation),
                              "refuse_key": refuse_key}

    @classmethod
    def save_nodes(cls):
        Path(cls.env["FAKE_NODES"]).write_text(json.dumps(cls.nodes))

    def admit(self, *extra, extra_env=None):
        result = self.run_cmd(
            ["ansible-playbook", *self.raw_onboard, "ingress/playbooks/05_admit.yml",
             "-e", f"onboard_ssh_private_key_file={self.client_key}",
             "-e", f"admit_batch_id={self.batch}", *self.domain(extra), *extra],
            check=False, extra_env=extra_env)
        # The YAML callback wraps long report lines; compare on single spaces.
        result.stdout = " ".join(result.stdout.split())
        return result

    @staticmethod
    def domain(extra) -> list[str]:
        """-e admit_client_domain=example.org, unless the test gives its own."""
        given = any(str(arg).startswith("admit_client_domain=") for arg in extra)
        return [] if given else ["-e", f"admit_client_domain={DOMAIN}"]

    def admitted(self) -> dict:
        path = self.client / "raw/admitted.yml"
        if not path.exists():
            return {}
        return (yaml.safe_load(path.read_text())["admitted"] or {}).get("hosts") or {}

    def known_hosts(self) -> str:
        return (self.client / "ssh/known_hosts").read_text()

    def check_inventory(self):
        result = self.run_cmd([sys.executable, "scripts/check_inventory.py", str(self.client)],
                              check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_0_refused_without_a_client_inventory(self):
        result = self.run_cmd(["ansible-playbook", "ingress/playbooks/05_admit.yml",
                               "-e", f"admit_batch_id={self.batch}",
                               "-e", "admit_addresses=203.0.113.10"], check=False)
        out = " ".join(result.stdout.split())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No client inventory is loaded", out)
        self.assertIn("scripts/inventory-args", out)
        self.assertNotIn("fetch the SSH host keys", out)

    def test_1_admission_outcomes(self):
        result = self.admit("-e", "admit_addresses=203.0.113.10,203.0.113.11,203.0.113.20,"
                                  "203.0.113.30,203.0.113.40,203.0.113.99")
        out = result.stdout
        # .30 and .40 are refused, so the run exits 2, after the report.
        self.assertEqual(result.returncode, 2, out[-3000:])
        self.assertIn("Refused or stopped: 203.0.113.30 refused, 203.0.113.40 refused", out)
        self.assertLess(out.index("Report every candidate"), out.index("Refused or stopped"))
        self.assertIn("203.0.113.10: admitted deb13-vt-0001.example.org", out)
        self.assertIn("PA-HOST-01 host key trusted on first use", out)
        self.assertIn("203.0.113.11: known deb13-vt-0001.example.org", out)
        self.assertIn("203.0.113.20: not-contract", out)
        self.assertIn("Permission denied (publickey)", out)
        self.assertIn("203.0.113.30: refused deb13-vt-0003.example.org - RN-ACC-07 sudo_nopasswd", out)
        self.assertIn("203.0.113.40: refused deb13-vt-0004.example.org - host keys differ", out)
        self.assertIn("203.0.113.99: not-contract - no SSH server answered", out)

        hosts = self.admitted()
        self.assertEqual(list(hosts), ["deb13-vt-0001.example.org"])
        entry = hosts["deb13-vt-0001.example.org"]
        self.assertEqual(entry["ansible_host"], "203.0.113.10")
        self.assertEqual(entry["ansible_port"], 22)
        self.assertEqual(entry["raw_node_contract"], "0.3.0")
        self.assertEqual(entry["raw_node_baseline"], "0.4.0")
        self.assertEqual(entry["raw_node_machine_id"], machine_id(1))
        self.assertEqual(entry["raw_node_macs"], [mac(1)])
        self.assertEqual(entry["raw_node_batch"], self.batch)
        self.assertRegex(str(entry["raw_node_admitted"]), r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d[+-]\d\d:\d\d$")
        known = self.known_hosts()
        self.assertIn("# BEGIN deb13-vt-0001.example.org, admitted by 05_admit.yml", known)
        self.assertEqual(sum(1 for l in known.splitlines() if l.startswith("deb13-vt-0001.example.org ")), 2)
        # The file starts with the template's own header, and the client
        # inventory passes its checks with the admitted host in it.
        template = (REPO / "inventory-template/raw/admitted.yml").read_text().split("admitted:\n")[0]
        self.assertTrue((self.client / "raw/admitted.yml").read_text().startswith(template))
        self.check_inventory()

        # 2. Again: known, nothing changes.
        before = (self.admitted(), self.known_hosts())
        again = self.admit("-e", "admit_addresses=203.0.113.10")
        self.assertEqual(again.returncode, 0, again.stdout[-2000:])
        self.assertIn("203.0.113.10: known deb13-vt-0001.example.org - deb13-vt-0001.example.org is already known", again.stdout)
        self.assertNotIn("PA-HOST-01", again.stdout)   # first use is warned of only on admission
        self.assertEqual((self.admitted(), self.known_hosts()), before)

        # 3. The strict connection refuses a changed host key, and accepts it restored.
        path = self.client / "ssh/known_hosts"
        original = path.read_text()
        line = next(l for l in original.splitlines() if l.startswith("deb13-vt-0001.example.org ssh-ed25519 "))
        key = line.split()[2]
        changed = key[:-6] + ("A" if key[-6] != "A" else "B") + key[-5:]
        path.write_text(original.replace(key, changed))
        ping = ["ansible", *self.raw_onboard, "deb13-vt-0001.example.org",
                "-m", "ansible.builtin.raw", "-a", "true",
                "-e", f"onboard_ssh_private_key_file={self.client_key}"]
        refused = self.run_cmd(ping, check=False)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("Host key verification failed", refused.stdout + refused.stderr)
        path.write_text(original)
        self.assertEqual(self.run_cmd(ping, check=False).returncode, 0)

    def test_2_failed_confirmation_is_undone(self):
        result = self.admit("-e", "admit_addresses=203.0.113.50",
                            extra_env={"FAKE_ANSIBLE": "fail"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Not admitted, confirmation failed", result.stdout)
        self.assertNotIn("deb13-vt-0005.example.org", self.admitted())
        self.assertNotIn("deb13-vt-0005.example.org", self.known_hosts())

    def test_3_console_fingerprint(self):
        wrong = self.admit("-e", "admit_addresses=203.0.113.50",
                           "-e", "admit_expected_fingerprint=SHA256:" + "B" * 43)
        self.assertIn("203.0.113.50: refused deb13-vt-0005.example.org - the console fingerprint", wrong.stdout)
        self.assertEqual(wrong.returncode, 2)
        self.assertNotIn("deb13-vt-0005.example.org", self.admitted())
        pub = self.nodes["203.0.113.50"]["keys"][0]
        right = subprocess.run(["ssh-keygen", "-l", "-E", "sha256", "-f", pub],
                               capture_output=True, text=True).stdout.split()[1]
        good = self.admit("-e", "admit_addresses=203.0.113.50",
                          "-e", f"admit_expected_fingerprint={right}")
        self.assertEqual(good.returncode, 0, good.stdout[-2000:])
        self.assertIn("203.0.113.50: admitted deb13-vt-0005.example.org", good.stdout)
        self.assertNotIn("PA-HOST-01 host key trusted on first use", good.stdout)
        self.assertIn("deb13-vt-0005.example.org", self.admitted())
        self.assertIn("deb13-vt-0001.example.org", self.admitted())

    def test_7_promoted_node_keeps_strict_host_key_checking(self):
        promoted = self.run_cmd(
            [sys.executable, "scripts/promote_node.py", "--inventory", str(self.client),
             "--from", "raw", "--to", "onboard/dev", "--host", "deb13-vt-0001.example.org",
             "--key-file", str(self.client_key), "--no-commit"], check=False)
        self.assertEqual(promoted.returncode, 0, promoted.stderr)
        self.assertNotIn("deb13-vt-0001.example.org", self.admitted())
        self.check_inventory()
        # Only the onboard stage: no admitted group_vars apply any more, and
        # uc_known_hosts_file comes from the onboarded group.
        ping = ["ansible", *self.inventory_args("onboard/dev"), "deb13-vt-0001.example.org",
                "-m", "ansible.builtin.raw", "-a", "true"]
        self.assertEqual(self.run_cmd(ping, check=False).returncode, 0)
        path = self.client / "ssh/known_hosts"
        original = path.read_text()
        line = next(l for l in original.splitlines() if l.startswith("deb13-vt-0001.example.org ssh-ed25519 "))
        key = line.split()[2]
        path.write_text(original.replace(key, key[:-6] + ("A" if key[-6] != "A" else "B") + key[-5:]))
        try:
            refused = self.run_cmd(ping, check=False)
        finally:
            path.write_text(original)
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("Host key verification failed", refused.stdout + refused.stderr)

    def test_4_from_discovered(self):
        discovered = self.client / "raw/discovered.yml"
        discovered.write_text(yaml.safe_dump({"discovered": {"hosts": {
            "disc-203-0-113-10": {"ansible_host": "203.0.113.10", "name_provisional": True},
            "disc-203-0-113-20": {"ansible_host": "203.0.113.20", "name_provisional": True},
            "disc-203-0-113-99": {"ansible_host": "203.0.113.99", "name_provisional": True},
        }}}))
        try:
            result = self.admit("-e", "admit_from_discovered=true")
        finally:
            discovered.unlink()
        self.assertEqual(result.returncode, 0, result.stdout[-2000:])
        self.assertIn("203.0.113.10: known deb13-vt-0001.example.org", result.stdout)
        self.assertIn("203.0.113.20: not-contract", result.stdout)
        self.assertIn("203.0.113.99: not-contract", result.stdout)

    def test_5_short_batch_reported_against_rn_acc_08(self):
        self.add_node("203.0.113.60", "deb13-vt-0006", 6)
        self.save_nodes()
        result = self.admit("-e", "admit_addresses=203.0.113.60",
                            "-e", "admit_batch_id=raw-1970-01-01-02")
        self.assertEqual(result.returncode, 0, result.stdout[-2000:])
        self.assertIn("203.0.113.60: admitted deb13-vt-0006.example.org", result.stdout)
        self.assertIn("warning RN-ACC-08 batch raw-1970-01-01-02 has a passphrase under "
                      "15 characters", result.stdout)
        self.assertEqual(self.admitted()["deb13-vt-0006.example.org"]["raw_node_batch"], "raw-1970-01-01-02")
        self.assertNotIn("abc123", result.stdout + result.stderr)

    def test_6_batch_must_have_a_file(self):
        result = self.admit("-e", "admit_addresses=203.0.113.10",
                            "-e", "admit_batch_id=raw-1970-01-01-99")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("uc_secret: batches/raw-1970-01-01-99: there is no file", result.stdout)
        self.assertNotIn("fetch the SSH host keys", result.stdout)

    def test_8_passphrases_never_logged(self):
        result = self.admit("-e", "admit_addresses=203.0.113.10", "-vvv")
        self.assertEqual(result.returncode, 0, result.stdout[-2000:])
        for secret in ("tannery unbiased pebble", "abc123"):
            self.assertNotIn(secret, result.stdout + result.stderr)

    def test_9_known_node_with_changed_host_keys_is_refused(self):
        """deb13-vt-0005.example.org (admitted in test_3) against altered records in ssh/known_hosts."""
        path = self.client / "ssh/known_hosts"
        original = path.read_text()
        lines = original.splitlines()
        mine = [l for l in lines if l.startswith("deb13-vt-0005.example.org ")]
        self.assertEqual(len(mine), 2)
        ed = next(l for l in mine if " ssh-ed25519 " in l)
        key = ed.split()[2]
        changed = ed.replace(key, key[:30] + ("A" if key[30] != "A" else "B") + key[31:])
        extra_key = self.root / "extra_rsa"
        subprocess.run(["ssh-keygen", "-q", "-t", "rsa", "-b", "2048", "-N", "", "-f", str(extra_key)],
                       check=True)
        extra = "deb13-vt-0005.example.org " + " ".join(Path(f"{extra_key}.pub").read_text().split()[:2])

        cases = {
            "one key changed": "\n".join(changed if l == ed else l for l in lines),
            "a type presented but not recorded": "\n".join(
                l for l in lines if not (l.startswith("deb13-vt-0005.example.org ") and " ecdsa-" in l)),
            "a type recorded but not presented": "\n".join(
                lines + [extra]) if not original.endswith("\n") else original + extra + "\n",
            "no keys recorded": "\n".join(l for l in lines if not l.startswith("deb13-vt-0005.example.org ")),
        }
        before = self.admitted()
        try:
            for name, text in cases.items():
                with self.subTest(case=name):
                    path.write_text(text if text.endswith("\n") else text + "\n")
                    written = path.read_text()
                    result = self.admit("-e", "admit_addresses=203.0.113.50")
                    self.assertEqual(result.returncode, 2, result.stdout[-2000:])
                    self.assertIn("203.0.113.50: refused deb13-vt-0005.example.org - ", result.stdout)
                    expected = ("no host keys are recorded for deb13-vt-0005.example.org"
                                if name == "no keys recorded"
                                else "host keys differ from ssh/known_hosts for deb13-vt-0005.example.org")
                    self.assertIn(expected, result.stdout)
                    self.assertIn(f"ssh-keygen -R deb13-vt-0005.example.org -f {path}", result.stdout)
                    self.assertEqual(path.read_text(), written)   # nothing rewritten
                    self.assertEqual(self.admitted(), before)
        finally:
            path.write_text(original)
        result = self.admit("-e", "admit_addresses=203.0.113.50")
        self.assertIn("203.0.113.50: known deb13-vt-0005.example.org", result.stdout)

    # Named to sort last: it needs deb13-vt-0005.example.org, admitted in test_3.
    def test_x_exit_status(self):
        # Hosts without SSH or that refuse the controller key: exit 0.
        quiet = self.admit("-e", "admit_addresses=203.0.113.20,203.0.113.99")
        self.assertEqual(quiet.returncode, 0, quiet.stdout[-2000:])
        self.assertIn("203.0.113.20: not-contract", quiet.stdout)
        self.assertIn("203.0.113.99: not-contract", quiet.stdout)
        # A stopped outcome: another node claims deb13-vt-0005.example.org's name. Exit 2.
        self.add_node("203.0.113.70", "deb13-vt-0005", 70)
        self.save_nodes()
        before = (self.admitted(), self.known_hosts())
        stopped = self.admit("-e", "admit_addresses=203.0.113.70,203.0.113.99")
        self.assertEqual(stopped.returncode, 2, stopped.stdout[-2000:])
        self.assertIn("203.0.113.70: stopped deb13-vt-0005.example.org", stopped.stdout)
        self.assertIn("203.0.113.99: not-contract", stopped.stdout)
        self.assertIn("Refused or stopped: 203.0.113.70 stopped", stopped.stdout)
        self.assertEqual((self.admitted(), self.known_hosts()), before)

    def fingerprint(self, address, kind="ed25519"):
        pub = next(k for k in self.nodes[address]["keys"] if f"_{kind}." in k)
        return subprocess.run(["ssh-keygen", "-l", "-E", "sha256", "-f", pub],
                              capture_output=True, text=True, check=True).stdout.split()[1]

    def candidates(self, entries, name="candidates") -> str:
        path = self.repo / f"{name}.yml"
        path.write_text(yaml.safe_dump({"admit_candidates": entries}))
        return f"@{path}"

    def test_y_candidates_file(self):
        self.add_node("203.0.113.80", "deb13-vt-0008", 8)
        self.add_node("203.0.113.81", "deb13-vt-0009", 9)
        self.add_node("203.0.113.82", "deb13-vt-0010", 10)
        self.save_nodes()

        # Each node with the fingerprint read at its own console: admitted,
        # with no trust-on-first-use warning.
        good = self.admit("-e", self.candidates([
            {"address": "203.0.113.80", "fingerprint": self.fingerprint("203.0.113.80")},
            {"address": "203.0.113.81", "fingerprint": self.fingerprint("203.0.113.81", "ecdsa")}]))
        self.assertEqual(good.returncode, 0, good.stdout[-2000:])
        self.assertIn("203.0.113.80: admitted deb13-vt-0008.example.org", good.stdout)
        self.assertIn("203.0.113.81: admitted deb13-vt-0009.example.org", good.stdout)
        self.assertNotIn("PA-HOST-01", good.stdout)

        # A fingerprint that does not belong to the node: refused, exit 2;
        # the other entry is still handled.
        before = (self.admitted(), self.known_hosts())
        wrong = self.admit("-e", self.candidates([
            {"address": "203.0.113.80", "fingerprint": self.fingerprint("203.0.113.80")},
            {"address": "203.0.113.82", "fingerprint": self.fingerprint("203.0.113.80")}]))
        self.assertEqual(wrong.returncode, 2, wrong.stdout[-2000:])
        self.assertIn("203.0.113.80: known deb13-vt-0008.example.org", wrong.stdout)
        self.assertIn("203.0.113.82: refused deb13-vt-0010.example.org - the console fingerprint", wrong.stdout)
        self.assertEqual((self.admitted(), self.known_hosts()), before)

        # Rejected before anything is contacted.
        fp = self.fingerprint("203.0.113.82")
        for name, args in {
            "missing fingerprint": ["-e", self.candidates(
                [{"address": "203.0.113.82"}], "c-missing")],
            "malformed fingerprint": ["-e", self.candidates(
                [{"address": "203.0.113.82", "fingerprint": "MD5:00:11"}], "c-malformed")],
            "address twice": ["-e", self.candidates(
                [{"address": "203.0.113.82", "fingerprint": fp},
                 {"address": "203.0.113.82", "fingerprint": fp}], "c-twice")],
            "two candidate sources": ["-e", self.candidates(
                [{"address": "203.0.113.82", "fingerprint": fp}], "c-two-sources"),
                "-e", "admit_addresses=203.0.113.82"],
            "one console fingerprint for two addresses": [
                "-e", "admit_addresses=203.0.113.80,203.0.113.82",
                "-e", f"admit_expected_fingerprint={fp}"],
        }.items():
            with self.subTest(case=name):
                result = self.admit(*args)
                self.assertEqual(result.returncode, 2, result.stdout[-1500:])
                self.assertNotIn("fetch the SSH host keys", result.stdout)
        self.assertNotIn("deb13-vt-0010.example.org", self.admitted())

    def test_z_names(self):
        """The admitted name is the fully qualified domain name, from the
        confirmation's hostname and admit_client_domain."""
        # No domain, or one that is not a domain: refused before anything is contacted.
        for name, extra in {
            "no domain": ["-e", "admit_client_domain=''"],
            "one label": ["-e", "admit_client_domain=org"],
            "upper case": ["-e", "admit_client_domain=Example.org"],
            "trailing dot": ["-e", "admit_client_domain=example.org."],
        }.items():
            with self.subTest(case=name):
                result = self.admit("-e", "admit_addresses=203.0.113.10", *extra)
                self.assertEqual(result.returncode, 2, result.stdout[-1500:])
                self.assertIn("Give the domain the nodes are named in", result.stdout)
                self.assertNotIn("fetch the SSH host keys", result.stdout)

        # One hostname in two domains: two nodes, two names, no collision.
        self.add_node("203.0.113.90", "dev", 21)
        self.add_node("203.0.113.91", "dev", 22)
        # A hostname that makes no fully qualified domain name, and one with a dot.
        self.add_node("203.0.113.92", "Dev", 23)
        self.add_node("203.0.113.93", "dev.example.org", 24)
        self.save_nodes()
        org = self.admit("-e", "admit_addresses=203.0.113.90")
        self.assertEqual(org.returncode, 0, org.stdout[-2000:])
        self.assertIn("203.0.113.90: admitted dev.example.org - dev.example.org is new on every count",
                      org.stdout)
        net = self.admit("-e", "admit_addresses=203.0.113.91", "-e", "admit_client_domain=example.net")
        self.assertEqual(net.returncode, 0, net.stdout[-2000:])
        self.assertIn("203.0.113.91: admitted dev.example.net", net.stdout)
        hosts = self.admitted()
        self.assertEqual(hosts["dev.example.org"]["ansible_host"], "203.0.113.90")
        self.assertEqual(hosts["dev.example.net"]["ansible_host"], "203.0.113.91")
        self.assertNotIn("dev", hosts)
        known = self.known_hosts()
        for name in ("dev.example.org", "dev.example.net"):
            self.assertIn(f"# BEGIN {name}, admitted by 05_admit.yml", known)
            self.assertEqual(sum(1 for l in known.splitlines() if l.startswith(f"{name} ")), 2)
        self.check_inventory()

        # The same node in a third domain is known under its first name, and
        # in the second domain, whose name another node holds, a collision.
        again = self.admit("-e", "admit_addresses=203.0.113.90", "-e", "admit_client_domain=example.com")
        self.assertEqual(again.returncode, 2, again.stdout[-2000:])
        self.assertIn("203.0.113.90: stopped dev.example.com - dev.example.com is new, but its "
                      "identity is known as: dev.example.org", again.stdout)
        clash = self.admit("-e", "admit_addresses=203.0.113.90", "-e", "admit_client_domain=example.net")
        self.assertEqual(clash.returncode, 2, clash.stdout[-2000:])
        self.assertIn("203.0.113.90: stopped dev.example.net - another node is already called "
                      "dev.example.net", clash.stdout)

        before = (self.admitted(), self.known_hosts())
        bad = self.admit("-e", "admit_addresses=203.0.113.92,203.0.113.93")
        self.assertEqual(bad.returncode, 2, bad.stdout[-2000:])
        self.assertIn("203.0.113.92: refused Dev.example.org - Dev.example.org is not a fully "
                      "qualified domain name", bad.stdout)
        self.assertIn("203.0.113.93: refused dev.example.org.example.org - the confirmation names "
                      "the host dev.example.org, which is not the first label of "
                      "dev.example.org.example.org", bad.stdout)
        self.assertEqual((self.admitted(), self.known_hosts()), before)

    def test_z_a_node_admitted_under_its_hostname_is_a_conflict(self):
        """A node admitted before 0.2.0, named by its hostname alone, is not
        the same name: admitting it again is stopped until its entry goes."""
        self.add_node("203.0.113.95", "stage", 25)
        self.save_nodes()
        path = self.client / "raw/admitted.yml"
        original = path.read_text()
        data = yaml.safe_load(original)
        data["admitted"]["hosts"]["stage"] = {
            "ansible_host": "203.0.113.95", "raw_node_machine_id": machine_id(25),
            "raw_node_macs": [mac(25)], "raw_node_batch": self.batch}
        path.write_text(yaml.safe_dump(data, sort_keys=False))
        try:
            result = self.admit("-e", "admit_addresses=203.0.113.95")
        finally:
            path.write_text(original)
        self.assertEqual(result.returncode, 2, result.stdout[-2000:])
        self.assertIn("203.0.113.95: stopped stage.example.org - stage.example.org is new, but its "
                      "identity is known as: stage (machine_id and mac, raw/admitted.yml)", result.stdout)


if __name__ == "__main__":
    unittest.main()
