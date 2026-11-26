#!/usr/bin/env python3
"""Build a versioned Ansible virtual environment and mark it as current.

Creates <root>/<version>/ansible, installs ansible==<version> into it, records
the result in <root>/<version>/pip-freeze.txt, and points <root>/current at the
new environment. Once activated, the shell prompt shows the version, as in
(ansible-14.6.0). The version comes from the command line or, failing that,
from the first ansible==<version> line in ansible/controller-requirements.txt.

Runs on Linux, macOS, and Windows using only the standard library.

Usage:
    python scripts/make_ansible_venv.py [ansible-version | latest] [options]
    python scripts/make_ansible_venv.py --installed environments already built
    python scripts/make_ansible_venv.py --list      all stable versions on PyPI
    python scripts/make_ansible_venv.py --latest    newest stable version on PyPI

Giving "latest" as the version builds the newest stable release on PyPI,
ignoring the pin in the requirements file. --installed, --list and --latest
only print; they build nothing. --installed marks the environment that
"current" points at with an asterisk.

Switching the current version:
    <root>/current is a symbolic link (on Windows, a directory junction when
    symlinks are not permitted) to <version>/ansible. To switch, run this
    script with the version wanted:

        python scripts/make_ansible_venv.py 13.8.0

    A version that is already built is not rebuilt; only the link moves. A
    version that is not built yet is built first. A shell that was activated
    before the switch keeps using the old environment until it runs
    "deactivate" and activates again.

Environment:
    VENVS_ROOT  where environments live (default ~/.venvs/ansible)
    PYTHON      interpreter the environment is built from
                (default: the interpreter running this script)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

WINDOWS = os.name == "nt"
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REQUIREMENTS = REPO_ROOT / "ansible" / "controller-requirements.txt"
DEFAULT_ROOT = Path.home() / ".venvs" / "ansible"

# Oldest Python each ansible community package release accepts on the
# controller. Releases newer than the last entry need at least that entry's
# Python; pip enforces the exact requirement during the install.
MIN_PYTHON = {9: (3, 10), 10: (3, 10), 11: (3, 11), 12: (3, 11), 13: (3, 12)}

PIN = re.compile(r"^\s*ansible\s*==\s*([^\s;#]+)", re.IGNORECASE)
VERSION = re.compile(r"^[0-9][0-9A-Za-z.]*$")

PYPI_URL = "https://pypi.org/pypi/ansible/json"
# Digits and dots only, which leaves out alpha, beta, rc, dev and post releases.
STABLE = re.compile(r"^\d+(\.\d+)*$")


EXAMPLES = """\
examples:
  %(prog)s                 build the version pinned in the requirements file
  %(prog)s latest          build the newest stable release
  %(prog)s --installed     show what is built; * marks the current one
  %(prog)s 13.8.0          switch 'current' to 13.8.0, building it if needed

'current' is a link to <version>/ansible. After switching, a shell that is
already activated keeps the old environment until you run 'deactivate' and
activate again.
"""


class Failure(Exception):
    """A problem to report to the user without a traceback."""


def version_from_requirements(path: Path) -> str:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise Failure(f"Cannot read {path}: {error.strerror}") from error
    for line in lines:
        match = PIN.match(line)
        if match:
            return match.group(1)
    raise Failure(f"No ansible==<version> line in {path}")


def stable_versions() -> list[str]:
    """Return every stable ansible release on PyPI, oldest first."""
    request = urllib.request.Request(
        PYPI_URL,
        headers={"Accept": "application/json", "User-Agent": "make_ansible_venv"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            releases = json.load(response)["releases"]
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as error:
        reason = getattr(error, "reason", None) or error
        raise Failure(f"Could not get the version list from {PYPI_URL}: {reason}") from error

    # A release with no files, or with every file yanked, cannot be installed.
    versions = [
        version for version, files in releases.items()
        if STABLE.match(version)
        and any(not item.get("yanked") for item in files)
    ]
    if not versions:
        raise Failure(f"No stable ansible releases listed at {PYPI_URL}")
    return sorted(versions, key=lambda v: tuple(int(part) for part in v.split(".")))


def min_python_for(version: str) -> tuple[int, int] | None:
    major = int(re.match(r"\d+", version).group())
    if major in MIN_PYTHON:
        return MIN_PYTHON[major]
    if major > max(MIN_PYTHON):
        return MIN_PYTHON[max(MIN_PYTHON)]
    return None


def resolve_python(name: str) -> str:
    found = shutil.which(name)
    if found is None:
        raise Failure(f"Python interpreter not found: {name}")
    return found


def check_python(python: str, version: str) -> None:
    probe = subprocess.run(
        [python, "-c", "import sys; print('%d %d' % sys.version_info[:2])"],
        capture_output=True, text=True,
    )
    if probe.returncode != 0:
        raise Failure(f"{python} did not run:\n{probe.stderr.strip()}")
    found = tuple(int(part) for part in probe.stdout.split())
    needed = min_python_for(version)
    if needed and found < needed:
        raise Failure(
            f"{python} is Python {found[0]}.{found[1]}, but ansible {version} "
            f"needs {needed[0]}.{needed[1]} or newer. Choose another "
            "interpreter with --python or the PYTHON environment variable."
        )
    support = subprocess.run(
        [python, "-c", "import venv, ensurepip"], capture_output=True
    )
    if support.returncode != 0:
        raise Failure(
            "Python venv support is missing. On Mint, Debian, or Ubuntu: "
            "sudo apt install python3-venv"
        )


def bin_dir(venv: Path) -> Path:
    return venv / ("Scripts" if WINDOWS else "bin")


def venv_python(venv: Path) -> Path:
    return bin_dir(venv) / ("python.exe" if WINDOWS else "python")


def venv_ansible(venv: Path) -> Path:
    return bin_dir(venv) / ("ansible.exe" if WINDOWS else "ansible")


def prompt_for(version: str) -> str:
    return f"ansible-{version}"


def has_prompt(venv: Path, prompt: str) -> bool:
    """True if the environment was created with this activation prompt."""
    try:
        lines = (venv / "pyvenv.cfg").read_text(encoding="utf-8").splitlines()
    except OSError:
        return False
    for line in lines:
        key, _, value = line.partition("=")
        if key.strip() == "prompt":
            return value.strip().strip("'\"") == prompt
    return False


def set_prompt(python: str, venv: Path, prompt: str) -> None:
    """Rewrite an existing environment's activation scripts with the prompt.

    Running venv again without --clear leaves the installed packages alone.
    """
    run([python, "-m", "venv", "--without-pip", "--prompt", prompt, venv],
        "Updating the environment's prompt")


def run(command: list, what: str) -> None:
    try:
        subprocess.run([str(part) for part in command], check=True)
    except subprocess.CalledProcessError as error:
        raise Failure(f"{what} failed (exit status {error.returncode}).") from error


def build(python: str, venv: Path, version: str, freeze_file: Path, verbose: bool) -> None:
    venv.parent.mkdir(parents=True, exist_ok=True)
    # The freeze file is written last and marks a complete build, so drop any
    # stale copy before starting. --clear empties a half-built environment.
    freeze_file.unlink(missing_ok=True)
    run([python, "-m", "venv", "--clear", "--prompt", prompt_for(version), venv],
        "Creating the virtual environment")

    pip = [venv_python(venv), "-m", "pip", "--disable-pip-version-check"]
    install = pip + ["install"] + ([] if verbose else ["--quiet"])
    run(install + ["--upgrade", "pip"], "Upgrading pip")
    run(install + [f"ansible=={version}"], f"Installing ansible=={version}")

    # Record exactly what was installed, for comparison when upgrading.
    frozen = subprocess.run(pip + ["freeze"], capture_output=True, text=True)
    if frozen.returncode != 0:
        raise Failure(f"pip freeze failed:\n{frozen.stderr.strip()}")
    freeze_file.write_text(frozen.stdout, encoding="utf-8", newline="\n")


def is_link(path: Path) -> bool:
    """True for a symlink or, on Windows, a directory junction."""
    if path.is_symlink():
        return True
    if WINDOWS:
        try:
            attributes = os.lstat(path).st_file_attributes
        except OSError:
            return False
        return bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
    return False


def remove_link(path: Path) -> None:
    try:
        os.unlink(path)
    except OSError:
        os.rmdir(path)  # removes a junction without touching its target


def point_current(root: Path, version: str) -> Path:
    """Point <root>/current at <root>/<version>/ansible."""
    current = root / "current"
    target = Path(version) / "ansible"  # relative, so the tree can be moved
    if os.path.lexists(current) and not is_link(current):
        raise Failure(f"{current} exists and is not a link; move it out of the way.")

    if not WINDOWS:
        # Create beside the old link, then rename over it, so "current"
        # never disappears or points at nothing.
        staging = root / f".current.{os.getpid()}"
        if os.path.lexists(staging):
            os.unlink(staging)
        os.symlink(target, staging)
        os.replace(staging, current)
        return current

    if os.path.lexists(current):
        remove_link(current)
    try:
        os.symlink(target, current, target_is_directory=True)
    except OSError:
        # Symlinks need Developer Mode or administrator rights on Windows.
        # A directory junction needs neither.
        made = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(current), str(root / target)],
            capture_output=True, text=True,
        )
        if made.returncode != 0:
            raise Failure(
                f"Could not link {current} to {root / target}:\n"
                f"{(made.stderr or made.stdout).strip()}"
            )
    return current


def version_key(version: str) -> tuple:
    """Sort key that orders 9.13.0 before 10.0.0 and tolerates 13.0.0rc1."""
    return tuple(
        (0, int(part)) if part.isdigit() else (-1, part)
        for part in re.findall(r"\d+|[A-Za-z]+", version)
    )


def core_version(freeze_file: Path) -> str | None:
    try:
        lines = freeze_file.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in lines:
        name, _, version = line.partition("==")
        if name.strip().lower() == "ansible-core":
            return version.strip()
    return None


def list_installed(root: Path) -> int:
    """Print the environments under root, oldest version first."""
    found = sorted(
        (entry.name for entry in root.iterdir()
         if entry.is_dir() and not is_link(entry)
         and VERSION.match(entry.name) and (entry / "ansible").is_dir()),
        key=version_key,
    ) if root.is_dir() else []
    if not found:
        print(f"No environments in {root}", file=sys.stderr)
        return 0

    current = root / "current"
    active = current.resolve() if os.path.lexists(current) else None
    for version in found:
        venv = root / version / "ansible"
        freeze_file = root / version / "pip-freeze.txt"
        line = f"{'*' if venv.resolve() == active else ' '} {version}"
        if not (venv_ansible(venv).exists() and freeze_file.exists()):
            line += "  (incomplete)"
        elif core_version(freeze_file):
            line += f"  [core {core_version(freeze_file)}]"
        print(line)
    return 0


def report(venv: Path, current: Path, version: str) -> int:
    shown = subprocess.run(
        [str(venv_ansible(venv)), "--version"], capture_output=True, text=True
    )
    status = 0
    if shown.returncode == 0 and shown.stdout:
        # "ansible [core 2.21.6]" names only the engine, so add the version
        # of the community package that was installed.
        core = shown.stdout.splitlines()[0].removeprefix("ansible").strip()
        print(f"ansible {version} {core}")
    elif WINDOWS:
        print(
            "warning: the environment is built, but ansible does not start. "
            "Ansible does not support native Windows as a control node; run "
            "it from WSL instead.",
            file=sys.stderr,
        )
    else:
        print(f"error: {venv_ansible(venv)} --version failed:", file=sys.stderr)
        print(shown.stderr.strip(), file=sys.stderr)
        status = 1

    scripts = bin_dir(current)
    if WINDOWS:
        print(f"Activate with (PowerShell): & '{scripts / 'Activate.ps1'}'")
        print(f"Activate with (cmd.exe):    \"{scripts / 'activate.bat'}\"")
    else:
        print(f"Activate with: . {scripts / 'activate'}")
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a versioned Ansible virtual environment and point "
                    "'current' at it.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "version", nargs="?",
        help="ansible version to install, or 'latest' for the newest stable "
             "release on PyPI (default: the ansible==<version> pin in the "
             "requirements file)",
    )
    query = parser.add_mutually_exclusive_group()
    query.add_argument(
        "--installed", action="store_true",
        help="print the environments already built under the venvs root, "
             "marking the current one with *, and exit",
    )
    query.add_argument(
        "--list", action="store_true", dest="list_versions",
        help="print every stable ansible version on PyPI, oldest first, "
             "and exit",
    )
    query.add_argument(
        "--latest", action="store_true",
        help="print the newest stable ansible version on PyPI and exit",
    )
    parser.add_argument(
        "--requirements", type=Path, default=DEFAULT_REQUIREMENTS, metavar="FILE",
        help="file holding the ansible==<version> pin (default: %(default)s)",
    )
    parser.add_argument(
        "--venvs-root", type=Path, metavar="DIR",
        default=Path(os.environ.get("VENVS_ROOT") or DEFAULT_ROOT),
        help="where environments live (default: $VENVS_ROOT or %(default)s)",
    )
    parser.add_argument(
        "--python", default=os.environ.get("PYTHON") or sys.executable,
        help="interpreter to build from (default: $PYTHON or the one "
             "running this script)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="rebuild the environment even if it is already complete",
    )
    parser.add_argument(
        "--no-current", action="store_true",
        help="leave the 'current' link alone",
    )
    parser.add_argument(
        "--verbose", action="store_true", help="show pip's full output",
    )
    args = parser.parse_args()
    if args.version and (args.installed or args.list_versions or args.latest):
        parser.error("--installed, --list and --latest take no version argument")
    return args


def main() -> int:
    args = parse_args()

    if args.installed:
        return list_installed(args.venvs_root.expanduser().resolve())
    if args.list_versions:
        print("\n".join(stable_versions()))
        return 0
    if args.latest:
        print(stable_versions()[-1])
        return 0

    if args.version == "latest":
        version = stable_versions()[-1]
        print(f"Latest stable ansible is {version}")
    else:
        version = args.version or version_from_requirements(args.requirements)
    if not VERSION.match(version):
        raise Failure(f"Not a usable ansible version: {version!r}")

    root = args.venvs_root.expanduser().resolve()
    venv = root / version / "ansible"
    freeze_file = root / version / "pip-freeze.txt"

    complete = venv_ansible(venv).exists() and freeze_file.exists()
    if complete and not args.force:
        print(f"Already present: {venv}")
        if not has_prompt(venv, prompt_for(version)):
            # Built before the prompt was added, or by other means.
            python = resolve_python(args.python)
            set_prompt(python, venv, prompt_for(version))
            print(f"Prompt set to ({prompt_for(version)})")
    else:
        python = resolve_python(args.python)
        check_python(python, version)
        if venv.exists() and not complete:
            print(f"Rebuilding incomplete environment: {venv}")
        else:
            print(f"Creating {venv}")
        build(python, venv, version, freeze_file, args.verbose)

    if args.no_current:
        current = venv
    else:
        previous = os.path.realpath(root / "current")
        current = point_current(root, version)
        if previous != os.path.realpath(current):
            print(f"Current is now {version}")
    return report(venv, current, version)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Failure as failure:
        print(f"error: {failure}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)
