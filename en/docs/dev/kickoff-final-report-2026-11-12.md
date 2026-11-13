# Kickoff Final Report: Multi-Source Raw Inventory, Option A Review Fixes, and Speed Settings

Date: 2026-11-12
Source: Claude Code CLI final report, as pasted from the terminal

The terminal output was damaged in the paste, with lines overwritten and cut short. Text that could not be recovered is marked `[…]`. Nothing has been filled in by guesswork; check any marked cell against the session record in the repository.

## Summary

The speed phase is finished, and all phases of the kickoff are committed across five stacked branches. Nothing is pushed or merged. The live host entries in `inventories/onboard/dev/hosts.yml` and `inventories/normalized/dev/hosts.yml` are left uncommitted, as requested.

## Branches, in Merge Order

| Order | Branch | Commits |
|-------|--------|---------|
| 1 | `feat/multi-source-raw-inventory` | 5 |
| 2 | `fix/option-a-review` | 11 |
| 3 | `feat/firewall-rules` | 3 |
| 4 | `fix/normalize-runnable` | 2 |
| 5 | `perf/ansible-cfg` | 10 |

## Review Items From the Inventory Notes

| Priority | Item | Status |
|----------|------|--------|
| High | Persistence model (`add_host` / `promote_node.py`) | […] promotion automatically, the model is […] ng is blocked |
| High | Discovery overwrites `hosts.yml` | […] y its own `discovered.yml` |
| Medium | Check for the connection types that need bootstrap | Fixed: bootstrap is gated on `needs_python_bootstrap`. There were no `ansible_connection` conditions t […] |
| Medium | Playbook and snapshot numbers aligned | Fixed: documented, with the res […] |
| Medium | Why raw has no environment split | Fixed: documented |

## Pre-Freeze List

- Normalize runs end to end: done. `failed=0` on bo […] -demote path was tested.
- Firewall settings implemented: done with `uc_fir` […] untested.
- Persistence documented and re-onboarding blocked: done.
- Discovery writes only its own file: done.
- Snapshot alignment and the no-environment rationale documented: done.

## Timings

### Throwaway Play

30 tasks, 2 nodes, median.

| Change | Time |
|--------|------|
| Baseline | 8.93 s (8.24 […] |
| Pipelining | 6.98 s |
| Fact cache moved | 7.06 s |
| Fresh facts in onboarding | 7.07 s |
| `forks = 20` | 7.48 s |
| `strategy: free` on converge plays | 7.00 s |

### Full Runs

| Run | Before | After |
|-----|--------|-------|
| Onboarding from `raw` | 192.8 s | 162.2 s |
| Normalize from `10-onboarded` | 279.1 s | 260.4 s |

### Notes on the Timings

- Pipelining is the only change with a measurable gain on two nodes. It saved about […] most of onboarding's 16%.
- The other settings show […] kept them because they're harmless.
- The normalize difference can't be credited to any […] a package install whose time depends on the network: it took 246 s in the baseline run and 34 […].
- […] th `strategy: free` on, `profile_tasks` no longer gives a reliable per-task breakdown for that play.
- No node needed a `requiretty` exemption, and `ssh_ar` […] at their defaults.

## Open Questions and Things Not Done

- `en/docs/onboarding-a-raw-dev-node.md` still tells readers to create vaults under […] you to decide.
- Vendored role behaviour, left untouched:
  - `robertdebock.selinux` installs the SELinux pol […]
  - `robertdebock.hostname` reboots the node on eve […]
  - Do you want either disabled through variables?
- The experimental scaffold writes a dictionary w […] t a list. It's noted in the design document, not fixed.
- Untested: auditd and the firewalld path. A Red […] cover both.
- Demotion from normalized to onboard drops extra […] bservers.
- Normalize doesn't save its own promotion, so mo […] a manual `promote_node.py` step.
- No specialize role exists yet, so `30_specialize` […] `-e specialize_role`.
- Renaming discovered nodes at onboarding and the […] up as proposals only.

## Documents Produced

- The design document is now `en/docs/uc-controller-` […]
- The speed record is `en/docs/dev/ansible-speed-optimisations-overview-` […]
- The session record is `en/docs/dev/sessions/multi-source-raw-inventory-` […] `rd-session.md`
