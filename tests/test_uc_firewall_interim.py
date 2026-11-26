"""shared/vars/uc_firewall_interim.yml gives uc_firewall the rules it had.

Until uc-controller switches to steelcj.foomuuri, the client inventory's
per-stage firewall values, shaped for that role, are turned into the
firewall_rules list shared/roles/uc_firewall reads. These tests template that
list on localhost, with no inventory and no host, and compare it with the
rules the firewall_rules_<stage> lists gave before the rename.

    python3 tests/run_tests.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
VARS = REPO / "shared/vars/uc_firewall_interim.yml"

SSH = {"port": 22, "sources": []}
NORMALIZE = [{"name": 9100, "protocol": "tcp", "sources": ["198.51.100.0/24"]}]
SPECIALIZE = [{"name": "http", "protocol": "tcp", "sources": ["0.0.0.0/0"]}]


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible not on PATH")
class Interim(unittest.TestCase):
    def rules(self, stages, **values):
        with tempfile.TemporaryDirectory() as tmp:
            play = Path(tmp) / "play.yml"
            play.write_text(yaml.safe_dump([{
                "hosts": "localhost", "gather_facts": False, "become": False,
                "vars_files": [str(VARS)],
                "vars": {"uc_firewall_stages": stages, **values},
                "tasks": [{"ansible.builtin.copy": {
                    "content": "{{ firewall_rules | to_json }}", "dest": f"{tmp}/rules.json"}}],
            }]))
            env = dict(os.environ, ANSIBLE_CONFIG=str(REPO / "ansible.cfg"))
            result = subprocess.run(
                ["ansible-playbook", "-i", "localhost,", "-c", "local", str(play)],
                capture_output=True, text=True, env=env, cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return json.loads((Path(tmp) / "rules.json").read_text())

    def test_1_the_rules_are_as_before(self):
        # What firewall_rules_onboard, _normalize and _specialize gave.
        self.assertEqual(
            self.rules(["onboard", "normalize", "specialize"], firewall_onboard_ssh=SSH,
                       firewall_normalize_services=NORMALIZE, firewall_specialize_services=SPECIALIZE),
            [{"name": "allow-ssh", "port": 22, "protocol": "tcp"},
             {"name": "allow-9100", "port": 9100, "protocol": "tcp", "source": "198.51.100.0/24"},
             {"name": "allow-http", "port": 80, "protocol": "tcp", "source": "0.0.0.0/0"}])

    def test_2_only_the_stages_listed(self):
        self.assertEqual(
            self.rules(["onboard"], firewall_onboard_ssh=SSH, firewall_normalize_services=NORMALIZE),
            [{"name": "allow-ssh", "port": 22, "protocol": "tcp"}])

    def test_3_one_rule_per_source(self):
        self.assertEqual(
            self.rules(["onboard"], firewall_onboard_ssh={"port": 22, "sources": ["0.0.0.0/0", "2001:db8::/32"]}),
            [{"name": "allow-ssh", "port": 22, "protocol": "tcp", "source": "0.0.0.0/0"},
             {"name": "allow-ssh", "port": 22, "protocol": "tcp", "source": "2001:db8::/32"}])

    def test_4_absent_and_defaults(self):
        self.assertEqual(
            self.rules(["normalize"], firewall_normalize_services=[
                {"name": "https", "state": "absent"}, {"name": 5353, "protocol": "udp"}, {"name": "https"}]),
            [{"name": "allow-5353", "port": 5353, "protocol": "udp"},
             {"name": "allow-https", "port": 443, "protocol": "tcp"}])

    def test_5_no_ssh_value_gives_no_ssh_rule(self):
        # So uc_firewall still refuses to enable the firewall.
        self.assertEqual(self.rules(["onboard", "normalize"], firewall_normalize_services=NORMALIZE),
                         [{"name": "allow-9100", "port": 9100, "protocol": "tcp", "source": "198.51.100.0/24"}])


if __name__ == "__main__":
    unittest.main()
