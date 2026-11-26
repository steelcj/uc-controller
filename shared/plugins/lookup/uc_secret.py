# An OpenBao backend, at fleet/batches/<batch>, will replace the file read here.
"""uc_secret: the only way a playbook, group variable or script reads a secret."""
from __future__ import annotations

DOCUMENTATION = r"""
name: uc_secret
short_description: Read one value from a uc-controller secrets file
description:
  - Reads C(<root>/<path>.yml), a YAML mapping, and returns the value under O(key).
  - The root is C(~/.secrets/uc/fleet), uc-controller's half of C(~/.secrets/uc), or the directory named by the environment variable
    E(UC_SECRETS_DIR), which the tests set.
  - The root, and every directory between it and the file, must be mode 0700 and owned by the
    user running Ansible. The file must be mode 0600 and owned by that user.
  - Every refusal says what to fix, and never includes the value.
  - The value is returned as unsafe text, so a value containing C({{) is never templated.
  - Tasks that print a value read through this lookup set C(no_log: true).
options:
  _terms:
    description: The secret's path under the root, without C(.yml), for example C(batches/raw-1970-01-01-01).
    required: true
  key:
    description: The key whose value is returned.
    type: str
    required: true
"""

EXAMPLES = r"""
ansible_become_password: "{{ lookup('uc_secret', 'batches/' ~ raw_node_batch, key='initial_password') }}"
"""

RETURN = r"""
_raw:
  description: The value, as unsafe text.
  type: list
  elements: str
"""

import os
import stat
from pathlib import Path, PurePosixPath

import yaml

from ansible.errors import AnsibleLookupError
from ansible.plugins.lookup import LookupBase
from ansible.utils.unsafe_proxy import wrap_var

GUIDE = "en/docs/guides/batch-secrets.md"


def secrets_root() -> Path:
    configured = os.environ.get("UC_SECRETS_DIR")
    return Path(configured).expanduser() if configured else Path.home() / ".secrets" / "uc" / "fleet"


def refuse(path: str, problem: str) -> None:
    raise AnsibleLookupError(f"uc_secret: {path}: {problem}")


def check_owner_and_mode(path: str, target: Path, expected: int, what: str) -> None:
    info = target.stat()
    if info.st_uid != os.getuid():
        refuse(path, f"{target} is not owned by you (uid {os.getuid()}). "
                     f"Take it over with chown, or recreate it, as {GUIDE} describes.")
    mode = stat.S_IMODE(info.st_mode)
    if mode != expected:
        refuse(path, f"{what} {target} is mode {mode:04o}, not {expected:04o}. "
                     f"Fix it with chmod {expected:04o} {target}.")


def read_value(path: str, key: str) -> str:
    """Return the value under key in <root>/<path>.yml, after every check."""
    if not isinstance(path, str) or not path.strip():
        refuse(str(path), "the path is empty.")
    relative = PurePosixPath(path)
    if relative.is_absolute() or path.startswith("~"):
        refuse(path, "the path must be relative to the secrets root, such as batches/<batch>.")
    if ".." in relative.parts or "." in relative.parts or "" in path.split("/"):
        refuse(path, "the path must not contain '..', '.' or empty parts.")

    root = secrets_root()
    if not root.is_dir():
        refuse(path, f"the secrets root {root} does not exist. "
                     f"Create it with mode 0700, as {GUIDE} describes.")
    real_root = root.resolve()
    target = root.joinpath(*relative.parts).with_name(relative.name + ".yml")
    if not target.exists():
        refuse(path, f"there is no file {target}. Create it, as {GUIDE} describes.")
    real_target = target.resolve()
    if real_root != real_target and real_root not in real_target.parents:
        refuse(path, f"{target} leads outside the secrets root {root}.")

    # The root and every directory on the way to the file, then the file.
    check_owner_and_mode(path, real_root, 0o700, "the secrets root")
    for directory in reversed(real_target.parents):
        if directory != real_root and real_root in directory.parents:
            check_owner_and_mode(path, directory, 0o700, "the directory")
    if not real_target.is_file():
        refuse(path, f"{target} is not a file.")
    check_owner_and_mode(path, real_target, 0o600, "the file")

    try:
        with real_target.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as error:
        # The parser's message can quote the file's text, so only its position is given.
        mark = getattr(error, "problem_mark", None)
        where = f" near line {mark.line + 1}" if mark is not None else ""
        refuse(path, f"{target} is not valid YAML{where}.")
    except (OSError, UnicodeDecodeError):
        refuse(path, f"{target} cannot be read as UTF-8 text.")
    if not isinstance(data, dict):
        refuse(path, f"{target} must hold a mapping of keys to values.")
    if key not in data:
        refuse(path, f"{target} has no key {key}. Add it, as {GUIDE} describes.")
    value = data[key]
    if not isinstance(value, str):
        refuse(path, f"the value of {key} in {target} is not a string. Quote it.")
    if not value:
        refuse(path, f"the value of {key} in {target} is empty.")
    return value


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        self.set_options(var_options=variables, direct=kwargs)
        key = self.get_option("key")
        if len(terms) != 1:
            raise AnsibleLookupError("uc_secret: give exactly one path, such as 'batches/<batch>'.")
        return [wrap_var(read_value(terms[0], key))]
