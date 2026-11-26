"""Fixture tests for scripts/check_raw_confirmation.py.

Standard library and PyYAML only. Each file in
tests/fixtures/raw-confirmations/ states what it expects in its header:

    # expect-exit: 1
    # expect: fail | RN-ACC-07 | sudo_nopasswd   severity | clause | field
    # expect-value: macs = ["52:54:00:12:34:56"]  a JSON value under "values"

A fixture expecting exit 0 must have no "fail" finding, and one expecting
exit 1 at least one. Adding a fixture needs no change here.

    python3 tests/run_tests.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "check_raw_confirmation.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "raw-confirmations"


def run(*args, stdin: bytes | None = None):
    result = subprocess.run([sys.executable, str(SCRIPT), *args], input=stdin,
                            capture_output=True)
    return result.returncode, json.loads(result.stdout)


def expectations(path: Path) -> dict:
    found = {"exit": None, "findings": [], "values": []}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        text = line.lstrip("# ")
        if text.startswith("expect-exit:"):
            found["exit"] = int(text.split(":", 1)[1])
        elif text.startswith("expect:"):
            severity, clause, field = (part.strip() for part in text.split(":", 1)[1].split("|"))
            found["findings"].append((severity, clause, field))
        elif text.startswith("expect-value:"):
            name, value = text.split(":", 1)[1].split("=", 1)
            found["values"].append((name.strip(), json.loads(value)))
    return found


class Fixtures(unittest.TestCase):
    def test_fixtures_exist(self):
        names = [p.name for p in FIXTURES.glob("*.yml")]
        self.assertTrue(any(n.startswith("pass-") for n in names))
        self.assertTrue(any(n.startswith("fail-") for n in names))

    def test_every_fixture(self):
        for path in sorted(FIXTURES.glob("*.yml")):
            expected = expectations(path)
            with self.subTest(fixture=path.name):
                self.assertIsNotNone(expected["exit"], "fixture has no expect-exit line")
                status, result = run(str(path))
                self.assertEqual(status, expected["exit"], json.dumps(result["findings"], indent=1))
                self.assertEqual(result["result"], {0: "pass", 1: "fail", 2: "error"}[status])
                found = {(f["severity"], f["clause"], f["field"]) for f in result["findings"]}
                for finding in expected["findings"]:
                    self.assertIn(finding, found)
                fails = [f for f in result["findings"] if f["severity"] == "fail"]
                if status == 0:
                    self.assertEqual(fails, [])
                if status == 1:
                    self.assertTrue(fails)
                for name, value in expected["values"]:
                    self.assertEqual(result["values"][name], value)


class Values(unittest.TestCase):
    def test_pass_values_are_normalized(self):
        status, result = run(str(FIXTURES / "pass-0.3.1-quoted.yml"))
        self.assertEqual(status, 0)
        values = result["values"]
        self.assertEqual(values["hostname"], "deb13-vt-c3d4")
        self.assertEqual(values["contract"], "0.3.1")
        self.assertIs(values["sudo"], True)
        self.assertIs(values["sudo_nopasswd"], False)
        self.assertEqual(values["ssh_port"], 22)
        self.assertEqual(values["macs"], ["02:00:00:ab:00:01"])
        self.assertEqual(values["addresses"], {"ipv4": ["203.0.113.10"], "ipv6": []})
        self.assertEqual(values["ssh_host_keys"][0]["type"], "ssh-ed25519")

    def test_real_node_fails_on_its_version(self):
        status, result = run(str(FIXTURES / "fail-real-deb13-vt-0001-contract-0.1.0.yml"))
        self.assertEqual(status, 1)
        version = [f for f in result["findings"] if f["field"] == "contract"]
        self.assertEqual(len(version), 1)
        self.assertIn("0.1.0 is not supported", version[0]["message"])
        self.assertEqual(result["values"]["machine_id"], "1970010100000000000000000000ab01")


class Options(unittest.TestCase):
    def test_stdin(self):
        status, result = run("-", stdin=(FIXTURES / "pass-0.3.0.yml").read_bytes())
        self.assertEqual((status, result["result"]), (0, "pass"))

    def test_expected_port_and_user(self):
        path = str(FIXTURES / "pass-0.3.0.yml")
        status, result = run(path, "--port", "2222")
        self.assertEqual(status, 1)
        self.assertIn(("RN-SSH-01", "ssh_port"),
                      {(f["clause"], f["field"]) for f in result["findings"]})
        status, _ = run(path, "--user", "bootstrap")
        self.assertEqual(status, 1)

    def test_extra_installer_default(self):
        status, _ = run(str(FIXTURES / "pass-0.3.0.yml"), "--installer-default", "deb13-vt-a1b2")
        self.assertEqual(status, 1)

    def test_missing_file_is_unreadable(self):
        with tempfile.TemporaryDirectory() as tmp:
            status, result = run(str(Path(tmp) / "absent.yml"))
        self.assertEqual((status, result["result"]), (2, "error"))

    def test_not_utf8_is_unreadable(self):
        status, result = run("-", stdin=b"\xff\xfe\x00bad")
        self.assertEqual(status, 2)

    def test_empty_input_fails(self):
        status, result = run("-", stdin=b"")
        self.assertEqual(status, 1)


if __name__ == "__main__":
    unittest.main()
