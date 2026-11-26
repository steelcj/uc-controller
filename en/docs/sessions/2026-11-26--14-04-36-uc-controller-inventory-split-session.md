---
title: Example Batch Name for uc-controller, Session
description: The session that changed the example batch name from raw-EXAMPLE-01 to raw-1970-01-01-01 across the inventory-split branch, with every occurrence, the checks that touch a batch name, and the version bumps.
version: 0.1.1
status: provisional
date: 2026-11-26
language: en-CA
---

# Example Batch Name for uc-controller, Session

## Abstract

The example batch name `raw-EXAMPLE-01` did not follow the `raw-YYYY-MM-DD-NN` pattern that real batches use. It was changed to `raw-1970-01-01-01`, the Unix epoch, which follows the pattern and is a date no real batch can have. The change was made in the guides, the design document, the template, the tests, the fixtures, a script comment, the lookup's documentation and the phase one report, and left out of the kickoff plan, which records what was asked. It is commit `42fe10d` on the branch `inventory-split`, in the worktree `../uc-controller-inventory-split`, unmerged and unpushed. `en/docs/guides/batch-secrets.md` 0.1.3 was applied on top of the operator's 0.1.2, committed with it. The suite passed, 96 tests.

## Contents

- [The prompt](#the-prompt)
- [Occurrences](#occurrences)
- [Variant mapping](#variant-mapping)
- [What touches a batch name](#what-touches-a-batch-name)
- [Version bumps](#version-bumps)
- [Left for the operator](#left-for-the-operator)
- [Changelog](#changelog)

## The prompt

```text
Change the example batch name from raw-EXAMPLE-01 to raw-1970-01-01-01 everywhere in the inventory-split worktree: guides, design doc, template, tests, fixtures, scripts' messages and the phase report. Find every occurrence with grep -rn 'raw-EXAMPLE' --exclude-dir=.git . and list them in your report.

- In batch-secrets.md, apply it on top of my v0.1.2, which I am copying in now, and make it v0.1.3. The sentence becomes: Batch names follow `raw-YYYY-MM-DD-NN`. Examples in these documents use `raw-1970-01-01-01`, the Unix epoch, a date no real batch can have.
- Leave the kickoff plan's text alone, since it records what was asked. Add a line to the phase report saying the example name changed and why.
- If anything validates batch names, check that it accepts raw-1970-01-01-01. If nothing does, say so.
- Bump the version of each versioned document you change, with a changelog row. Add a CHANGELOG.md entry under [Unreleased].
- Run the suite and commit on inventory-split.
```

## Occurrences

From `grep -rn 'raw-EXAMPLE' --exclude-dir=.git .`, before the change:

| File | Lines | Changed |
| :-- | :-- | :-- |
| `README.md` | 18 | Yes |
| `inventory-template/README.md` | 30 | Yes |
| `ingress/playbooks/05_admit.yml` | 38, the usage comment | Yes |
| `shared/plugins/lookup/uc_secret.py` | 19, the option's documentation | Yes |
| `en/docs/admitting-a-raw-node.md` | 71, 98, 102, 179, 194 | Yes |
| `en/docs/guides/batch-secrets.md` | 69, the pattern sentence, and 94, 138, 144, 155, 177, 185 | Yes |
| `en/docs/guides/client-inventories.md` | 84 | Yes |
| `en/docs/uc-controller-v0.1.8.md` | 1936, 1987 | Yes |
| `en/docs/sessions/2026-11-25--08-56-44-uc-controller-inventory-split-phase-one-report.md` | 47, 70 | Yes |
| `en/docs/sessions/2026-11-24--22-46-54-uc-controller-inventory-split-plan-and-kickoff.md` | 116, 121 | No, it records what was asked |
| `tests/test_uc_secret.py` | 48, 64, 67, 88, 91, 94, 100, 101, 127, 139, 143, 161, 168 | Yes |
| `tests/test_admit_playbook.py` | 160, 162, 394, 397, 399, 404, 406 | Yes |
| `tests/test_client_inventory.py` | 212, 293, 352, 364 | Yes |
| `tests/test_raw_inventory_scripts.py` | 32, 154 | Yes |
| `tests/fixtures/inventory-split/client/raw/admitted.yml` | 11 | Yes |
| `tests/fixtures/inventory-split/expected/raw+onboard-dev.yml` | 65 | Yes |

The same grep, given `-l`, also lists ignored `__pycache__/*.pyc` files, compiled from the old test sources. They were not edited, and were rebuilt on the next run.

After the change, `raw-EXAMPLE-01` remains in the kickoff plan, and on purpose in three entries that say what replaced it: the entry in `CHANGELOG.md`, the 0.1.3 row of `batch-secrets.md`, and the line added to the phase one report.

## Variant mapping

| Before | After | Where | Use |
| :-- | :-- | :-- | :-- |
| `raw-EXAMPLE-01` | `raw-1970-01-01-01` | Everywhere above | The example batch |
| `raw-EXAMPLE-02` | `raw-1970-01-01-02` | `tests/test_uc_secret.py` | A batch file that is a symlink out of the root |
| `raw-EXAMPLE-short` | `raw-1970-01-01-02` | `tests/test_admit_playbook.py` | The batch whose password is under 15 characters, for RN-ACC-08. A comment there now says so, since the name no longer does |
| `raw-EXAMPLE-99` | `raw-1970-01-01-99` | `tests/test_uc_secret.py`, `tests/test_admit_playbook.py` | A batch with no file |

## What touches a batch name

Nothing validates the `raw-YYYY-MM-DD-NN` pattern. Three things touch a batch name, and `raw-1970-01-01-01` passes all three; the suite exercises each:

| Where | What it checks |
| :-- | :-- |
| `ingress/playbooks/05_admit.yml` | `admit_batch_id` is defined and not empty |
| `scripts/check_inventory.py` | Every admitted host has a `raw_node_batch` that is a non-empty string |
| `shared/plugins/lookup/uc_secret.py` | The path `batches/<batch>` has no absolute, `~`, `.`, `..` or empty part |

## Version bumps

| Document | Version | Changelog |
| :-- | :-- | :-- |
| `en/docs/guides/batch-secrets.md` | 0.1.2 to 0.1.3 | A row for the new example name and the reason, with the pattern sentence as given in the prompt |
| `en/docs/guides/client-inventories.md` | 0.1.1 to 0.1.2 | A row for the new example name |
| `en/docs/sessions/2026-11-25--08-56-44-uc-controller-inventory-split-phase-one-report.md` | 0.1.1 to 0.1.2 | A row, and a line under the test changes saying the name changed and why |
| `en/docs/admitting-a-raw-node.md` | No version field | Its 2026-11-26 row extended |
| `en/docs/uc-controller-v0.1.8.md` | No version field | A row, Example batch, in its v0.1.7 to v0.1.8 table |
| `CHANGELOG.md` | Not versioned | An entry under [Unreleased], Changed |

## Left for the operator

Neither file was read, created or deleted in the session.

1. Create the batch file for the admitted host's batch, in `~/.secrets/uc/fleet/batches/`, with `initial_password` only, as `en/docs/guides/batch-secrets.md` describes.
2. Delete `~/.secrets/uc/fleet/batches/raw-EXAMPLE-01.yml`, a test file left from trying the recipe in that guide.

## Changelog

| Version | Date | Change |
| :-- | :-- | :-- |
| 0.1.1 | 2026-11-26 | Retitled with the work it records, Example Batch Name, in the README's form. The real batch name replaced by a description, as session records name no real batch |
| 0.1.0 | 2026-11-26 | First version |
