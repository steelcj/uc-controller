"""The inventory split leaves every variable as it was.

Before the split, step 0 of the inventory split phase recorded what
ansible-inventory --list gave for the repository's own inventories with one
host in each source group and stage. tests/fixtures/inventory-split/expected/
holds that output with only the allowed changes applied:

- ansible_become_password: the vault expression replaced by the uc_secret lookup
- UserKnownHostsFile: the repository's ssh/known_hosts replaced by uc_known_hosts_file
- the users authorized key: the literal replaced by onboard_initial_authorized_keys
- uc_client_inventory, uc_known_hosts_file and onboard_initial_authorized_keys, which are new
- the firewall_rules_<stage> lists, renamed and reshaped for steelcj.foomuuri:
  firewall_onboard_ssh, firewall_normalize_services and firewall_specialize_services,
  with the same ports, protocols and sources (tests/test_uc_firewall_interim.py checks
  that uc_firewall still gets the same rules)
- for the stage environments only, the onboard policy (umask, openssh and users),
  which inventory-defaults/onboard/ now gives every onboard environment and the
  old onboard/stage inventory did not set

The operator's public key and key path are replaced by example values.

This test makes a client inventory with scripts/new-inventory, puts the same
hosts and values into it from tests/fixtures/inventory-split/client/, runs
ansible-inventory with scripts/inventory-args for the same stage
combinations, and compares the parsed output with the fixture. ansible-inventory
shows users' authorized key as its expression, so the resolved value is
checked with the debug module, which runs on the controller and connects to
no host.

    python3 tests/run_tests.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests/fixtures/inventory-split"
COMBINATIONS = {
    "raw+onboard-dev": ("raw", "onboard/dev"),
    "onboard-dev+normalized-dev": ("onboard/dev", "normalized/dev"),
    "onboard-stage+normalized-stage": ("onboard/stage", "normalized/stage"),
}
EXAMPLE_KEY = "ssh-ed25519 EXAMPLE-PUBLIC-KEY-NOT-A-REAL-ONE initial@example.org"


@unittest.skipUnless(shutil.which("ansible-inventory"), "Ansible not on PATH")
class InventorySplit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.client = Path(cls.tmp.name) / "example.org"
        subprocess.run([sys.executable, str(REPO / "scripts/new-inventory"), str(cls.client)],
                       check=True, capture_output=True)
        # No fixture asks an Incus server what exists: the incus host is static.
        (cls.client / "raw/incus.yml").unlink()
        shutil.copytree(FIXTURES / "client", cls.client, dirs_exist_ok=True)
        cls.env = dict(os.environ, ANSIBLE_NOCOLOR="1", ANSIBLE_BECOME="false")
        cls.env.pop("ANSIBLE_CONFIG", None)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def inventory_args(self, *stages) -> list[str]:
        result = subprocess.run([sys.executable, str(REPO / "scripts/inventory-args"),
                                 str(self.client), *stages], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.split()

    def test_variables_are_as_before(self):
        for name, stages in COMBINATIONS.items():
            with self.subTest(combination=name):
                result = subprocess.run(
                    ["ansible-inventory", *self.inventory_args(*stages), "--list", "--yaml"],
                    cwd=REPO, env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                expected = yaml.safe_load((FIXTURES / "expected" / f"{name}.yml").read_text())
                self.assertEqual(yaml.safe_load(result.stdout), expected)

    def test_users_resolves_to_the_same_key(self):
        hosts = ["deb13-vt-0001.example.org", "example-onb-dev", "disc-203-0-113-20", "example-incus-01"]
        result = subprocess.run(
            ["ansible", ",".join(hosts), *self.inventory_args("raw", "onboard/dev"),
             "-m", "ansible.builtin.debug", "-a", "var=users",
             # The admitted host's become password is evaluated even for debug.
             "-e", "ansible_become_password=not-used"],
            cwd=REPO, capture_output=True, text=True,
            env=dict(self.env, ANSIBLE_LOAD_CALLBACK_PLUGINS="1", ANSIBLE_STDOUT_CALLBACK="json"))
        self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])
        document, _ = json.JSONDecoder().raw_decode(result.stdout[result.stdout.index("{"):])
        resolved = document["plays"][0]["tasks"][0]["hosts"]
        self.assertEqual(sorted(resolved), sorted(hosts))
        for host, value in resolved.items():
            with self.subTest(host=host):
                self.assertEqual(value["users"], [{
                    "name": "initial", "comment": "Ansible management user",
                    "sudo_options": "ALL=(ALL) NOPASSWD: ALL", "authorized_keys": [EXAMPLE_KEY]}])


if __name__ == "__main__":
    unittest.main()
