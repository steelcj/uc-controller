"""The Foomuuri fragments each stage writes, offline.

10_onboard.yml, 20_normalize.yml and 30_specialize.yml each call
steelcj.foomuuri for one fragment: 10-base, 20-normalize and 30-specialize.
These tests read each call's variables from the playbook as it is, with the
play's own variables, and render the role's template, from the vendored
roles/steelcj.foomuuri, on localhost with the client inventory template's
firewall values. They check what each fragment accepts, that each call keeps
the other two fragments, and that a stage with no service removes its
fragment. No host is contacted.

The role's own checks, the play's refusals and the result on a node are
tested on a throwaway node, as the step report of the handover work records.

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
ROLE = REPO / "roles/steelcj.foomuuri"
TEMPLATE = REPO / "inventory-template"
PLAYBOOKS = {
    "10-base": REPO / "ingress/playbooks/10_onboard.yml",
    "20-normalize": REPO / "converge/playbooks/20_normalize.yml",
    "30-specialize": REPO / "converge/playbooks/30_specialize.yml",
}
FRAGMENTS = sorted(PLAYBOOKS)


def load(path: Path):
    return yaml.safe_load(path.read_text())


def foomuuri_call(playbook: Path) -> tuple[dict, dict]:
    """(the play's vars, the call's vars) for the one steelcj.foomuuri call."""
    found = []
    for play in load(playbook):
        for role in play.get("roles") or []:
            if isinstance(role, dict) and role.get("role") == "steelcj.foomuuri":
                found.append((play.get("vars") or {}, role.get("vars") or {}))
        for task in play.get("tasks") or []:
            include = task.get("ansible.builtin.include_role") or {}
            if include.get("name") == "steelcj.foomuuri":
                found.append((play.get("vars") or {}, task.get("vars") or {}))
    assert len(found) == 1, f"{playbook} calls steelcj.foomuuri {len(found)} times"
    return found[0]


@unittest.skipUnless(shutil.which("ansible-playbook"), "Ansible not on PATH")
class Fragments(unittest.TestCase):
    def render(self, fragment: str, version: str = "0.27", **client) -> dict:
        """The fragment's text, state and kept fragments, as the role would write them."""
        play_vars, call_vars = foomuuri_call(PLAYBOOKS[fragment])
        values = {**load(ROLE / "defaults/main.yml"), **load(ROLE / "vars/main.yml"),
                  **play_vars, **call_vars, **client,
                  # What the role reads from the node with foomuuri --version.
                  "foomuuri_version": {"stdout": version}}
        with tempfile.TemporaryDirectory() as tmp:
            play = Path(tmp) / "play.yml"
            play.write_text(yaml.safe_dump([{
                "hosts": "localhost", "gather_facts": False, "become": False, "vars": values,
                "tasks": [
                    {"ansible.builtin.copy": {
                        "dest": f"{tmp}/call.json",
                        "content": "{{ {'fragment': foomuuri_fragment, 'state': foomuuri_fragment_state,"
                                   " 'keep': foomuuri_keep_fragments,"
                                   " 'require_ssh': foomuuri_require_ssh} | to_json }}"}},
                    {"ansible.builtin.template": {"src": str(ROLE / "templates/foomuuri.conf.j2"),
                                                  "dest": f"{tmp}/fragment.conf"}},
                ]}]))
            env = dict(os.environ, ANSIBLE_CONFIG=str(REPO / "ansible.cfg"))
            result = subprocess.run(["ansible-playbook", "-i", "localhost,", "-c", "local", str(play)],
                                    capture_output=True, text=True, env=env, cwd=tmp)
            self.assertEqual(result.returncode, 0, result.stdout[-3000:] + result.stderr[-2000:])
            call = json.loads((Path(tmp) / "call.json").read_text())
            text = (Path(tmp) / "fragment.conf").read_text()
        rules = [line.strip() for line in text.splitlines()
                 if line.startswith("  ") and not line.strip().startswith("#")]
        return {**call, "text": text, "rules": rules}

    def template_values(self, *files: str) -> dict:
        merged = {}
        for relative in files:
            merged.update(load(TEMPLATE / relative) or {})
        return merged

    def test_each_playbook_writes_its_own_fragment_and_keeps_the_others(self):
        for fragment, playbook in PLAYBOOKS.items():
            with self.subTest(fragment=fragment):
                rendered = self.render(fragment, **self.template_values(
                    "onboard/dev/group_vars/all.yml", "normalized/dev/group_vars/all.yml",
                    "normalized/dev/group_vars/webservers.yml"))
                self.assertEqual(rendered["fragment"], fragment)
                self.assertEqual(sorted(rendered["keep"] + [fragment]), FRAGMENTS)
                self.assertIs(rendered["require_ssh"], True)
                self.assertNotIn("uc_firewall", playbook.read_text().replace("uc_firewall had", ""))

    def test_onboard_writes_ssh_from_firewall_onboard_ssh(self):
        dev = self.render("10-base", **self.template_values("onboard/dev/group_vars/all.yml"))
        self.assertEqual(dev["state"], "present")
        self.assertIn("zone {", dev["text"])
        self.assertEqual(dev["rules"], ["localhost", "public eth* en* wl*", "dhcp-client",
                                        "dhcpv6-client", "ping", "ssh", "accept"])
        stage = self.render("10-base", version="0.33",
                            **self.template_values("onboard/stage/group_vars/all.yml"))
        self.assertIn("ssh saddr 0.0.0.0/0", stage["rules"])
        self.assertIn("public *", stage["rules"])
        several = self.render("10-base", firewall_onboard_ssh={
            "port": 22, "sources": ["198.51.100.10/32", "2001:db8::/32"]})
        self.assertIn("ssh saddr 198.51.100.10/32 2001:db8::/32", several["rules"])

    def test_normalize_writes_its_services_and_no_ssh(self):
        rendered = self.render("20-normalize", **self.template_values(
            "onboard/dev/group_vars/all.yml", "normalized/dev/group_vars/all.yml"))
        self.assertEqual(rendered["state"], "present")
        self.assertNotIn("zone {", rendered["text"])
        self.assertEqual(rendered["rules"], ["tcp 9100 saddr 198.51.100.0/24"])
        mixed = self.render("20-normalize", firewall_normalize_services=[
            {"name": "https", "state": "absent"}, {"name": 5353, "protocol": "udp"}, {"name": "https"}])
        self.assertEqual(mixed["rules"], ["udp 5353", "https"])

    def test_specialize_writes_the_groups_services(self):
        rendered = self.render("30-specialize",
                               **self.template_values("normalized/dev/group_vars/webservers.yml"))
        self.assertEqual(rendered["state"], "present")
        self.assertEqual(rendered["rules"], ["http saddr 0.0.0.0/0"])

    def test_a_stage_with_no_service_removes_its_fragment(self):
        for fragment, variable in (("20-normalize", "firewall_normalize_services"),
                                   ("30-specialize", "firewall_specialize_services")):
            for case, value in (("undefined", None), ("empty", []),
                                ("only absent", [{"name": "http", "state": "absent"}])):
                with self.subTest(fragment=fragment, case=case):
                    client = {} if value is None else {variable: value}
                    self.assertEqual(self.render(fragment, **client)["state"], "absent")


if __name__ == "__main__":
    unittest.main()
