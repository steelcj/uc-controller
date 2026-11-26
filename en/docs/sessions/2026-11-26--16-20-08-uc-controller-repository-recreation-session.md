---
title: Repository Recreation for uc-controller, Session
description: The session that cleaned every tracked file of real values, merged the inventory split, checked the repository recreated with no history, and cut and published release 0.1.7.
version: 0.1.0
status: provisional
date: 2026-11-26
language: en-CA
---

# Repository Recreation for uc-controller, Session

## Abstract

The repository was recreated with no history, so the files in its tree were all that would survive. This session first replaced every real value in those files with a safe value from the register in uc-contracts, or with a description where a sentence states a fact. It then merged the inventory split into the old repository's main branch, checked the new repository the operator made by copying those files into a fresh clone, settled the starter files it came with, and cut and published release 0.1.7, the first release of the recreated repository. Real values in this record are described in words, as the safe values register asks.

## Contents

- [Cleaning the tree](#cleaning-the-tree)
- [The register](#the-register)
- [The merge](#the-merge)
- [The recreated repository](#the-recreated-repository)
- [Release 0.1.7](#release-017)
- [Checks](#checks)
- [Left for later](#left-for-later)
- [Changelog](#changelog)

## Cleaning the tree

Every tracked file was searched for real values and each match was replaced, in the older versioned documents, the session records and the kickoff plan too, since the new repository starts from these files.

| Real value, described | Safe value used |
| :-- | :-- |
| The admitted dev host's name | `deb13-vt-0001` |
| That host's address on the operator's LAN, and the LAN's subnet | `203.0.113.10`, `198.51.100.0/24`; another LAN address became `203.0.113.11`, another `203.0.113.50` |
| The host's two MAC addresses and its machine id | `02:00:00:ab:00:01`, `02:00:00:ab:00:02`, `1970010100000000000000000000ab01` |
| The admitted host's batch, the batch made by hand before the batch scripts, and an example batch ID of the real form | `raw-1970-01-01-01`, `raw-1970-01-01-03`, `raw-1970-01-01-01` |
| The project's former name in key file names and three headings | `example-org-raw-initial-id_ed25519` and its siblings; `uc-controller` |
| The operator's home directory on the workstation, and the workstation's shell prompt | `/home/operator`; `operator@workstation` |
| Addresses on the workstation's Incus bridge | `10.0.0.21` for the test container, `10.0.0.1` for the bridge, other hosts keeping their last number, `10.0.0.*` in SSH config |
| Real host key fingerprints and an earlier example | `SHA256:EXAMPLEexampleEXAMPLEexampleEXAMPLEexample0` for an ed25519 key, `…example1` for an ecdsa key |

Where a replacement would have turned a true sentence into a false one, the sentence describes the real thing instead, such as "the two test batches made before the batch files". Paths on a node keep the bootstrap account's home, which is public by design. The fixture reproducing a real 0.1.0 confirmation was renamed to `fail-real-deb13-vt-0001-contract-0.1.0.yml`, with its shape and failures kept.

A fingerprint is 43 characters after `SHA256:`, and admission and `scripts/check_raw_confirmation.py` refuse any other length, so the register's first example, which was longer, was corrected. In the confirmation fixtures each host key now has its own value.

## The register

The safe values register lives in uc-contracts, as the latest `safe-values-and-substitutions-v*.md` in `en/docs/design/`. Version 0.1.2 added the corrected fingerprint form, the operator's machine as `workstation`, the key file rule `<prefix>-raw-initial-id_ed25519`, and Incus bridge addresses under `10.0.0.0/24`. Version 0.1.2 of the documents and secrets strategy points the CLAUDE.md rule at the latest register. Both are committed in uc-contracts, not pushed.

## The merge

Before the merge, the full suite passed on the branch, and the value checks found nothing. The branch was merged into the old repository's `main` with `--no-ff`, with no conflict, and the suite passed again on `main`. The leftover, untracked admitted inventory there was checked against the client inventory repository: the same host, under the same name, with the same batch, every field identical. The operator deleted it, and the worktree and the branch were removed. Every other local branch was already merged into `main`, so recreating the repository lost no work.

## The recreated repository

The operator deleted the old repository on GitHub, created it empty, cloned it, and copied the old checkout's files into the clone. The checks found one history commit, GitHub's, no nested repository, and no inventories, host keys, release builds, caches, vault files or private notes. They also found three things to settle:

- A Word copy of an SSH guide still held the project's former name, which text searches had skipped. It was removed, and its Markdown file is the source.
- A spreadsheet named a person in its author fields. Both fields were emptied.
- The repository's starter files, from the uc-repo template: `LICENSE` was a placeholder, and the copy had replaced six others with the old repository's versions.

The settlement:

- `LICENSE` holds the GNU Affero General Public License version 3, from gnu.org, and `README.md` states `SPDX-License-Identifier: AGPL-3.0-or-later` with its notice.
- `VERSION` stays 0.1.6, and the `[0.1.6]` changelog section says releases up to 0.1.6 were published from the earlier repository, which no longer exists.
- The template's other files stay as they came.

| Commit | What |
| :-- | :-- |
| `840764e` | GitHub's first commit, the uc-repo template |
| `6e99884` | uc-controller 0.1.6, recreated from the current files |
| `8c7cc46` | The licence notice, AGPL-3.0-or-later |

GitHub showed exactly those three commits on `main`, no other branch, and no tags or releases before 0.1.7.

## Release 0.1.7

Cut and published as `en/docs/guides/releases/cut-and-publish-a-release.md` describes, unsigned.

| Item | Value |
| :-- | :-- |
| First line committed before the cut | `bd4347f`, under `[Unreleased]`: this is the first release from the recreated repository, and earlier releases were published from the earlier repository, which no longer exists |
| Release commit | `20685bbffcc79fed173aa2ef6549ab0233e11406`, "release 0.1.7", changing only `VERSION` and `CHANGELOG.md` |
| Tag | `v0.1.7`, annotated, tag object `f2bcafc3834f6fe86773b483f02237cdb7b80ad7` |
| Tarball | `uc-controller-0.1.7.tar.gz`, 995,611 bytes, 795 files |
| SHA256SUMS | `afddf7ee3515f97dea7b21e09ed53313a6beefd0f461c0dea5b424e92a27f67d  uc-controller-0.1.7.tar.gz` |
| Release | https://github.com/steelcj/uc-controller/releases/tag/v0.1.7, with the tarball and `SHA256SUMS` as assets |

Before publishing, the tarball was built with `publish-release.py`'s own `build_tarball`, twice, in a temporary directory, with identical bytes both times. Its contents were listed and checked, and it was extracted and checked for real values. The published tarball has the same checksum. Downloaded again from the release, it passed `sha256sum -c` and was byte for byte the one checked.

## Checks

The same value checks ran on the branch before the merge, on the recreated working tree, on the staged first commit, on the release tarball, and on this record:

- the old LAN prefix, the old Incus bridge prefix, the project's former name, the admitted host's real name, the real batch prefix and a real fingerprint's start, each as a fixed string
- the earlier, longer fingerprint example
- every `SHA256:` value against `^SHA256:EXAMPLEexampleEXAMPLEexampleEXAMPLEexample[0-9]$`, or a prefix of one
- binary files, by their text: the Word document, the spreadsheet and the image

None of them found anything in the final tree, the tarball or this record. The full suite, 96 tests, passed on the branch, on the old `main` after the merge, on the recreated tree, and before each commit.

## Left for later

1. Give the client inventory repository a private remote, and push it.
2. Create the batch file for the admitted host's batch, and delete the test batch file left from trying the recipe.
3. Confirm or reject that the stage environments now get the onboard policy.
4. Switch the firewall to `steelcj.foomuuri`, as `ROADMAP.md` describes.
5. Push uc-contracts. There, safe values 0.1.2 still cites the strategy at 0.1.1, and the raw node handoff document's intake examples still use the project's former name in a key comment.

## Changelog

| Version | Date | Change |
| :-- | :-- | :-- |
| 0.1.0 | 2026-11-26 | First version |
