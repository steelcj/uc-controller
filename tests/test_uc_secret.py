"""Tests for shared/plugins/lookup/uc_secret.py.

Every test makes its own secrets root in a temporary directory and names it
with UC_SECRETS_DIR, so ~/.secrets/ is never read. The values are test
values, made up here.

Needs Ansible importable (the controller's Ansible virtual environment);
skipped otherwise.

    python3 tests/run_tests.py
"""
from __future__ import annotations

import inspect
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "shared/plugins/lookup/uc_secret.py"
VALUE = "test value, made up for this test only"

try:
    import ansible  # noqa: F401
    from ansible.errors import AnsibleLookupError
except ImportError:  # pragma: no cover
    ansible = None


def load_plugin():
    """The plugin as Ansible loads it, so its documented options are registered."""
    from ansible.plugins.loader import lookup_loader
    lookup_loader.add_directory(str(PLUGIN.parent))
    return lookup_loader.get("uc_secret")


@unittest.skipUnless(ansible is not None, "Ansible is not importable")
class UcSecret(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "uc"
        self.root.mkdir(mode=0o700)
        (self.root / "batches").mkdir(mode=0o700)
        self.file = self.write("batches/raw-1970-01-01-01.yml",
                               f'initial_password: "{VALUE}"\nother: 3\nempty: ""\n')
        self.plugin = load_plugin()
        patcher = mock.patch.dict(os.environ, {"UC_SECRETS_DIR": str(self.root)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, relative: str, text: str, mode: int = 0o600) -> Path:
        path = self.root / relative
        path.write_text(text, encoding="utf-8")
        path.chmod(mode)
        return path

    def read(self, path="batches/raw-1970-01-01-01", key="initial_password"):
        return self.plugin.run([path], variables={}, key=key)

    def refused(self, expected: str, path="batches/raw-1970-01-01-01", key="initial_password"):
        with self.assertRaises(AnsibleLookupError) as caught:
            self.read(path, key)
        message = str(caught.exception)
        self.assertIn(expected, message)
        self.assertNotIn(VALUE, message)
        return message

    def test_good_read(self):
        self.assertEqual(self.read(), [VALUE])

    def test_default_root_is_home_secrets_uc(self):
        with mock.patch.dict(os.environ, {}, clear=True), \
                mock.patch.object(Path, "home", return_value=Path("/nonexistent-home")):
            module = inspect.getmodule(type(self.plugin))
            self.assertEqual(module.secrets_root(), Path("/nonexistent-home/.secrets/uc/fleet"))

    def test_absolute_path(self):
        self.refused("must be relative", path=str(self.file.with_suffix("")))

    def test_home_path(self):
        self.refused("must be relative", path="~/batches/raw-1970-01-01-01")

    def test_dot_dot(self):
        self.refused("must not contain '..'", path="batches/../batches/raw-1970-01-01-01")

    def test_empty_part(self):
        self.refused("empty parts", path="batches//raw-1970-01-01-01")

    def test_symlink_out_of_the_root(self):
        outside = Path(self.tmp.name) / "outside.yml"
        outside.write_text(f'initial_password: "{VALUE}"\n')
        outside.chmod(0o600)
        (self.root / "batches/raw-1970-01-01-02.yml").symlink_to(outside)
        self.refused("leads outside the secrets root", path="batches/raw-1970-01-01-02")

    def test_missing_root(self):
        shutil.rmtree(self.root)
        self.refused("does not exist")

    def test_root_not_0700(self):
        self.root.chmod(0o755)
        self.refused("the secrets root")
        self.refused("is mode 0755, not 0700")

    def test_directory_on_the_way_not_0700(self):
        (self.root / "batches").chmod(0o750)
        self.refused(f"the directory {self.root / 'batches'} is mode 0750, not 0700")

    def test_file_not_0600(self):
        for mode in (0o644, 0o640, 0o400, 0o700):
            with self.subTest(mode=oct(mode)):
                self.file.chmod(mode)
                self.refused(f"is mode {mode:04o}, not 0600")

    def test_not_owned_by_the_user(self):
        with mock.patch("os.getuid", return_value=os.getuid() + 1):
            self.refused("is not owned by you")

    def test_missing_file(self):
        self.refused("there is no file", path="batches/raw-1970-01-01-99")

    def test_missing_key(self):
        self.refused("has no key initial_password_hash", key="initial_password_hash")

    def test_value_not_a_string(self):
        self.refused("is not a string", key="other")

    def test_empty_value(self):
        self.refused("is empty", key="empty")

    def test_not_a_mapping(self):
        self.write("batches/raw-1970-01-01-01.yml", f"- {VALUE}\n")
        self.refused("must hold a mapping")

    def test_invalid_yaml_does_not_quote_the_file(self):
        self.write("batches/raw-1970-01-01-01.yml", f'initial_password: "{VALUE}\n  : [\n')
        self.refused("is not valid YAML")

    def test_one_path_only(self):
        with self.assertRaises(AnsibleLookupError):
            self.plugin.run(["a", "b"], variables={}, key="initial_password")


@unittest.skipUnless(shutil.which("ansible"), "ansible not on PATH")
class UcSecretInAnsible(unittest.TestCase):
    """Through Ansible itself, with the repository's ansible.cfg."""

    def test_value_is_not_templated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "uc"
            (root / "batches").mkdir(parents=True)
            root.chmod(0o700)
            (root / "batches").chmod(0o700)
            path = root / "batches/raw-1970-01-01-01.yml"
            path.write_text('initial_password: "made up {{ 6 * 7 }} value"\n')
            path.chmod(0o600)
            env = dict(os.environ, UC_SECRETS_DIR=str(root), ANSIBLE_NOCOLOR="1")
            env.pop("ANSIBLE_CONFIG", None)
            result = subprocess.run(
                ["ansible", "localhost", "-m", "ansible.builtin.debug", "-a",
                 "msg={{ lookup('uc_secret', 'batches/raw-1970-01-01-01', key='initial_password') }}"],
                cwd=REPO, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("made up {{ 6 * 7 }} value", result.stdout)
        self.assertNotIn("made up 42 value", result.stdout)


if __name__ == "__main__":
    unittest.main()
