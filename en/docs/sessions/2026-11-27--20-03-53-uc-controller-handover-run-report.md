---
title: Handover for uc-controller, Run Report
description: Step six of the handover work on example-org, as narrowed by the firewall-only decision: the node admitted under its hostname moved to its fully qualified name by following Admit and Onboard, step by step, what each guide step said and what happened, the guide change, what did not fit, what is left in example-org, and what remains before release 0.2.0.
version: 0.1.0
status: provisional
date: 2026-11-27
language: en-CA
---

# Handover for uc-controller, Run Report

## Summary

Step six ran on example-org after Christopher's go, as the step report narrowed it: `dev.example.org`, admitted by uc-node's phase two under its hostname, `dev`, was removed and admitted again from its candidate under its fully qualified domain name, by following the new guide, Admit and Onboard. Both changes are committed in the client inventory, one commit each. The node was not onboarded or normalized, since `10_onboard.yml` does not onboard admitted nodes yet, so the firewall on the node is still uc-node's, untouched. One guide change came out of the run.

uc-controller was used from the worktree `~/areas/development/uc-controller-handover`, on `handover` at `3b62643`, with `UC_CONTROLLER` pointing there for the client inventory's pre-commit hook. Under `~/.private/` I read and wrote only `~/.private/uc/example-org/`. Under `~/.secrets/` I opened nothing: admission read the batch through `uc_secret`. Every run's output was searched for `$6$` and `$y$`, and none held either.

## The run

### Before

| Item | Found |
| :-- | :-- |
| example-org's client inventory | `main` at `77a1296`, the working tree clean. `raw/admitted.yml` held one host, `dev`, and `ssh/known_hosts` its three keys between `# BEGIN dev` and `# END dev` lines |
| The new `check_inventory.py` on it | One problem: `raw/admitted.yml: admitted host dev is not named by a fully qualified domain name`. The committed candidate passed |
| `read_candidates.py` for `raw-2026-11-27-01` | One valid candidate, `dev.example.org`, no problems, none of other batches |
| The instance `dev-example-org` | Running |

### Move the node admitted under its hostname

| The guide says | What happened |
| :-- | :-- |
| Remove `dev` from `raw/admitted.yml` with the Python snippet, keeping the header | Done as written. The file kept its header, and was left with `hosts: {}`, as the template has it |
| Remove its block from `ssh/known_hosts` with `sed`, from `BEGIN` to `END` | Done as written. The file was left empty, `dev` being its only node |
| `git diff` shows only `dev`'s entry and its block | It did: 16 lines removed and one added, `hosts: {}` |
| Commit both | Commit `08d0ca5`. The hook passed, and printed three line-length warnings: the key lines in `intake/defaults.yml` and `intake/dev.example.org.yml`, 131 characters, and one in `onboard/stage/group_vars/all.yml`, 121. The guide did not say so |

Not run: admission before the removal, which the guide says is stopped as known under another name. Running it would have changed nothing, but the session went straight to the removal, as the plan's step six says. The tests cover it, in `test_z_a_node_admitted_under_its_hostname_is_a_conflict`.

### Admit from the candidate

| The guide says | What happened |
| :-- | :-- |
| Before admission: the candidate committed, its fingerprint compared at the console, the batch file in place, the client's key in the agent | The candidate was committed in `c7d6aa2`. Its fingerprint equals `incus exec dev-example-org -- ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub`. The client's key was in the agent, so `ssh-add` was not needed. The batch file was not looked at: admission's `uc_secret` read it |
| `ansible-playbook $(scripts/inventory-args … raw onboard/dev) ingress/playbooks/05_admit.yml -e admit_batch_id="$batch" -e admit_from_candidates=true` | Exit 0. The report: `<address>: admitted dev.example.org - dev.example.org is new on every count`, in the form the guide shows. The confirmation passed, the become with the batch password was confirmed |
| `raw/admitted.yml` gains `dev.example.org` with its address, port, contract, baseline, machine ID, MACs, batch and the time | It did. The machine ID, address and MAC address equal those of the old `dev` entry, so it is the same node |
| `ssh-keygen -lf ssh/known_hosts`: the line ending `dev.example.org (ED25519)` holds the fingerprint to compare | It did, and the fingerprint equals the console's. The three keys are the old entry's three keys, under the new name, between `# BEGIN dev.example.org` and `# END dev.example.org` |
| Admission never changes `candidates/` | `git status` showed only `raw/admitted.yml` and `ssh/known_hosts` changed |
| Commit both | Commit `be3fcfc`. The hook passed, with the same three warnings. `check_inventory.py` passes on the result |
| Run it again at any time: a node already admitted is reported as `known` | A second run: exit 0, `known dev.example.org - dev.example.org is already known with this machine_id`, nothing written, the working tree clean |

### The firewall on the node

Not changed. The node was neither onboarded nor normalized, so `/etc/foomuuri/` still holds uc-node's `10-base.conf` alone. Admission reads the node and changes nothing on it.

## Guide changes

| Commit | Guide | Change, and the point in the run behind it |
| :-- | :-- | :-- |
| `086c16a` | Admit and Onboard, 0.1.1 | Both commits printed yamllint's line-length warnings, which the guide did not mention: the guide now shows one and says a warning does not stop the commit. Removing the only admitted host leaves `hosts: {}`, which the guide now says |

Every other step of the guide matched what happened, commands and output alike. The README, Client Inventories and Batch Secrets were not part of the run, which made no client inventory and no batch.

## What did not fit

- **The plan's step six, narrowed.** Onboarding `dev.example.org` with `onboard/dev`, normalizing it with `normalized/dev`, and checking the firewall after each could not be done, since `10_onboard.yml` leaves admitted nodes out. Christopher chose the firewall-only cut before step one. The Foomuuri switch was tested on a throwaway node reached as root instead, as the step report records.
- **The commit messages.** The guide's commit messages say "Admit dev.example.org, batch raw-YYYY-MM-DD-NN". The run's add "(test of uc-controller's guide Admit and Onboard, …)", as the plan asks for test commits, in the form uc-node's phase two used.
- **The hook's warnings.** The three line-length warnings come from key lines in `intake/` and the template's `onboard/stage` file, which uc-node's phase two report traced to writing the key line by hand. They are warnings now, as decided, and do not stop a commit.

## What is left in example-org

| What | Where |
| :-- | :-- |
| The instance `dev-example-org`, running, with uc-node's firewall | Incus |
| `dev.example.org`, admitted under its name, batch `raw-2026-11-27-01`, its three host keys under the same name | `raw/admitted.yml`, `ssh/known_hosts` |
| Its candidate and node definition, unchanged | `candidates/dev.example.org.yml`, `intake/dev.example.org.yml`, `intake/defaults.yml` |
| Two commits of this run, after uc-node's phase two's `77a1296` | `08d0ca5` the removal of `dev`, `be3fcfc` the admission, on `main`, not pushed |
| The batch `raw-2026-11-27-01`, both files | `~/.secrets/uc/build/batches/` and `~/.secrets/uc/fleet/batches/`, not opened |

The client inventory's working tree is clean. To undo the run, revert `be3fcfc` and `08d0ca5`, in that order.

## What remains before 0.2.0

1. Review the branch `handover`, from `7165cb6` to the commit of this report, and the two commits in example-org.
2. The three corrections outside this repository, in the step report: uc-node's guide 4, and the handoff design's line 207 and firewall examples in uc-contracts.
3. Onboarding admitted nodes, if 0.2.0 should onboard `dev.example.org`, or after it. Until then the node stays admitted, and the onboard and normalize half of step six waits for it.
4. Cut 0.2.0.

## Changelog

| Version | Date | Change |
| :-- | :-- | :-- |
| 0.1.0 | 2026-11-27 | First version |
