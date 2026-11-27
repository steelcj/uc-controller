"""Tests for match_raw_identity.py, and for how promote_node.py and
reset_inventories.py handle a client inventory's raw/admitted.yml.

Standard library and PyYAML only, and yamllint where it is on PATH. Each
test works on a temporary copy of scripts/, inventory-defaults/ and
inventory-template/, with a client inventory made by scripts/new-inventory,
never on a real client inventory.

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

# The register's machine IDs, 19700101...ab<host number>.
ID_1, ID_2, ID_3, ID_4 = (f"19700101{'0' * 20}ab{n:02d}" for n in (1, 2, 3, 4))

ADMITTED = {
    "ansible_host": "192.0.2.10",
    "ansible_port": 22,
    "raw_node_contract": "0.3.0",
    "raw_node_baseline": "0.4.0",
    "raw_node_machine_id": ID_1,
    "raw_node_macs": ["02:00:00:ab:00:01"],
    "raw_node_batch": "raw-1970-01-01-01",
    "raw_node_admitted": "2026-11-18T01:00:00-05:00",
}


class TempRepo(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "uc-controller"
        for item in ("scripts", "inventory-defaults", "inventory-template"):
            shutil.copytree(REPO / item, self.repo / item,
                            ignore=shutil.ignore_patterns("__pycache__"))
        (self.repo / "ansible.cfg").write_text("[defaults]\n")
        self.client = Path(self.tmp.name) / "example.org"
        made = subprocess.run([sys.executable, str(self.repo / "scripts/new-inventory"),
                               str(self.client)], capture_output=True, text=True)
        self.assertEqual(made.returncode, 0, made.stderr)
        (self.client / "raw/incus.yml").unlink()
        self.write("raw/admitted.yml", {"admitted": {"hosts": {"deb13-vt-0001.example.org": dict(ADMITTED)}}})

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative: str, data) -> Path:
        path = self.client / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data))
        return path

    def run_script(self, name: str, *args):
        return subprocess.run([sys.executable, str(self.repo / "scripts" / name), *args],
                              capture_output=True, text=True, cwd=self.repo)


class IdentityDecisions(TempRepo):
    def decide(self, name, machine_id, *macs):
        args = ["--inventory", str(self.client), "--name", name, "--machine-id", machine_id]
        for mac in macs:
            args += ["--mac", mac]
        result = self.run_script("match_raw_identity.py", *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_the_client_inventory_is_required(self):
        result = self.run_script("match_raw_identity.py", "--name", "x", "--machine-id", "y")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--inventory", result.stderr)

    def test_new(self):
        outcome = self.decide("deb13-vt-0002.example.org", ID_2, "02:00:00:ab:00:02")
        self.assertEqual((outcome["decision"], outcome["admit"]), ("new", True))

    def test_known(self):
        outcome = self.decide("deb13-vt-0001.example.org", ID_1, "02:00:00:ab:00:01")
        self.assertEqual((outcome["decision"], outcome["admit"]), ("known", False))
        self.assertEqual(outcome["matches"][0]["file"], "raw/admitted.yml")

    def test_reinstall_in_raw(self):
        outcome = self.decide("deb13-vt-0001.example.org", ID_3, "02:00:00:ab:00:01")
        self.assertEqual(outcome["decision"], "reinstall")
        self.assertIn(f"remove deb13-vt-0001.example.org from {self.client}/raw/admitted.yml", outcome["message"])
        self.assertIn(f"ssh-keygen -R deb13-vt-0001.example.org -f {self.client}/ssh/known_hosts",
                      outcome["message"])

    def test_reinstall_in_onboard_says_what_to_demote(self):
        self.write("raw/admitted.yml", {"admitted": {"hosts": {}}})
        self.write("onboard/dev/hosts.yml", {"onboarded": {"hosts": {"deb13-vt-0001.example.org": dict(ADMITTED)}}})
        outcome = self.decide("deb13-vt-0001.example.org", ID_3, "02:00:00:ab:00:01")
        self.assertEqual(outcome["decision"], "reinstall")
        self.assertIn(f"demote_node.py --inventory {self.client} --from onboard/dev --to raw "
                      "--host deb13-vt-0001.example.org", outcome["message"])

    def test_collision(self):
        outcome = self.decide("deb13-vt-0001.example.org", ID_3, "02:00:00:ab:00:09")
        self.assertEqual(outcome["decision"], "collision")

    def test_collision_with_a_host_without_identifiers(self):
        self.write("normalized/dev/hosts.yml", {"normalized": {"hosts": {"dev.example.org": {"ansible_host": "203.0.113.2"}}}})
        outcome = self.decide("dev.example.org", ID_3, "02:00:00:ab:00:09")
        self.assertEqual(outcome["decision"], "collision")

    def test_known_under_another_name(self):
        for args in (("deb13-vt-0009.example.org", ID_1, "02:00:00:ab:00:09"),
                     ("deb13-vt-0009.example.org", ID_3, "02:00:00:ab:00:01")):
            with self.subTest(args=args):
                outcome = self.decide(*args)
                self.assertEqual(outcome["decision"], "conflict")
                self.assertIn("deb13-vt-0001.example.org", outcome["message"])

    def test_host_vars_count(self):
        self.write("raw/admitted.yml", {"admitted": {"hosts": {}}})
        self.write("onboard/dev/host_vars/deb13-vt-0001.example.org.yml", {"raw_node_machine_id": ID_1})
        outcome = self.decide("deb13-vt-0001.example.org", ID_1)
        self.assertEqual(outcome["decision"], "known")

    def test_names_are_compared_whole(self):
        # The same hostname in another domain is another name.
        outcome = self.decide("deb13-vt-0001.example.net", ID_2, "02:00:00:ab:00:02")
        self.assertEqual(outcome["decision"], "new")
        # A node admitted under its hostname alone is known by its identity.
        self.write("raw/admitted.yml", {"admitted": {"hosts": {"dev": dict(ADMITTED)}}})
        outcome = self.decide("dev.example.org", ID_1, "02:00:00:ab:00:01")
        self.assertEqual(outcome["decision"], "conflict")
        self.assertIn("dev (machine_id and mac, raw/admitted.yml)", outcome["message"])

    def test_the_client_repositorys_git_directory_is_not_read(self):
        self.write(".git/stray.yml", {"admitted": {"hosts": {"deb13-vt-0007.example.org": {"raw_node_machine_id": ID_4}}}})
        outcome = self.decide("deb13-vt-0008.example.org", ID_4)
        self.assertEqual(outcome["decision"], "new")


class PromoteAndReset(TempRepo):
    def promote(self, host, *extra):
        return self.run_script(
            "promote_node.py", "--inventory", str(self.client), "--from", "raw",
            "--to", "onboard/dev", "--host", host, "--key-file", "~/.ssh/key", "--no-commit", *extra)

    def onboarded(self, host):
        onboard = yaml.safe_load((self.client / "onboard/dev/hosts.yml").read_text())
        return onboard["onboarded"]["hosts"][host]

    def test_promote_moves_an_admitted_host_out_of_raw(self):
        result = self.promote("deb13-vt-0001.example.org")
        self.assertEqual(result.returncode, 0, result.stderr)
        admitted = self.client / "raw/admitted.yml"
        text = admitted.read_text()
        self.assertTrue(text.startswith("# raw/admitted.yml"))
        self.assertTrue(text.startswith((REPO / "inventory-template/raw/admitted.yml").read_text()
                                        .split("admitted:\n")[0]))
        self.assertNotIn("deb13-vt-0001.example.org", text)
        entry = self.onboarded("deb13-vt-0001.example.org")
        self.assertEqual(entry["raw_node_machine_id"], ID_1)
        self.assertEqual(entry["raw_node_batch"], "raw-1970-01-01-01")
        self.assertEqual(entry["ansible_user"], "initial")
        self.assertNotIn("uc_origin", entry)

        # The admitted group's strict host key settings, from
        # inventory-defaults/raw/group_vars/admitted.yml, move onto the host.
        self.assertIs(entry["ansible_ssh_host_key_checking"], True)
        args = entry["ansible_ssh_common_args"]
        for option in ("IdentitiesOnly=yes", "StrictHostKeyChecking=yes",
                       "HostKeyAlias={{ inventory_hostname }}",
                       "UserKnownHostsFile={{ uc_known_hosts_file }}",
                       "GlobalKnownHostsFile=/dev/null"):
            self.assertIn(option, args)
        self.assertIn("keeps its strict host key settings", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_a_promoted_inventory_passes_the_client_checks(self):
        self.write("raw/discovered.yml", {"discovered": {"hosts": {
            "disc-192-0-2-20": {"ansible_host": "192.0.2.20", "name_provisional": True}}}})
        for host in ("deb13-vt-0001.example.org", "disc-192-0-2-20"):
            self.assertEqual(self.promote(host).returncode, 0)
        check = self.run_script("check_inventory.py", str(self.client))
        self.assertEqual(check.returncode, 0, check.stderr)
        if shutil.which("yamllint"):
            lint = subprocess.run(["yamllint", "-c", str(self.client / ".yamllint"), "."],
                                  cwd=self.client, capture_output=True, text=True)
            self.assertEqual(lint.returncode, 0, lint.stdout + lint.stderr)

    def test_promotion_and_demotion_keep_the_name(self):
        name = "deb13-vt-0001.example.org"
        moves = [("promote_node.py", "raw", "onboard/dev", ["--key-file", "~/.ssh/key"]),
                 ("promote_node.py", "onboard/dev", "normalized/dev", []),
                 ("demote_node.py", "normalized/dev", "onboard/dev", []),
                 ("promote_node.py", "onboard/dev", "normalized/dev", [])]
        for script, source, dest, extra in moves:
            with self.subTest(move=f"{source} -> {dest}"):
                result = self.run_script(script, "--inventory", str(self.client), "--from", source,
                                         "--to", dest, "--host", name, "--no-commit", *extra)
                self.assertEqual(result.returncode, 0, result.stderr)
                hosts = yaml.safe_load((self.client / dest / "hosts.yml").read_text())
                group = "onboarded" if dest.startswith("onboard") else "normalized"
                self.assertEqual(list(hosts[group]["hosts"]), [name])
                self.assertEqual(hosts[group]["hosts"][name]["raw_node_batch"], "raw-1970-01-01-01")
                left = yaml.safe_load((self.client / source / "hosts.yml").read_text()) if source != "raw" \
                    else yaml.safe_load((self.client / "raw/admitted.yml").read_text())
                self.assertNotIn(name, str(left))
        # The client checks pass with the name at the normalized stage, its
        # host keys still under it in ssh/known_hosts.
        (self.client / "ssh/known_hosts").write_text(
            f"{name} ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIExampleExampleExampleExampleExampleExampl\n")
        check = self.run_script("check_inventory.py", str(self.client))
        self.assertEqual(check.returncode, 0, check.stderr)
        result = self.run_script("demote_node.py", "--inventory", str(self.client), "--from",
                                 "normalized/dev", "--to", "raw", "--host", name, "--no-commit")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(name, (self.client / "normalized/dev/hosts.yml").read_text())

    def test_stages_are_named_not_given_as_paths(self):
        for stages in (("raw", "onboard"), ("raw", "inventories/onboard/dev"), ("raw", "onboard/prod")):
            with self.subTest(stages=stages):
                result = self.run_script("promote_node.py", "--inventory", str(self.client),
                                         "--from", stages[0], "--to", stages[1],
                                         "--host", "deb13-vt-0001.example.org", "--no-commit")
                self.assertNotEqual(result.returncode, 0)
        self.assertIn("deb13-vt-0001.example.org", (self.client / "raw/admitted.yml").read_text())

    def test_promote_without_strict_settings_is_unchanged(self):
        self.write("raw/discovered.yml", {"discovered": {"hosts": {
            "disc-192-0-2-20": {"ansible_host": "192.0.2.20", "name_provisional": True}}}})
        result = self.promote("disc-192-0-2-20")
        self.assertEqual(result.returncode, 0, result.stderr)
        entry = self.onboarded("disc-192-0-2-20")
        self.assertEqual(entry["ansible_ssh_common_args"], "-o IdentitiesOnly=yes")
        self.assertNotIn("ansible_ssh_host_key_checking", entry)
        self.assertNotIn("strict", result.stdout)

    def test_promote_keeps_host_level_strict_settings(self):
        self.write("raw/discovered.yml", {"discovered": {"hosts": {
            "disc-192-0-2-30": {"ansible_host": "192.0.2.30",
                                "ansible_host_key_checking": "yes",
                                "ansible_ssh_common_args": "-o StrictHostKeyChecking=yes"}}}})
        self.assertEqual(self.promote("disc-192-0-2-30").returncode, 0)
        entry = self.onboarded("disc-192-0-2-30")
        self.assertEqual(entry["ansible_host_key_checking"], "yes")
        self.assertEqual(entry["ansible_ssh_common_args"],
                         "-o IdentitiesOnly=yes -o StrictHostKeyChecking=yes")

    def test_reset_clears_admitted(self):
        dry = self.run_script("reset_inventories.py", "--inventory", str(self.client),
                              "--dry-run", "--keep-facts")
        self.assertIn("Would clear raw/admitted.yml: deb13-vt-0001.example.org", dry.stdout)
        self.assertIn("deb13-vt-0001.example.org", (self.client / "raw/admitted.yml").read_text())
        done = self.run_script("reset_inventories.py", "--inventory", str(self.client), "--keep-facts")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(f"ssh-keygen -R <host> -f {self.client}/ssh/known_hosts", done.stdout)
        data = yaml.safe_load((self.client / "raw/admitted.yml").read_text())
        self.assertEqual(data, {"admitted": {"hosts": {}}})

    def test_reset_keep_raw(self):
        result = self.run_script("reset_inventories.py", "--inventory", str(self.client),
                                 "--keep-raw", "--keep-facts")
        self.assertNotIn("admitted.yml", result.stdout)
        self.assertIn("deb13-vt-0001.example.org", (self.client / "raw/admitted.yml").read_text())

    def test_reset_needs_the_client_inventory(self):
        result = self.run_script("reset_inventories.py", "--keep-facts")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--inventory", result.stderr)


if __name__ == "__main__":
    unittest.main()
