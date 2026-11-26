---
title: Inventory Split for uc-controller, Session
description: The working session after phase one of the inventory split, which moved the operator's inventory into its own private repository, renamed the firewall values for steelcj.foomuuri, and split batch secrets by controller.
version: 0.1.0
status: provisional
date: 2026-11-26
language: en-CA
---

# Inventory Split for uc-controller, Session

## Abstract

After phase one, three changes were made on the branch `inventory-split`, in the worktree `../uc-controller-inventory-split`, in two commits, unmerged and unpushed. The operator's inventory was moved out of uc-controller into a private client inventory repository beside it. The firewall values were renamed and reshaped for `steelcj.foomuuri`, the firewall uc-node builds nodes with, while `uc_firewall` keeps applying them until the switch. Batch secrets were split into one file per controller, so uc-controller's `uc_secret` reads only `~/.secrets/uc/fleet/`. The guiding document for the firewall and the secrets is `en/docs/design/raw-node-handoff-inventories-and-secrets-v0.1.0.md` in uc-contracts. Both changes are approaches to try, adjusted if testing shows a better way.

## Contents

- [Commits](#commits)
- [The client inventory repository](#the-client-inventory-repository)
- [Firewall values for steelcj.foomuuri](#firewall-values-for-steelcjfoomuuri)
- [Batch secrets by controller](#batch-secrets-by-controller)
- [Checks](#checks)
- [Decisions](#decisions)
- [Before the merge](#before-the-merge)
- [Changelog](#changelog)

## Commits

| Commit | Change |
| :-- | :-- |
| `600c138` | Firewall values per stage, shaped for `steelcj.foomuuri` |
| `d0197a4` | Batch secrets split by controller: `uc_secret` reads `~/.secrets/uc/fleet` |

This record is a third commit, together with the date in `en/docs/sessions/README.md`.

## The client inventory repository

The operator's inventory now lives in a private repository of its own, made with `scripts/new-inventory` beside the uc-controller checkout. It has two commits and no remote. Its contents are not described here, because session records are published: it holds one admitted host with its batch name, that host's keys in `ssh/known_hosts`, and the client's values for `onboard/` and `normalized/`.

- What moved: the admitted host, unchanged under the template's header; the host keys; the controller key path, the initial user's public key, locale and time zone for `onboard/dev`; the firewall values of every stage.
- What stayed in uc-controller: the connection settings, the onboard policy and the become password lookup, which `inventory-defaults/` holds now.
- `onboard/stage` holds only its SSH rule, as before the split, with no controller key and no public key. Onboarding into stage fails until it has its own key, which the operator will make when it is first needed. Dev's key is not borrowed.
- Resolving the inventory with `scripts/inventory-args` gives the admitted host its batch, its key path, and the new repository's `ssh/known_hosts` as `uc_known_hosts_file`. The first commit passed the pre-commit hook: `scripts/check_inventory.py` and yamllint.
- The main checkout's `inventories/raw/admitted.yml` is not tracked, so merging the branch leaves it on disk. It is deleted by hand once the copy is confirmed.

## Firewall values for steelcj.foomuuri

uc-node writes the Foomuuri base fragment, `10-base`, only as a bootstrap rule that lets the controller in. From admission on, uc-controller owns every fragment, which the raw node contract 0.3.1 allows. The client inventory gives one variable per stage, so a run that combines stages cannot clobber one with another:

| Variable | Where | Becomes |
| :-- | :-- | :-- |
| `firewall_onboard_ssh` | `onboard/<env>/group_vars/all.yml` | `foomuuri_ssh_port` and `foomuuri_ssh_sources`, in `10-base` |
| `firewall_normalize_services` | `normalized/<env>/group_vars/all.yml` | `foomuuri_services`, in `20-normalize` |
| `firewall_specialize_services` | `normalized/<env>/group_vars/<group>.yml` | `foomuuri_services`, in `30-specialize` |

- Until the switch, `shared/vars/uc_firewall_interim.yml` turns these into the `firewall_rules` list `uc_firewall` reads, one rule per source, and the three playbooks load it with `vars_files`. Without `firewall_onboard_ssh` it gives no SSH rule, so `uc_firewall` still refuses to enable the firewall.
- Where the old data said `0.0.0.0/0`, the new values keep it: any IPv4 address. An empty list means any address, IPv6 included.
- The switch itself is a separate change after the merge, recorded in `ROADMAP.md` and in Moving to steelcj.foomuuri in `en/docs/uc-controller-v0.1.8.md`. Onboard replaces uc-node's `10-base` under the same name, with `foomuuri_require_ssh` left true. Every call keeps all of uc-controller's other fragments, and an empty service list removes its fragment. `uc_firewall`, the interim vars file and its test are removed with it.
- The SSH port stays at 22 on dev and stage. The role moves only the firewall's rule, and sshd moves later in the same run, which is the lockout uc-node's ROADMAP describes.
- The stage TODO now reads "narrow the IPv4 sources for SSH on stage", in the template and in the client inventory.

## Batch secrets by controller

| File | Holds | Read by |
| :-- | :-- | :-- |
| `~/.secrets/uc/fleet/batches/<batch>.yml` | `initial_password` only | uc-controller, through `uc_secret` |
| `~/.secrets/uc/build/batches/<batch>.yml` | The hashes, later | uc-node, once it reads batch files |

- `uc_secret`'s root is `~/.secrets/uc/fleet`, or `UC_SECRETS_DIR` in tests. Lookups are unchanged: `batches/<batch>`.
- The paths match the `fleet` and `build` mounts of the proposed OpenBao layout, so the move to OpenBao changes the lookup, not the playbooks.
- `en/docs/guides/batch-secrets.md` 0.1.1 gives the layout, and a recipe that writes uc-controller's file only. `check_inventory.py`'s messages, the comments, the v0.1.8 design, the guides, the phase one report (0.1.1) and `CHANGELOG.md` use the new paths.

## Checks

| Check | Result |
| :-- | :-- |
| `python3 tests/run_tests.py` after the firewall commit | 96 tests, all passing, including the 5 new tests in `tests/test_uc_firewall_interim.py` |
| `test_uc_secret`, `test_client_inventory` and `test_inventory_split` after the secrets commit | All passing; `test_uc_secret` checks the new default root |
| The interim translation | The template's values give the rules the old `firewall_rules_<stage>` lists gave; one rule per source; `absent` entries left out; macros mapped to their ports |
| `ansible-playbook --syntax-check` on `10_onboard.yml`, `20_normalize.yml` and `30_specialize.yml` | Passing |
| ansible-lint on those three playbooks and the interim vars file | No findings in the vars file; the playbooks' findings are the existing ones (name casing, truthy values) |
| The batch file recipe, run as the guide gives it, in a throwaway `HOME` | Directories 0700, file 0600; a made-up password containing `'` and `{{ }}` read back exactly through the lookup's default root; differing entries wrote nothing |

## Decisions

- **Stage gets no borrowed key.** Failing until stage has its own key is the safe way to fail.
- **Firewall values move now, the role switches later.** Renaming in the branch means the client inventory does not change again at the switch.
- **The batch split happens before the operator creates the batch file**, so the file is made once, in its final place.
- **The handoff document is referred to in uc-contracts**, where it lives. It is not in uc-controller.

## Before the merge

1. Create a private remote for the client inventory repository and push it.
2. Create `~/.secrets/uc/fleet/batches/<batch>.yml` for the admitted host's batch, with `initial_password` only, as `en/docs/guides/batch-secrets.md` describes.
3. After the merge, point `UC_CONTROLLER` at the main checkout for the client repository's hook, and delete the leftover `inventories/raw/admitted.yml` there.
4. Confirm or reject that the stage environments now get the onboard policy, as the phase one report asks.

## Changelog

| Version | Date | Change |
| :-- | :-- | :-- |
| 0.1.0 | 2026-11-26 | First version |
