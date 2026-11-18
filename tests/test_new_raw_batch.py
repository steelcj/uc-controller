"""Tests for scripts/new_raw_batch.py and scripts/vault-client.py.

Standard library and PyYAML only. The end-to-end tests also need
ansible-vault on PATH and are skipped without it. Every test uses a
temporary vault directory (UC_VAULT_DIR) and a temporary store, never the
operator's own.

    python3 -m unittest discover -s tests
"""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "new_raw_batch.py"
CLIENT = REPO / "scripts" / "vault-client.py"
sys.path.insert(0, str(REPO / "scripts"))

import new_raw_batch  # noqa: E402
from sha512_crypt import sha512_crypt  # noqa: E402

PASSWORD = "abcDEF123456789xyz"


class BatchIds(unittest.TestCase):
    def test_valid(self):
        for batch_id in ("raw-2026-11-17-01", "raw-2026-11-17-manual", "raw-2026-11-17-a-b"):
            self.assertEqual(new_raw_batch.check_batch_id(batch_id), batch_id)

    def test_invalid(self):
        for batch_id in ("raw-2026-11-17", "raw-2026-13-01-01", "Raw-2026-11-17-01",
                         "raw-2026-11-17-../x", "raw-2026-11-17-$(id)", "x"):
            with self.subTest(batch_id=batch_id), self.assertRaises(SystemExit):
                new_raw_batch.check_batch_id(batch_id)

    def test_next_id_skips_used(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Path(tmp)
            index = new_raw_batch.load_index(store)
            first = new_raw_batch.next_batch_id(store, index)
            self.assertTrue(first.endswith("-01"))
            index["batches"][first] = {"status": "retired"}
            self.assertTrue(new_raw_batch.next_batch_id(store, index).endswith("-02"))


class Passwords(unittest.TestCase):
    def test_generated(self):
        for _ in range(50):
            value = new_raw_batch.generate_password(24)
            self.assertEqual(len(value), 24)
            self.assertTrue(value.isalnum() and value.isascii())
            self.assertTrue(any(c.isdigit() for c in value))
            self.assertTrue(any(c.isalpha() for c in value))


class RetireChecksHosts(unittest.TestCase):
    """--retire looks at raw_node_batch on hosts in every stage inventory."""

    BATCH = "raw-2026-11-17-01"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.inventories = root / "inventories"
        self.store = root / "store"
        self.store.mkdir()
        (self.store / f"{self.BATCH}.vault").write_text(new_raw_batch.VAULT_HEADER + "\n")
        new_raw_batch.save_index(self.store, {
            "current": "raw-2026-11-17-02",
            "batches": {
                self.BATCH: {"status": "active", "origin": "generated", "meets_min_length": True},
                "raw-2026-11-17-02": {"status": "active", "origin": "generated", "meets_min_length": True},
            },
        })
        patcher = mock.patch.object(new_raw_batch, "INVENTORIES", self.inventories)
        patcher.start()
        self.addCleanup(patcher.stop)
        quiet = mock.patch("sys.stdout", new_callable=io.StringIO)
        quiet.start()
        self.addCleanup(quiet.stop)
        self.addCleanup(self.tmp.cleanup)

    def write(self, relative: str, data) -> None:
        path = self.inventories / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(data))

    def test_hosts_found_in_every_kind_of_file(self):
        self.write("raw/admitted.yml", {"admitted": {"hosts": {"a1": {"raw_node_batch": self.BATCH}}}})
        self.write("raw/incus.yml", {"plugin": "community.general.incus"})
        self.write("onboard/dev/hosts.yml", {"onboarded": {"hosts": {
            "o1": {"raw_node_batch": self.BATCH}, "o2": {"raw_node_batch": "raw-2026-11-17-02"}}}})
        self.write("normalized/dev/host_vars/n1.yml", {"raw_node_batch": self.BATCH})
        self.write("normalized/dev/group_vars/all.yml", {"raw_node_batch": self.BATCH})
        self.write("normalized/dev/hosts.yml", {"normalized": {"children": {
            "web": {"hosts": {"n2": None}}}}})
        found = sorted(host for _, host in new_raw_batch.hosts_using(self.BATCH))
        self.assertEqual(found, ["a1", "n1", "o1"])

    def test_mention_without_raw_node_batch_does_not_block(self):
        self.write("onboard/dev/hosts.yml", {"onboarded": {"hosts": {
            "o1": {"note": f"was built with {self.BATCH}"}}}})
        self.assertEqual(new_raw_batch.retire(self.store, self.BATCH, False), 0)

    def test_refused_while_a_host_uses_it(self):
        self.write("onboard/dev/hosts.yml", {"onboarded": {"hosts": {"o1": {"raw_node_batch": self.BATCH}}}})
        with self.assertRaises(SystemExit) as raised:
            new_raw_batch.retire(self.store, self.BATCH, False)
        self.assertIn("o1", str(raised.exception))
        self.assertTrue((self.store / f"{self.BATCH}.vault").exists())

    def test_force(self):
        self.write("onboard/dev/hosts.yml", {"onboarded": {"hosts": {"o1": {"raw_node_batch": self.BATCH}}}})
        with mock.patch("sys.stderr"):
            self.assertEqual(new_raw_batch.retire(self.store, self.BATCH, True), 0)
        self.assertFalse((self.store / f"{self.BATCH}.vault").exists())
        self.assertEqual(new_raw_batch.load_index(self.store)["batches"][self.BATCH]["status"], "retired")


@unittest.skipUnless(shutil.which("ansible-vault"), "ansible-vault not on PATH")
@unittest.skipUnless(os.name == "posix", "ansible-vault runs on Linux and macOS")
class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = self.root / "store"
        self.env = dict(os.environ, UC_VAULT_DIR=str(self.root / "vault"))

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args, stdin=None, script=SCRIPT):
        extra = ["--store", str(self.store)] if script == SCRIPT else []
        return subprocess.run([sys.executable, str(script), *extra, *args], input=stdin,
                              capture_output=True, text=True, env=self.env, cwd=REPO)

    def index(self):
        return yaml.safe_load((self.store / "index.yml").read_text())

    def init_vault(self):
        result = self.run_script("--init", script=CLIENT)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_refuses_without_vault_password(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("--init", result.stderr)
        self.assertFalse(self.store.exists())

    def test_client_placeholder_without_password(self):
        result = self.run_script("--vault-id", "raw_batch", script=CLIENT)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout.strip()), 64)

    def test_vault_password_file_is_private(self):
        self.init_vault()
        mode = (self.root / "vault" / "raw_batch").stat().st_mode & 0o777
        self.assertEqual(mode, 0o600)

    def test_create(self):
        self.init_vault()
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stderr)
        lines = dict(line.split(": ", 1) for line in result.stdout.strip().splitlines())
        batch_id = lines["password_batch"].strip('"')
        self.assertTrue(lines["initial_password_hash"].startswith('"$6$'))
        self.assertEqual(self.index()["current"], batch_id)
        encrypted = (self.store / f"{batch_id}.vault").read_text()
        self.assertTrue(encrypted.startswith(new_raw_batch.VAULT_HEADER))
        # Only the ID and the hash are printed: two lines on stdout, and the
        # password is in neither stream.
        self.assertEqual(len(result.stdout.strip().splitlines()), 2)
        self.assertNotIn("shown once", result.stderr)

    def test_import_hash_and_no_plaintext(self):
        self.init_vault()
        result = self.run_script("--import", "raw-2026-11-17-manual", stdin=PASSWORD + "\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(self.index()["current"])
        for path in self.store.iterdir():
            self.assertNotIn(PASSWORD, path.read_text())
        self.assertNotIn(PASSWORD, result.stdout + result.stderr)
        hashed = self.run_script("--hash", "raw-2026-11-17-manual").stdout
        value = hashed.split('initial_password_hash: "')[1].split('"')[0]
        salt = value.split("$")[2]
        self.assertEqual(sha512_crypt(PASSWORD, salt), value)

    def test_import_rejects_other_characters(self):
        self.init_vault()
        for bad in ("abcdefghijklmn!op", "abc def 123456789", ""):
            with self.subTest(bad=bad):
                result = self.run_script("--import", "raw-2026-11-17-bad", stdin=bad + "\n")
                self.assertEqual(result.returncode, 1)

    def test_import_short_password_recorded(self):
        self.init_vault()
        result = self.run_script("--import", "raw-2026-11-17-short", stdin="abc123\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("RN-ACC-08", result.stderr)
        self.assertIs(self.index()["batches"]["raw-2026-11-17-short"]["meets_min_length"], False)
        self.assertIn("under 15 characters", self.run_script("--list").stdout)
        self.run_script("--import", "raw-2026-11-17-long", stdin=PASSWORD + "\n")
        self.assertIs(self.index()["batches"]["raw-2026-11-17-long"]["meets_min_length"], True)

    def test_created_batch_meets_min_length(self):
        self.init_vault()
        self.run_script()
        entry = next(iter(self.index()["batches"].values()))
        self.assertIs(entry["meets_min_length"], True)

    def test_ids_never_reused_and_retire_rules(self):
        self.init_vault()
        self.run_script("--import", "raw-2026-11-17-manual", "--current", stdin=PASSWORD + "\n")
        self.assertEqual(self.run_script("--retire", "raw-2026-11-17-manual").returncode, 1)
        self.assertEqual(self.run_script().returncode, 0)
        retired = self.run_script("--retire", "raw-2026-11-17-manual")
        self.assertEqual(retired.returncode, 0, retired.stderr)
        self.assertFalse((self.store / "raw-2026-11-17-manual.vault").exists())
        again = self.run_script("--import", "raw-2026-11-17-manual", stdin=PASSWORD + "\n")
        self.assertEqual(again.returncode, 1)
        self.assertEqual(self.run_script("--list").returncode, 0)

    def test_missing_meets_min_length_is_an_error(self):
        self.init_vault()
        self.run_script()
        index = self.index()
        batch_id = index["current"]
        del index["batches"][batch_id]["meets_min_length"]
        new_raw_batch.save_index(self.store, index)
        listed = self.run_script("--list")
        self.assertEqual(listed.returncode, 1)
        self.assertIn("no meets_min_length", listed.stderr)
        for args in (["--set-current", batch_id], ["--hash", batch_id]):
            with self.subTest(args=args):
                self.assertEqual(self.run_script(*args).returncode, 1)

    def test_list_flags_unencrypted_file(self):
        self.init_vault()
        self.run_script()
        (self.store / "stray.vault").write_text("not encrypted\n")
        result = self.run_script("--list")
        self.assertEqual(result.returncode, 1)
        self.assertIn("NOT encrypted", result.stderr)


if __name__ == "__main__":
    unittest.main()
