# Cut and Publish a Release

- **Version:** 0.1.6
- **Date:** 2026-11-23

## Description

The Cut and Publish a Release process:

### Cut Release

* bumps the version in the repository's `VERSION` file

* Creates a dated section holding any new change log entries under the `## [Unreleased]` section in the `CHANGELOG.md`

* commits those two files, and creates an annotated tag

### Publish Release

* creates a GitHub release for the tag, holding a tarball of the tag and its `SHA256SUMS`. `SHA256SUMS` is signed with gpg when signing is enabled and there is a usable signing key

Three scripts in `scripts/` do the mechanical parts. First you write the change log entries, then you cut the release, push it, and publish it.

The scripts also support signing `SHA256SUMS` with gpg. The basic process below publishes without a signature; [(Optional) enable gpg signing](#optional-enable-gpg-signing) sets it up.

| Step | Who | What |
| :-- | :-- | :-- |
| Write the changelog entries | You | Under `## [Unreleased]` in `CHANGELOG.md`, as work happens |
| Cut | `scripts/cut-release.py` | Bumps `VERSION` with `scripts/bump-version.py`, rolls `[Unreleased]` into a dated section, commits those two files, tags |
| Push | You | The commit and the tag |
| Publish | `scripts/publish-release.py` | Builds the tarball twice and refuses if the bytes differ, writes `SHA256SUMS`, signs it if asked and able, creates the GitHub release |

The scripts work on the repository root whatever directory you run them from, but the commands below assume the root.

## Before you start

### Requirements

* git
* Install and configure gh
* (optional) create a signing key

### Confirmations

- The GitHub CLI, authenticated once:

  ```sh
  gh auth status
  ```

  If it is not logged in, run `gh auth login`.

- `dist/` in `.gitignore`. `scripts/publish-release.py` builds its files there, and they are not part of the repository.

- Your work committed. `scripts/cut-release.py` commits only `VERSION` and `CHANGELOG.md`, so anything else you want in the release must already be committed.

### Write your changelog entries

As work happens, add entries under `## [Unreleased]` in `CHANGELOG.md`. Write them for the people who will read the release: they become the GitHub release notes.

```markdown
## [Unreleased]

### <What changed>

<What it means for the people who use this repository.>
```

The scripts never write changelog prose. They only rename the heading.

## Cut a release

### Choose the version type

| Change | Command | Example |
| :-- | :-- | :-- |
| Fixes, documentation, nothing a user has to change | `patch` | 0.1.1 to 0.1.2 |
| New features that keep working with what is there | `minor` | 0.1.2 to 0.2.0 |
| Changes a user has to act on | `major` | 0.2.0 to 1.0.0 |
| A specific number | `0.3.2` | to 0.3.2 |

### Cut your release

```sh
scripts/cut-release.py patch
```

It prints the old and new version, the changelog heading it wrote, and the tag:

```
VERSION: 0.1.1 -> 0.1.2
CHANGELOG.md: [Unreleased] -> ## [0.1.2] - 2026-11-23
[RELEASE] 0.1.1 -> 0.1.2, tagged v0.1.2.
  Nothing pushed. Push when ready:
    git push && git push origin v0.1.2
```

#### Confirm your results

Check the result before pushing:

```sh
git show --stat HEAD
git show v0.1.2:VERSION
head -12 CHANGELOG.md
```

The commit changes only `VERSION` and `CHANGELOG.md`, the tag holds the new version, and `CHANGELOG.md` has an empty `## [Unreleased]` above the new dated section.

#### Push the commit and the tag

```sh
git push && git push origin v0.1.2
```

Pushing is deliberately left to you, over whatever connection you trust.

## Publish your release

### (Optional) Dry run

Optionally, run everything except the publish first:

```sh
scripts/publish-release.py --no-sign --dry-run
```

### Publish

```sh
scripts/publish-release.py --no-sign
```

It checks the tag locally and on `origin`, builds `dist/<repository>-<version>.tar.gz` twice and refuses if the two builds differ, writes `dist/SHA256SUMS`, and creates the GitHub release with both files, titled with the repository and version, with the changelog section as its notes.

`--no-sign` keeps the release unsigned whatever keys are on this machine. Once signing is set up, leave it out.

### Check the release

```sh
gh release view v0.1.2
gh release download v0.1.2 --dir /tmp/v0.1.2
cd /tmp/v0.1.2 && sha256sum -c SHA256SUMS
```

The release lists the tarball and `SHA256SUMS`, and the last command confirms the tarball matches its checksum:

```
<repository>-0.1.2.tar.gz: OK
```

### (Optional) enable gpg signing

A signature on `SHA256SUMS` lets anyone check that the release came from you, not only that the download is intact. `scripts/publish-release.py` signs with the first gpg key on this machine that can sign: one that has not expired or been revoked, has a signing capability, and whose secret part is present.

| Option | Effect |
| :-- | :-- |
| none | Sign if a usable key exists, otherwise publish unsigned, with a note. Never blocks a release |
| `--sign` | Require a signature: fail if there is no usable key |
| `--no-sign` | Never sign |

#### Check your keys

```sh
gpg --list-secret-keys
```

Look for a line that can sign on this machine: `sec` (not `sec#`) with `[S]` among its capabilities, or an `ssb` subkey with `[S]`. These common layouts cannot sign:

| You see | Why it cannot sign |
| :-- | :-- |
| `sec#` | The primary key's secret part is not on this machine, which is usual when the primary is kept offline. A primary with only `[C]` can only certify other keys anyway |
| `ssb … [E]` and no `[S]` | The only subkey can encrypt, not sign |
| `[expired: …]` or `[revoked]` | The key can no longer sign |

#### Check the key's identity

Signatures name the key's identity, its `uid` line. Make sure it is your real name and address, not a placeholder such as `Your Name <you@example.org>`. If it is a placeholder, make a proper key before adding a signing subkey.

#### Add a signing subkey

With the primary kept offline, add a signing subkey on the machine that holds the primary, then bring only the subkeys to the machine that publishes. Replace `<fingerprint>` with the primary key's fingerprint from `gpg --list-secret-keys`.

On the machine with the primary:

```sh
gpg --quick-add-key <fingerprint> ed25519 sign 2y
gpg --export-secret-subkeys <fingerprint> > subkeys.gpg
```

On the machine that publishes:

```sh
gpg --import subkeys.gpg
gpg --list-secret-keys
```

The list now shows an `ssb … [S]` line. Delete `subkeys.gpg` from both machines once it is imported.

Publish your public key, so others can check your signatures:

```sh
gpg --armor --export <fingerprint> > public-key.asc
```

### (Optional) Publish a signed release

```sh
scripts/publish-release.py --sign
```

`--sign` makes sure the release is signed, failing rather than publishing unsigned if the key is not usable. The release then holds a third file, `SHA256SUMS.asc`.

#### Check a signed release

```sh
gh release download v0.1.2 --dir /tmp/v0.1.2
cd /tmp/v0.1.2
gpg --verify SHA256SUMS.asc SHA256SUMS
sha256sum -c SHA256SUMS
```

The first check reports a good signature from your key, and the second confirms the tarball.

## When a script refuses

Every refusal stops before anything that cannot be undone. Fix the cause and run the same command again.

| Message | Cause | What to do |
| :-- | :-- | :-- |
| `VERSION has uncommitted changes` | A release was left half-done | Finish it by hand, or restore `VERSION` with `git restore VERSION` |
| `'## [Unreleased]' … is empty` | Nothing to release | Write the changelog entries first |
| `Tag vX.Y.Z already exists` | That version was released before | Tags are never reused: cut the next version |
| `Tag vX.Y.Z does not exist` | Not cut yet | Run `scripts/cut-release.py` |
| `Tag vX.Y.Z is not on origin` | Not pushed yet | `git push && git push origin vX.Y.Z` |
| `gh not found` or `gh is not authenticated` | The GitHub CLI is missing or logged out | Install it, then `gh auth login` |
| `A release for vX.Y.Z already exists` | It was published before | Releases are never reused: cut the next version |
| `Tarball bytes differ` | The archive is not reproducible | Do not publish, and find out why first |
| `--sign given but no usable gpg secret key` | No key on this machine can sign | See [Check your keys](#check-your-keys) |
| `gpg signing failed: Unusable secret key` | An older `publish-release.py`, which does not check whether a key can sign | Use the current script, or add `--no-sign` |
