#!/usr/bin/env python3
#
# source
#   path: scripts/cut-release.py
#
"""
cut-release.py, cut a release: bump VERSION, roll CHANGELOG.md's
Unreleased section into a dated version section, commit surgically, tag,
and stop before push.

This script owns the release ceremony only. Version arithmetic stays in
bump-version.py, which this script calls rather than reimplements, so
there is exactly one place that computes "what's the next version."

Document versions under en/docs/ are independent of the repository
version, per CONTRIBUTORS.md, and are never touched here. The only
content this script writes is mechanical: renaming CHANGELOG.md's
`## [Unreleased]` heading into a dated `## [X.Y.Z] - YYYY-MM-DD` heading
and leaving a fresh empty Unreleased section above it, per Keep a
Changelog. The entries themselves, what actually changed, are written by
hand as work happens; this script never composes changelog prose.

It lives in the repository's scripts/ directory, beside bump-version.py,
and works on the repository root above it, whatever the current directory.

Usage:
    scripts/cut-release.py patch      0.1.0 -> 0.1.1
    scripts/cut-release.py minor      0.1.1 -> 0.2.0
    scripts/cut-release.py major      0.2.0 -> 1.0.0
    scripts/cut-release.py 0.3.2      set an explicit version

Sequence: guard (VERSION clean, Unreleased section has content) -> bump
(via bump-version.py) -> roll Unreleased into a dated version section in
CHANGELOG.md -> surgical commit (VERSION and CHANGELOG.md only, never
`git add .`) -> guard (HEAD:VERSION) -> annotated tag -> guard
(tag:VERSION) -> report. It stops before push; pushing stays a
deliberate act:

    git push && git push origin vX.Y.Z

Refusals: a dirty VERSION before starting (a half-done release is
finished, not built upon); an empty or missing Unreleased section
(nothing to release); an existing tag for the target version (fix
forward, tags are never reused).
"""
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve().parent   # the scripts/ directory
_ROOT = _HERE.parent                       # the repository root

# ── Repository configuration ────────────────────────────────────────────────
# The only section that differs between repositories using this pattern.

BUMP_SCRIPT = _HERE / "bump-version.py"
VERSION_FILE = _ROOT / "VERSION"
CHANGELOG_FILE = _ROOT / "CHANGELOG.md"

UNRELEASED_HEADING = "## [Unreleased]"
VERSION_HEADING_RE = re.compile(r"^## \[", re.MULTILINE)


# ── Helpers ──────────────────────────────────────────────────────────────────

def fail(msg: str) -> None:
    print(f"[RELEASE ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


def git(*args: str, capture: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=_ROOT,
        capture_output=capture, text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or "").strip() if capture else ""
        fail(f"git {' '.join(args)} failed" + (f": {detail}" if detail else ""))
    return (result.stdout or "").strip()


def read_version() -> str:
    text = VERSION_FILE.read_text(encoding="utf-8").strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", text):
        fail(f"VERSION file does not contain a semantic version: {text!r}")
    return text


def dirty_paths(paths: list) -> str:
    return git("status", "--porcelain", "--",
               *(str(f.relative_to(_ROOT)) for f in paths))


def unreleased_body() -> str:
    text = CHANGELOG_FILE.read_text(encoding="utf-8")
    start = text.find(UNRELEASED_HEADING)
    if start == -1:
        fail(f"No '{UNRELEASED_HEADING}' section in "
             f"{CHANGELOG_FILE.relative_to(_ROOT)}")
    body_start = start + len(UNRELEASED_HEADING)
    m = VERSION_HEADING_RE.search(text, body_start)
    body_end = m.start() if m else len(text)
    return text[body_start:body_end]


# ── Pre-flight guards ─────────────────────────────────────────────────────────

def refuse_if_version_dirty() -> None:
    """A dirty VERSION before starting means a previous release was left
    half-done: finish it by hand, do not stack another on top."""
    if dirty_paths([VERSION_FILE]):
        fail("VERSION has uncommitted changes.\n"
             "  A half-done release is finished, not built upon.")


def refuse_if_nothing_to_release() -> None:
    if not unreleased_body().strip():
        fail(f"'{UNRELEASED_HEADING}' in "
             f"{CHANGELOG_FILE.relative_to(_ROOT)} is empty. "
             "Add entries there by hand as work happens, before cutting "
             "a release.")


def refuse_if_tagged(new: str) -> None:
    if git("tag", "--list", f"v{new}"):
        fail(f"Tag v{new} already exists. Tags are never reused; fix "
             f"forward with the next version number.")


# ── Changelog roll ───────────────────────────────────────────────────────────

def roll_unreleased_into(new: str) -> None:
    """Rename `## [Unreleased]` into a dated `## [X.Y.Z] - YYYY-MM-DD`
    heading, and leave a fresh empty Unreleased section above it. This is
    the one write this script performs, and it is purely mechanical: the
    entries underneath are exactly what was already there, written by
    hand."""
    text = CHANGELOG_FILE.read_text(encoding="utf-8")
    if text.count(UNRELEASED_HEADING) != 1:
        fail(f"Expected exactly one '{UNRELEASED_HEADING}' in "
             f"{CHANGELOG_FILE.relative_to(_ROOT)}")
    today = date.today().isoformat()
    dated_heading = f"## [{new}] - {today}"
    rolled = text.replace(
        UNRELEASED_HEADING,
        f"{UNRELEASED_HEADING}\n\n{dated_heading}",
        1,
    )
    CHANGELOG_FILE.write_text(rolled, encoding="utf-8")
    print(f"{CHANGELOG_FILE.relative_to(_ROOT)}: [Unreleased] -> {dated_heading}")


# ── Ceremony ─────────────────────────────────────────────────────────────────

def main() -> int:
    args = sys.argv[1:]
    if len(args) != 1:
        print(__doc__)
        return 1
    bump_arg = args[0]

    refuse_if_version_dirty()
    refuse_if_nothing_to_release()

    current = read_version()
    result = subprocess.run(
        [sys.executable, str(BUMP_SCRIPT), bump_arg],
        cwd=_ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return result.returncode
    print(result.stdout.strip())
    new = read_version()

    refuse_if_tagged(new)
    roll_unreleased_into(new)

    git("add", "--", str(VERSION_FILE.relative_to(_ROOT)),
        str(CHANGELOG_FILE.relative_to(_ROOT)))
    git("commit", "-m", f"release {new}", capture=False)

    head_version = git("show", "HEAD:VERSION").strip()
    if head_version != new:
        fail(f"HEAD:VERSION is {head_version!r}, expected {new!r}. "
             f"Do not tag; investigate the commit.")

    git("tag", "-a", f"v{new}", "-m", f"version {new}")

    tag_version = git("show", f"v{new}:VERSION").strip()
    if tag_version != new:
        fail(f"v{new}:VERSION is {tag_version!r}, expected {new!r}. "
             f"Delete the local tag and investigate before retrying.")

    print()
    print(f"[RELEASE] {current} -> {new}, tagged v{new}.")
    print("  Nothing pushed. Push when ready:")
    print(f"    git push && git push origin v{new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
