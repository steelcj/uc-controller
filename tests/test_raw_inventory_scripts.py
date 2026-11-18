"""Tests for match_raw_identity.py, and for how promote_node.py and
reset_inventories.py handle inventories/raw/admitted.yml.

Standard library and PyYAML only. Each test works on a temporary copy of
scripts/ and inventories/, never on the repository's own inventories.

    python3 tests/run_tests.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent

ADMITTED = {
    "ansible_host": "192.0.2.10",
    "ansible_port": 22,
    "raw_node_contract": "0.3.0",
    "raw_node_baseline": "0.4.0",
    "raw_node_machine_id": "a" * 32,
    "raw_node_macs": ["52:54:00:00:00:01"],
    "raw_node_batch": "raw-2026-11-17-manual",
    "raw_node_admitted": "2026-11-18T01:00:00-05:00",
}


class TempRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        shutil.copytree(REPO / "scripts", self.repo / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        # Leave out the generated raw inventories, but not group_vars/admitted.yml.
        generated = {REPO / "inventories/raw/admitted.yml", REPO / "inventories/raw/discovered.yml"}
        shutil.copytree(REPO / "inventories", self.repo / "inventories",
                        ignore=lambda folder, names: [n for n in names
                                                      if Path(folder) / n in generated])
        (self.repo / "ansible.cfg").write_text("[defaults]\n")
        self.write("raw/admitted.yml", {"admitted": {"hosts": {"node-vt-0001": dict(ADMITTED)}}})

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative: str, data) -> Path:
        path = self.repo / "inventories" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data))
        return path

    def run_script(self, name: str, *args):
        return subprocess.run([sys.executable, str(self.repo / "scripts" / name), *args],
                              capture_output=True, text=True, cwd=self.repo)


class IdentityDecisions(TempRepo):
    def decide(self, hostname, machine_id, *macs):
        args = ["--hostname", hostname, "--machine-id", machine_id]
        for mac in macs:
            args += ["--mac", mac]
        result = self.run_script("match_raw_identity.py", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_new(self):
        outcome = self.decide("node-vt-0002", "b" * 32, "52:54:00:00:00:02")
        self.assertEqual((outcome["decision"], outcome["admit"]), ("new", True))

    def test_known(self):
        outcome = self.decide("node-vt-0001", "a" * 32, "52:54:00:00:00:01")
        self.assertEqual((outcome["decision"], outcome["admit"]), ("known", False))

    def test_reinstall_in_raw(self):
        outcome = self.decide("node-vt-0001", "c" * 32, "52:54:00:00:00:01")
        self.assertEqual(outcome["decision"], "reinstall")
        self.assertIn("remove node-vt-0001 from inventories/raw/admitted.yml", outcome["message"])
        self.assertIn("ssh-keygen -R node-vt-0001 -f ssh/known_hosts", outcome["message"])

    def test_reinstall_in_onboard_says_what_to_demote(self):
        self.write("raw/admitted.yml", {"admitted": {"hosts": {}}})
        self.write("onboard/dev/hosts.yml", {"onboarded": {"hosts": {"node-vt-0001": dict(ADMITTED)}}})
        outcome = self.decide("node-vt-0001", "c" * 32, "52:54:00:00:00:01")
        self.assertEqual(outcome["decision"], "reinstall")
        self.assertIn("demote_node.py --from inventories/onboard/dev --to inventories/raw "
                      "--host node-vt-0001", outcome["message"])

    def test_collision(self):
        outcome = self.decide("node-vt-0001", "c" * 32, "52:54:00:00:00:09")
        self.assertEqual(outcome["decision"], "collision")

    def test_collision_with_a_host_without_identifiers(self):
        self.write("normalized/dev/hosts.yml", {"normalized": {"hosts": {"deb13": {"ansible_host": "10.0.0.2"}}}})
        outcome = self.decide("deb13", "c" * 32, "52:54:00:00:00:09")
        self.assertEqual(outcome["decision"], "collision")

    def test_known_under_another_name(self):
        for args in (("node-vt-0009", "a" * 32, "52:54:00:00:00:09"),
                     ("node-vt-0009", "c" * 32, "52:54:00:00:00:01")):
            with self.subTest(args=args):
                outcome = self.decide(*args)
                self.assertEqual(outcome["decision"], "conflict")
                self.assertIn("node-vt-0001", outcome["message"])

    def test_host_vars_count(self):
        self.write("raw/admitted.yml", {"admitted": {"hosts": {}}})
        self.write("onboard/dev/host_vars/node-vt-0001.yml", {"raw_node_machine_id": "a" * 32})
        outcome = self.decide("node-vt-0001", "a" * 32)
        self.assertEqual(outcome["decision"], "known")


class PromoteAndReset(TempRepo):
    def test_promote_moves_an_admitted_host_out_of_raw(self):
        result = self.run_script(
            "promote_node.py", "--from", "inventories/raw", "--to", "inventories/onboard/dev",
            "--host", "node-vt-0001", "--key-file", "~/.ssh/key", "--no-commit")
        self.assertEqual(result.returncode, 0, result.stderr)
        admitted = self.repo / "inventories/raw/admitted.yml"
        text = admitted.read_text()
        self.assertTrue(text.startswith("# inventories/raw/admitted.yml"))
        self.assertNotIn("node-vt-0001", text)
        onboard = yaml.safe_load((self.repo / "inventories/onboard/dev/hosts.yml").read_text())
        entry = onboard["onboarded"]["hosts"]["node-vt-0001"]
        self.assertEqual(entry["raw_node_machine_id"], "a" * 32)
        self.assertEqual(entry["raw_node_batch"], "raw-2026-11-17-manual")
        self.assertEqual(entry["ansible_user"], "initial")
        self.assertNotIn("uc_origin", entry)

        # The admitted group's strict host key settings move onto the host.
        self.assertIs(entry["ansible_ssh_host_key_checking"], True)
        args = entry["ansible_ssh_common_args"]
        for option in ("IdentitiesOnly=yes", "StrictHostKeyChecking=yes",
                       "HostKeyAlias={{ inventory_hostname }}",
                       "UserKnownHostsFile={{ ansible_config_file | dirname }}/ssh/known_hosts",
                       "GlobalKnownHostsFile=/dev/null"):
            self.assertIn(option, args)
        self.assertIn("keeps its strict host key settings", result.stdout)
        # group_vars/admitted/vault.yml is encrypted: passed over, with a warning.
        self.assertIn("warning: ", result.stderr)
        self.assertIn("group_vars/admitted/vault.yml is encrypted and was not read", result.stderr)

    def promote(self, host):
        result = self.run_script(
            "promote_node.py", "--from", "inventories/raw", "--to", "inventories/onboard/dev",
            "--host", host, "--key-file", "~/.ssh/key", "--no-commit")
        self.assertEqual(result.returncode, 0, result.stderr)
        onboard = yaml.safe_load((self.repo / "inventories/onboard/dev/hosts.yml").read_text())
        return onboard["onboarded"]["hosts"][host], result

    def test_promote_without_strict_settings_is_unchanged(self):
        self.write("raw/discovered.yml", {"discovered": {"hosts": {
            "disc-192-0-2-20": {"ansible_host": "192.0.2.20", "name_provisional": True}}}})
        entry, result = self.promote("disc-192-0-2-20")
        self.assertEqual(entry["ansible_ssh_common_args"], "-o IdentitiesOnly=yes")
        self.assertNotIn("ansible_ssh_host_key_checking", entry)
        self.assertNotIn("strict", result.stdout)

    def test_promote_keeps_host_level_strict_settings(self):
        self.write("raw/discovered.yml", {"discovered": {"hosts": {
            "disc-192-0-2-30": {"ansible_host": "192.0.2.30",
                                "ansible_host_key_checking": "yes",
                                "ansible_ssh_common_args": "-o StrictHostKeyChecking=yes"}}}})
        entry, _ = self.promote("disc-192-0-2-30")
        self.assertEqual(entry["ansible_host_key_checking"], "yes")
        self.assertEqual(entry["ansible_ssh_common_args"],
                         "-o IdentitiesOnly=yes -o StrictHostKeyChecking=yes")

    def test_reset_clears_admitted(self):
        dry = self.run_script("reset_inventories.py", "--dry-run", "--keep-facts")
        self.assertIn("Would clear raw/admitted.yml: node-vt-0001", dry.stdout)
        self.assertIn("node-vt-0001", (self.repo / "inventories/raw/admitted.yml").read_text())
        done = self.run_script("reset_inventories.py", "--keep-facts")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("ssh-keygen -R", done.stdout)
        data = yaml.safe_load((self.repo / "inventories/raw/admitted.yml").read_text())
        self.assertEqual(data, {"admitted": {"hosts": {}}})

    def test_reset_keep_raw(self):
        result = self.run_script("reset_inventories.py", "--keep-raw", "--keep-facts")
        self.assertNotIn("admitted.yml", result.stdout)
        self.assertIn("node-vt-0001", (self.repo / "inventories/raw/admitted.yml").read_text())


if __name__ == "__main__":
    unittest.main()
