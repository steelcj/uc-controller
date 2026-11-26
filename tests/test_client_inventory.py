"""Tests for the client inventory template and its tools:
scripts/inventory-args, scripts/new-inventory, scripts/check_inventory.py and
the template's pre-commit hook, and for uc_known_hosts_file resolving to the
same file at every stage.

Every client inventory here is made with scripts/new-inventory in a temporary
directory, with raw/incus.yml deleted so that nothing asks an Incus server
what exists. Secret-shaped test values (a vault file, a crypt hash, a private
key) are made at run time, never written in this file.

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
SCRIPTS = REPO / "scripts"
DEFAULTS = REPO / "inventory-defaults"
TEMPLATE = REPO / "inventory-template"

# A run of git that ignores the operator's own configuration.
GIT_ENV = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.org",
           "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.org"}


def run(argv, cwd=None, env=None, stdin=None):
    return subprocess.run([str(a) for a in argv], cwd=cwd, capture_output=True, text=True,
                          env=dict(os.environ, **GIT_ENV, **(env or {})), input=stdin)


def new_client(parent: Path, name: str = "example.org") -> Path:
    """A client inventory made with scripts/new-inventory, without the Incus plugin."""
    path = parent / name
    result = run([sys.executable, SCRIPTS / "new-inventory", path])
    assert result.returncode == 0, result.stderr
    (path / "raw" / "incus.yml").unlink()
    return path


def write_yaml(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False))
    return path


def tracked_files(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*")
                  if p.is_file() and ".git" not in p.relative_to(root).parts)


class TempDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()


class InventoryArgs(TempDir):
    def args(self, *stages, client=None):
        return run([sys.executable, SCRIPTS / "inventory-args", client or self.client, *stages])

    def setUp(self):
        super().setUp()
        self.client = new_client(self.root)

    def test_defaults_first_then_client_in_stage_order(self):
        result = self.args("raw", "onboard/dev")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), [
            "-i", str(DEFAULTS / "raw"), "-i", str(DEFAULTS / "onboard"),
            "-i", str(self.client / "raw"), "-i", str(self.client / "onboard/dev")])

    def test_order_follows_the_stages_given(self):
        result = self.args("onboard/dev", "normalized/dev")
        self.assertEqual(result.stdout.split()[1::2], [
            str(DEFAULTS / "onboard"), str(DEFAULTS / "normalized"),
            str(self.client / "onboard/dev"), str(self.client / "normalized/dev")])

    def test_a_defaults_directory_is_given_once(self):
        result = self.args("onboard/dev", "onboard/stage")
        self.assertEqual(result.stdout.split()[1::2], [
            str(DEFAULTS / "onboard"), str(self.client / "onboard/dev"),
            str(self.client / "onboard/stage")])

    def test_refusals(self):
        cases = {
            "unknown stage": (["converge"], "unknown stage"),
            "onboard without environment": (["onboard"], "is not raw, onboard/<environment>"),
            "raw with environment": (["raw/dev"], "is not raw, onboard/<environment>"),
            "dot dot": (["onboard/.."], "is not raw"),
            "missing environment": (["onboard/prod"], "has no onboard/prod/ directory"),
            "twice": (["raw", "raw"], "given twice"),
        }
        for name, (stages, message) in cases.items():
            with self.subTest(case=name):
                result = self.args(*stages)
                self.assertEqual(result.returncode, 2)
                self.assertIn(message, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_missing_client(self):
        result = self.args("raw", client=self.root / "nowhere")
        self.assertEqual(result.returncode, 2)
        self.assertIn("is not a directory", result.stderr)

    def test_whitespace_is_refused(self):
        spaced = new_client(self.root, "with space")
        result = self.args("raw", client=spaced)
        self.assertEqual(result.returncode, 2)
        self.assertIn("contains whitespace", result.stderr)

    def test_usage(self):
        result = run([sys.executable, SCRIPTS / "inventory-args"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("Print the -i options", result.stderr)


class NewInventory(TempDir):
    def test_makes_a_repository_from_the_template(self):
        client = self.root / "example.org"
        result = run([sys.executable, SCRIPTS / "new-inventory", client])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(tracked_files(client), tracked_files(TEMPLATE))
        self.assertTrue((client / ".git").is_dir())
        self.assertEqual(run(["git", "config", "core.hooksPath"], cwd=client).stdout.strip(),
                         ".githooks")
        self.assertTrue(os.access(client / ".githooks/pre-commit", os.X_OK))
        self.assertEqual(run(["git", "remote"], cwd=client).stdout, "")
        self.assertNotEqual(run(["git", "rev-parse", "--verify", "HEAD"], cwd=client).returncode, 0)
        self.assertEqual((client / "ssh/known_hosts").read_text(), "")

    def test_an_empty_directory_is_accepted(self):
        client = self.root / "empty"
        client.mkdir()
        self.assertEqual(run([sys.executable, SCRIPTS / "new-inventory", client]).returncode, 0)

    def test_refuses_a_path_that_exists_and_is_not_empty(self):
        occupied = self.root / "occupied"
        occupied.mkdir()
        (occupied / "notes.txt").write_text("keep me\n")
        a_file = self.root / "a-file"
        a_file.write_text("x\n")
        for path in (occupied, a_file):
            with self.subTest(path=path.name):
                result = run([sys.executable, SCRIPTS / "new-inventory", path])
                self.assertEqual(result.returncode, 2)
                self.assertIn("exists and is not an empty directory", result.stderr)
        self.assertEqual(sorted(p.name for p in occupied.iterdir()), ["notes.txt"])


@unittest.skipUnless(shutil.which("yamllint"), "yamllint not on PATH")
class PreCommitHook(TempDir):
    def setUp(self):
        super().setUp()
        self.client = new_client(self.root)
        run(["git", "add", "-A"], cwd=self.client)

    def commit(self, env):
        return run(["git", "commit", "-q", "-m", "test"], cwd=self.client, env=env)

    def test_refused_until_uc_controller_is_set(self):
        result = subprocess.run(["git", "commit", "-q", "-m", "test"], cwd=self.client,
                                capture_output=True, text=True,
                                env={k: v for k, v in dict(os.environ, **GIT_ENV).items()
                                     if k != "UC_CONTROLLER"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("set UC_CONTROLLER to the uc-controller checkout", result.stderr)

    def test_passes_on_the_template(self):
        result = self.commit({"UC_CONTROLLER": str(REPO)})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_refuses_logic(self):
        write_yaml(self.client / "onboard/dev/group_vars/extra.yml", {"ansible_user": "root"})
        run(["git", "add", "-A"], cwd=self.client)
        result = self.commit({"UC_CONTROLLER": str(REPO)})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("sets ansible_user", result.stderr)


class CheckInventory(TempDir):
    def setUp(self):
        super().setUp()
        self.client = new_client(self.root)

    def check(self):
        return run([sys.executable, SCRIPTS / "check_inventory.py", self.client])

    def assert_refused(self, message):
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(message, result.stderr)

    def assert_clean(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def admit(self, host="example-vt-0001", known=True, **host_vars):
        host_vars = {"ansible_host": "203.0.113.10", "raw_node_batch": "raw-1970-01-01-01", **host_vars}
        write_yaml(self.client / "raw/admitted.yml", {"admitted": {"hosts": {host: host_vars}}})
        if known:
            key = self.root / "host_key"
            if not key.exists():
                run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", key])
            public = " ".join(Path(f"{key}.pub").read_text().split()[:2])
            with (self.client / "ssh/known_hosts").open("a") as handle:
                handle.write(f"{host} {public}\n")

    def test_the_template_is_clean(self):
        self.assert_clean()

    def test_forbidden_variables_are_a_named_constant(self):
        source = (SCRIPTS / "check_inventory.py").read_text()
        self.assertIn("# Variables that indicate logic leaked into a client inventory.\n"
                      "FORBIDDEN_VARIABLES = (", source)

    def test_forbidden_variables_under_group_vars_and_host_vars(self):
        for variable in ("ansible_connection", "ansible_user", "ansible_ssh_common_args",
                         "ansible_ssh_host_key_checking", "ansible_become_password"):
            for relative in ("raw/group_vars/all.yml", "onboard/dev/group_vars/onboarded.yml",
                             "raw/group_vars/admitted/main.yml", "normalized/stage/host_vars/web1.yml"):
                with self.subTest(variable=variable, file=relative):
                    path = self.client / relative
                    original = path.read_text() if path.exists() else None
                    data = (yaml.safe_load(original) if original else None) or {}
                    write_yaml(path, {**data, variable: "x"})
                    try:
                        self.assert_refused(f"{relative}: sets {variable}")
                    finally:
                        if original is None:
                            path.unlink()
                        else:
                            path.write_text(original)
        self.assert_clean()

    def test_connection_variables_per_host_in_generated_hosts_files(self):
        contract = {"ansible_connection": "ssh", "ansible_user": "initial",
                    "ansible_ssh_common_args": "-o IdentitiesOnly=yes",
                    "ansible_ssh_host_key_checking": True}
        self.admit(**contract)
        write_yaml(self.client / "raw/discovered.yml",
                   {"discovered": {"hosts": {"disc-203-0-113-20": {"ansible_host": "203.0.113.20",
                                                                    **contract}}}})
        for stage, group in (("onboard/dev", "onboarded"), ("normalized/stage", "normalized")):
            write_yaml(self.client / stage / "hosts.yml",
                       {group: {"hosts": {f"example-{group}": {"ansible_host": "203.0.113.30",
                                                                 **contract}}}})
        self.assert_clean()

    def test_forbidden_variables_on_a_group_in_a_hosts_file(self):
        write_yaml(self.client / "onboard/dev/hosts.yml",
                   {"onboarded": {"hosts": {}, "vars": {"ansible_user": "root"}}})
        self.assert_refused("sets ansible_user on group onboarded")

    def test_vault_file(self):
        header = "$" + "ANSIBLE_VAULT;1.1;AES256"
        body = "\n".join(os.urandom(40).hex() for _ in range(3))
        (self.client / "raw/group_vars/secrets.yml").write_text(f"{header}\n{body}\n")
        self.assert_refused("raw/group_vars/secrets.yml: holds an ansible-vault header")

    @unittest.skipUnless(shutil.which("openssl"), "openssl not on PATH")
    def test_crypt_hash(self):
        made = run(["openssl", "passwd", "-6", "-stdin"], stdin="made up for this test\n")
        self.assertEqual(made.returncode, 0, made.stderr)
        write_yaml(self.client / "onboard/dev/group_vars/all.yml",
                   {"uc_client_inventory": True, "initial_password_hash": made.stdout.strip()})
        self.assert_refused("onboard/dev/group_vars/all.yml: holds a crypt hash")

    @unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen not on PATH")
    def test_private_key(self):
        key = self.root / "made_up_key"
        run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", key])
        shutil.copy(key, self.client / "ssh" / "id_ed25519")
        self.assert_refused("ssh/id_ed25519: holds a private key block")

    def test_lookups(self):
        for expression in ("{{ lookup('ansible.builtin.file', '/etc/hostname') }}",
                           "{{ query('ansible.builtin.env', 'HOME') }}",
                           "{{ q('ansible.builtin.env', 'HOME') }}",
                           "{{ lookup('uc_secret', 'batches/raw-1970-01-01-01', key='initial_password') }}",
                           "{% if lookup('ansible.builtin.env', 'X') %}a{% endif %}"):
            with self.subTest(expression=expression):
                write_yaml(self.client / "raw/group_vars/all.yml",
                           {"uc_client_inventory": True, "value": expression})
                self.assert_refused("raw/group_vars/all.yml: uses a lookup")

    def test_the_word_lookup_outside_a_template_is_fine(self):
        path = self.client / "raw/group_vars/all.yml"
        path.write_text(path.read_text() + "# No lookup here: uc_secret is used only by uc-controller.\n")
        self.assert_clean()

    def test_admitted_host_needs_a_batch(self):
        for host_vars in ({"raw_node_batch": ""}, {"raw_node_batch": None}):
            with self.subTest(host_vars=host_vars):
                (self.client / "ssh/known_hosts").write_text("")
                self.admit(**host_vars)
                self.assert_refused("admitted host example-vt-0001 has no raw_node_batch")
        write_yaml(self.client / "raw/admitted.yml",
                   {"admitted": {"hosts": {"example-vt-0002": None}}})
        self.assert_refused("admitted host example-vt-0002 has no raw_node_batch")

    def test_admitted_host_needs_its_host_keys(self):
        self.admit(known=False)
        self.assert_refused("admitted host example-vt-0001 has no entry in ssh/known_hosts")
        self.admit()
        self.assert_clean()

    @unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen not on PATH")
    def test_hashed_known_hosts_entry(self):
        self.admit()
        known = self.client / "ssh/known_hosts"
        run(["ssh-keygen", "-H", "-f", known])
        Path(f"{known}.old").unlink()
        self.assertNotIn("example-vt-0001", known.read_text())
        self.assert_clean()

    def test_invalid_yaml(self):
        (self.client / "raw/group_vars/all.yml").write_text("a: [\n")
        self.assert_refused("raw/group_vars/all.yml: is not valid YAML near line")

    def test_bad_arguments(self):
        result = run([sys.executable, SCRIPTS / "check_inventory.py", self.root / "nowhere"])
        self.assertEqual(result.returncode, 2)


@unittest.skipUnless(shutil.which("ansible"), "ansible not on PATH")
class KnownHostsFile(TempDir):
    """uc_known_hosts_file resolves to the client's ssh/known_hosts for every host,
    with each stage on its own and in the combined runs the playbooks use."""

    HOSTS = {"raw": "example-vt-0001", "onboard/dev": "example-onb-dev",
             "onboard/stage": "example-onb-stage", "normalized/dev": "example-norm-dev",
             "normalized/stage": "example-norm-stage"}

    def setUp(self):
        super().setUp()
        self.client = new_client(self.root)
        write_yaml(self.client / "raw/admitted.yml", {"admitted": {"hosts": {
            self.HOSTS["raw"]: {"ansible_host": "203.0.113.10", "raw_node_batch": "raw-1970-01-01-01"}}}})
        for number, stage in enumerate(("onboard/dev", "onboard/stage", "normalized/dev",
                                        "normalized/stage")):
            group = "onboarded" if stage.startswith("onboard") else "normalized"
            write_yaml(self.client / stage / "hosts.yml", {group: {"hosts": {
                self.HOSTS[stage]: {"ansible_host": f"203.0.113.{30 + number}"}}}})
        # The admitted host's become password is a uc_secret lookup, which
        # Ansible evaluates even for debug; give it a made-up batch file.
        self.secrets = self.root / "secrets"
        (self.secrets / "batches").mkdir(parents=True)
        self.secrets.chmod(0o700)
        (self.secrets / "batches").chmod(0o700)
        batch = self.secrets / "batches/raw-1970-01-01-01.yml"
        batch.write_text('initial_password: "made up for this test"\n')
        batch.chmod(0o600)

    def resolve(self, *stages) -> dict:
        args = run([sys.executable, SCRIPTS / "inventory-args", self.client, *stages])
        self.assertEqual(args.returncode, 0, args.stderr)
        # onboard_ssh_private_key_file is an onboard stage value, which the
        # admitted group's key setting refers to; raw alone does not have it.
        extra = [] if "onboard/dev" in stages else ["-e", "onboard_ssh_private_key_file=~/.ssh/unused"]
        result = run(["ansible", "all", *args.stdout.split(), "-m", "ansible.builtin.debug",
                      "-a", "var=uc_known_hosts_file", *extra], cwd=REPO,
                     env={"UC_SECRETS_DIR": str(self.secrets), "ANSIBLE_BECOME": "false",
                          "ANSIBLE_LOAD_CALLBACK_PLUGINS": "1", "ANSIBLE_STDOUT_CALLBACK": "json",
                          "ANSIBLE_NOCOLOR": "1"})
        self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])
        # The json callback's document comes first; ansible.cfg's profile_tasks
        # callback prints its recap after it.
        document, _ = json.JSONDecoder().raw_decode(result.stdout[result.stdout.index("{"):])
        hosts = document["plays"][0]["tasks"][0]["hosts"]
        return {host: value.get("uc_known_hosts_file") for host, value in hosts.items()}

    def test_every_stage_and_combination_gives_the_same_file(self):
        expected = str((self.client / "ssh/known_hosts").resolve())
        for stages in (["raw"], ["onboard/dev"], ["onboard/stage"], ["normalized/dev"],
                       ["normalized/stage"], ["raw", "onboard/dev"], ["onboard/dev", "normalized/dev"]):
            with self.subTest(stages=stages):
                resolved = self.resolve(*stages)
                self.assertEqual(sorted(resolved), sorted(self.HOSTS[s] for s in stages))
                self.assertEqual(set(resolved.values()), {expected}, resolved)


if __name__ == "__main__":
    unittest.main()
