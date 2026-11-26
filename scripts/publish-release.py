#!/usr/bin/env python3
#
# source
#   path: scripts/publish-release.py
#
"""
publish-release.py, publish a cut release: build a byte-stable tarball
for an already-pushed tag, compute SHA256SUMS, optionally GPG-sign the
checksum file, and publish the artifacts through a provider backend.

This script owns the publishing ceremony only. Cutting stays in
cut-release.py (bump, changelog roll, commit, tag), and pushing stays a
human act over whatever transport the maintainer trusts; this script
runs strictly after both.

Connectivity is two layers. Transport (git push, tags) is provider
agnostic and this script uses it only for preflight, `git ls-remote` to
confirm the tag is on the remote. The publish channel (creating the
release, attaching assets) is provider specific and is reached through
a small backend seam:

    detect(remote_url)   which provider is this repository on
    preflight()          is the channel ready for this tag
    publish(tag, files)  create the release, attach the artifacts
    release_url(tag)     where consumers will find them

The seam stays honest to the narrowest backend: a release IS files
at stable locations plus SHA256SUMS plus an optional signature,
because that is all the narrowest backend (a plain directory) can
express. Anything richer a provider offers is carried
inside that provider's backend or not at all.

Backends: `gh` (GitHub, auto-detected from the origin URL) and `dir`
(a local directory, the narrowest backend, selected explicitly with
--backend dir --target DIR; also the offline test fixture).

It lives in the repository's scripts/ directory and works on the
repository root above it, whatever the current directory.

Usage:
    scripts/publish-release.py            publish VERSION's tag via the
                                          detected backend
    scripts/publish-release.py --dry-run  everything except publish
    scripts/publish-release.py --backend dir --target DIR
    scripts/publish-release.py --no-sign  skip GPG even if available
    scripts/publish-release.py --sign     require GPG, fail if absent

Sequence: guard (tag exists locally, tag:VERSION matches) -> transport
preflight (tag on remote via ls-remote) -> backend detect and preflight
-> build tarball twice from `git archive` and refuse on any byte
difference (the determinism gate, checked on every run, not assumed)
-> SHA256SUMS -> optional GPG detached signature -> publish -> report
the release URL.

Refusals: no tag for VERSION (cut first); tag content disagreeing with
VERSION; tag absent from the remote (push first); no backend for the
remote; a backend whose channel is not ready (gh absent or
unauthenticated, release already existing, target directory already
holding this tag); nondeterministic archive bytes; --sign with no
usable gpg key.

This script never reads, stores, logs, or echoes a credential.
Authentication belongs to the backend's own tooling (`gh auth login`,
the ssh-agent) and to the human, by design.
"""
import argparse
import gzip
import hashlib
import io
import shutil
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent   # the scripts/ directory
_ROOT = _HERE.parent                       # the repository root

# ── Repository configuration ────────────────────────────────────────────────
# The only section that differs between repositories using this pattern.

VERSION_FILE = _ROOT / "VERSION"
CHANGELOG_FILE = _ROOT / "CHANGELOG.md"
DIST_DIR = _ROOT / "dist"
REMOTE = "origin"


# ── Small helpers ───────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(f"[publish-release] {msg}")


def fail(msg: str) -> None:
    print(f"[publish-release ERROR] {msg}", file=sys.stderr)
    sys.exit(1)


def run(*args: str, capture: bool = True, check: bool = True) -> str:
    result = subprocess.run(
        list(args), cwd=_ROOT,
        capture_output=capture, text=True,
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() if capture else ""
        fail(f"command failed: {' '.join(args)}" + (f"\n  {detail}" if detail else ""))
    return (result.stdout or "") if capture else ""


def git(*args: str, **kw) -> str:
    return run("git", *args, **kw)


def read_version() -> str:
    if not VERSION_FILE.is_file():
        fail(f"{VERSION_FILE.name} not found. This script runs in a "
             f"release-managed repository.")
    return VERSION_FILE.read_text(encoding="utf-8").strip()


# ── Preflight, transport layer (provider agnostic) ──────────────────────────

def refuse_unless_tagged(tag: str, version: str) -> None:
    if not git("tag", "--list", tag).strip():
        fail(f"Tag {tag} does not exist. Cut the release first:\n"
             f"    scripts/cut-release.py {version}")
    tag_version = git("show", f"{tag}:VERSION").strip()
    if tag_version != version:
        fail(f"{tag}:VERSION is {tag_version!r} but VERSION is "
             f"{version!r}. Publish from the commit the tag points at, "
             f"or investigate the tag.")


def refuse_unless_pushed(tag: str) -> None:
    """Transport-layer preflight: works identically over SSH or HTTPS,
    against any provider, because it is a git operation, not a platform
    one."""
    out = git("ls-remote", "--tags", REMOTE, f"refs/tags/{tag}")
    if f"refs/tags/{tag}" not in out:
        fail(f"Tag {tag} is not on {REMOTE}. Pushing is a human act; "
             f"push first:\n    git push && git push {REMOTE} {tag}")


def remote_url() -> str:
    return git("remote", "get-url", REMOTE).strip()


def repo_name(url: str) -> str:
    name = url.rstrip("/").rsplit("/", 1)[-1]
    return name[:-4] if name.endswith(".git") else name


# ── Backends ────────────────────────────────────────────────────────────────
# The seam. publish(tag, files) is the whole contract; a release is
# files plus SHA256SUMS plus an optional signature, nothing more,
# because the narrowest backend is a directory.

class GhBackend:
    """GitHub, through the gh CLI. Authentication is gh's own; this
    script never touches a token."""

    name = "gh"

    def __init__(self, repo: str, version: str):
        self.repo = repo
        self.version = version

    def preflight(self, tag: str) -> None:
        if not shutil.which("gh"):
            fail("gh not found. Install the GitHub CLI (official "
                 "packages exist for macOS, Windows, and Linux) and "
                 "authenticate once with: gh auth login")
        auth = subprocess.run(["gh", "auth", "status"], cwd=_ROOT,
                              capture_output=True, text=True)
        if auth.returncode != 0:
            fail("gh is not authenticated. Authenticate once with: "
                 "gh auth login")
        view = subprocess.run(["gh", "release", "view", tag], cwd=_ROOT,
                              capture_output=True, text=True)
        if view.returncode == 0:
            fail(f"A release for {tag} already exists. Releases are "
                 f"never reused; fix forward with the next version.")

    def publish(self, tag: str, files: list) -> None:
        # Release notes are provider garnish, carried inside this
        # backend only: the changelog section for this version, when
        # present, becomes the gh release notes.
        notes = changelog_section(self.version)
        args = ["gh", "release", "create", tag,
                *[str(f) for f in files],
                "--title", f"{self.repo} {self.version}",
                "--verify-tag"]
        if notes:
            notes_file = DIST_DIR / "RELEASE_NOTES.md"
            notes_file.write_text(notes, encoding="utf-8")
            args += ["--notes-file", str(notes_file)]
        else:
            args += ["--notes", ""]
        result = subprocess.run(args, cwd=_ROOT, capture_output=True,
                                text=True)
        if result.returncode != 0:
            fail("gh release create failed:\n  "
                 + (result.stderr or result.stdout).strip())

    def release_url(self, tag: str) -> str:
        url = remote_url()
        base = url[:-4] if url.endswith(".git") else url
        if base.startswith("git@github.com:"):
            base = "https://github.com/" + base[len("git@github.com:"):]
        return f"{base}/releases/tag/{tag}"


class DirBackend:
    """A plain directory: the narrowest backend, and therefore the one
    that defines what a release is. Also the offline test fixture."""

    name = "dir"

    def __init__(self, target: Path):
        self.target = target

    def preflight(self, tag: str) -> None:
        if self.target is None:
            fail("--backend dir requires --target DIR")
        if (self.target / tag).exists():
            fail(f"{self.target / tag} already exists. Releases are "
                 f"never reused; fix forward with the next version.")

    def publish(self, tag: str, files: list) -> None:
        dest = self.target / tag
        dest.mkdir(parents=True, exist_ok=False)
        for f in files:
            shutil.copyfile(f, dest / f.name)

    def release_url(self, tag: str) -> str:
        return str(self.target / tag)


def detect_backend(args, repo: str, version: str):
    if args.backend == "dir":
        return DirBackend(Path(args.target).expanduser().resolve()
                          if args.target else None)
    url = remote_url()
    if "github.com" in url:
        return GhBackend(repo, version)
    fail(f"No backend for remote {url!r}. Available: gh (github.com "
         f"remotes, auto-detected), dir (--backend dir --target DIR).")


# ── Artifacts ───────────────────────────────────────────────────────────────

def build_tarball(tag: str, repo: str, version: str) -> bytes:
    """git archive is deterministic for a given tag (sorted entries,
    commit-timestamp mtimes, no uid/gid); gzip with mtime=0 and no
    filename keeps the compressed bytes deterministic too."""
    result = subprocess.run(
        ["git", "archive", "--format=tar",
         f"--prefix={repo}-{version}/", tag],
        cwd=_ROOT, capture_output=True,
    )
    if result.returncode != 0:
        fail("git archive failed:\n  " + result.stderr.decode().strip())
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(result.stdout)
    return buf.getvalue()


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def changelog_section(version: str) -> str:
    """The changelog entries for this version, heading excluded. Used
    only as gh-backend garnish; absence warns, never blocks."""
    if not CHANGELOG_FILE.is_file():
        return ""
    text = CHANGELOG_FILE.read_text(encoding="utf-8")
    heading = f"## [{version}]"
    start = text.find(heading)
    if start == -1:
        log(f"note: no '{heading}' section in {CHANGELOG_FILE.name}; "
            f"publishing without release notes")
        return ""
    body_start = text.index("\n", start) + 1
    nxt = text.find("\n## [", body_start)
    return text[body_start: nxt if nxt != -1 else len(text)].strip() + "\n"


def usable_signing_key() -> str:
    """The fingerprint of the first secret key gpg can sign with, or "".

    A secret key can be listed and still be unusable: expired, revoked,
    disabled, without a signing capability, or a stub whose secret part
    is elsewhere (a smartcard, another machine). Each secret key's
    "sec" line in --with-colons output carries its validity (field 2),
    its usable capabilities (field 12, an upper-case "S" means it can
    sign, through itself or a subkey) and a stub marker (field 15, "#").
    """
    keys = subprocess.run(
        ["gpg", "--list-secret-keys", "--with-colons"],
        capture_output=True, text=True)
    if keys.returncode != 0:
        return ""
    lines = [line.split(":") for line in keys.stdout.splitlines()]
    for i, fields in enumerate(lines):
        if fields[0] != "sec" or len(fields) < 15:
            continue
        validity, capabilities, token = fields[1], fields[11], fields[14]
        if validity in ("e", "r", "d", "i") or "S" not in capabilities \
                or token == "#":
            continue
        for following in lines[i + 1:]:
            if following[0] == "fpr":
                return following[9]
            if following[0] == "sec":
                break
    return ""


def maybe_sign(sums_path: Path, mode: str) -> Path:
    """Detached armored signature of SHA256SUMS. Absence of gpg (or of
    a usable secret key) must not block publishing; --sign makes
    absence an error, --no-sign skips entirely. The key is
    chosen explicitly, so an unusable default key cannot fail the
    signature after a usable one was found."""
    if mode == "never":
        return None
    key = usable_signing_key() if shutil.which("gpg") else ""
    if not key:
        if mode == "require":
            fail("--sign given but no usable gpg secret key is "
                 "available (none that is unexpired, unrevoked, able to "
                 "sign and present on this machine).")
        log("gpg or a usable secret key is unavailable; publishing "
            "unsigned (allowed, never blocking).")
        return None
    sig = sums_path.with_suffix(sums_path.suffix + ".asc")
    sig.unlink(missing_ok=True)
    result = subprocess.run(
        ["gpg", "--batch", "--yes", "--armor", "--detach-sign",
         "--local-user", key, "--output", str(sig), str(sums_path)],
        capture_output=True, text=True)
    if result.returncode != 0:
        fail("gpg signing failed:\n  " + result.stderr.strip())
    log(f"signed: {sig.name}, with key {key[-16:]}")
    return sig


# ── Ceremony ────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        prog="scripts/publish-release.py",
        description="Publish an already-cut, already-pushed release "
                    "through a provider backend.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Everything except publish.")
    parser.add_argument("--backend", choices=["auto", "dir"],
                        default="auto",
                        help="Backend selection; auto detects from the "
                             "remote URL.")
    parser.add_argument("--target",
                        help="Destination directory for --backend dir.")
    sign = parser.add_mutually_exclusive_group()
    sign.add_argument("--sign", dest="sign", action="store_const",
                      const="require", default="auto",
                      help="Require a GPG signature.")
    sign.add_argument("--no-sign", dest="sign", action="store_const",
                      const="never", help="Skip GPG signing.")
    args = parser.parse_args()

    version = read_version()
    tag = f"v{version}"
    repo = repo_name(remote_url())

    refuse_unless_tagged(tag, version)
    refuse_unless_pushed(tag)

    backend = detect_backend(args, repo, version)
    backend.preflight(tag)
    log(f"backend: {backend.name}, tag {tag} verified locally and on "
        f"{REMOTE}")

    # The determinism gate, verified on every run rather than assumed.
    first = build_tarball(tag, repo, version)
    second = build_tarball(tag, repo, version)
    if sha256_of(first) != sha256_of(second):
        fail("Tarball bytes differ between two identical builds. The "
             "determinism gate failed; do not publish. Investigate "
             "before retrying.")

    DIST_DIR.mkdir(exist_ok=True)
    tarball = DIST_DIR / f"{repo}-{version}.tar.gz"
    tarball.write_bytes(first)
    digest = sha256_of(first)
    log(f"built: {tarball.name} ({len(first)} bytes, sha256 "
        f"{digest[:16]}…, deterministic)")

    sums = DIST_DIR / "SHA256SUMS"
    sums.write_text(f"{digest}  {tarball.name}\n", encoding="utf-8")
    files = [tarball, sums]

    sig = maybe_sign(sums, args.sign)
    if sig is not None:
        files.append(sig)

    if args.dry_run:
        log("dry run; nothing published. Artifacts left in "
            f"{DIST_DIR.name}/:")
        for f in files:
            print(f"  {f.name}")
        return 0

    backend.publish(tag, files)
    print()
    log(f"published {tag} via {backend.name}:")
    print(f"  {backend.release_url(tag)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
