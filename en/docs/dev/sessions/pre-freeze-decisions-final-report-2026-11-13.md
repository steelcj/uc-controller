# Kickoff Final Report: Pre-Freeze Decisions and Fixes

Date: 2026-11-13
Kickoff: `kickoff-pre-freeze-decisions-and-fixes.md`
Session record: `pre-freeze-decisions-session.md`

## Summary

Phases 1 to 3 are done and committed, followed by a cleanup branch that closes port 443 in the inventory data and stops the in-memory promotions from counting as changes. Phase 4 was skipped by decision, so the chain is verified on Debian 13 containers only. Nothing is pushed or merged. The live host entries in `inventories/onboard/dev/hosts.yml` and `inventories/normalized/dev/hosts.yml` are left uncommitted.

## Branches, in Merge Order

The five branches of the previous kickoff (`feat/multi-source-raw-inventory` to `perf/ansible-cfg`) are not merged into `main` and come first.

| Order | Branch | Commits | Contents |
|-------|--------|---------|----------|
| 1 | `fix/pre-freeze-decisions` | 6 | Phase 1 decisions, design document v0.1.5 started |
| 2 | `fix/normalize-promotion` | 7 | Phase 2, `shared/roles`, boundary check, stopped-snapshot rule, naming v0.1.3, deb13 guide |
| 3 | `feat/specialize-webserver` | 4 | Phase 3, guides, verification status, session record, this report |
| 4 | `fix/pre-freeze-cleanup` | 1 | Port 443 removed, `changed_when: false` on the promotions, Known Issues, this report updated |

## Decisions and Fixes

| Item | Status |
|------|--------|
| Hostname reboot stays at the role default; `hostname` after `selinux` | Done, with a caveat: a reboot on an actual hostname change has not been observed, because the image hostname already matches |
| SELinux only on the Red Hat family | Done, with a caveat: the skip on Debian is verified; the Red Hat path is untested |
| Vault instruction removed from the onboarding guide | Done |
| Experimental scaffold removed | Done |
| Normalize persists its own promotion | Done. `onboard_inventory` is required as well as the destination |
| A host that fails normalize is not promoted | Done, with a caveat: run without a `tmp-` snapshot, by decision, because the snapshot hung |
| Demotion keeps group memberships | Done. Found and fixed: demotion to onboard no longer rewrites the connection settings |
| `uc_firewall` used by ingress and converge | Done: moved to `shared/roles/`; the boundary check fails on cross-concern role use |
| Snapshot hang investigation | Done, with a caveat: cause not found. Recorded under Known Issues in the design document: it occurs with the container stopped too, and the time limit and one retry have always worked |
| In-memory promotions report no change | Done: `changed_when: false` on the `add_host` promotion tasks in `10_onboard.yml` and `20_normalize.yml` |
| `webserver` specialize role | Done, with a caveat: verified on Debian 13 only |
| HTTP opened as `webservers` inventory data | Done. 443 removed from the data on `fix/pre-freeze-cleanup`. On `deb13` the existing `allow-https` rule remains, because `uc_firewall` never removes rules: needs your decision |
| `30_specialize.yml` fails early without `specialize_role` | Done |
| `30-webserver` snapshot | Done |
| SELinux reboot check on `rky9` | Not done: Phase 4 skipped |
| Phase 4, Red Hat family node | Not done: skipped by decision |
| Design document | Done: v0.1.5, including Verification Status |
| Guides | Done: the deb13 guide covers raw to specialized; the raw dev node guide has current commands |
| Session record | Done |

## Final Verification

Node `deb13`, a Debian 13 container, restored to `raw` with the stage inventories reset. Each stage ran as its own command.

| Stage | Result | Inventory on disk afterwards |
|-------|--------|------------------------------|
| Onboard | `ok=178 changed=33 failed=0 rescued=1` (the expected bootstrap rescue) | `onboard/dev`: `deb13` in `onboarded` and `webservers`; `normalized/dev` empty |
| `10-onboarded` snapshot | First attempt timed out at 120 s with the instance stopped; retry succeeded in under 1 s | — |
| Normalize | `ok=51 changed=6 failed=0`, no reboot | `normalized/dev`: `deb13` in `normalized` and `webservers`; `onboard/dev` empty |
| `20-normalized` snapshot | Succeeded | — |
| Specialize, `webserver` | `ok=19 changed=3 failed=0`; port 80 closed before, page served after; SSH and all firewall layers present | Unchanged |
| `30-webserver` snapshot | Succeeded | — |
| Normalize again | `ok=48 changed=1 failed=0`; no reboot, boot ID and hostname unchanged. The change is the in-memory `add_host` | Unchanged |
| Specialize again | `ok=19 changed=0 failed=0` | Unchanged |
| Normalize, after the cleanup | `ok=48 changed=0 failed=0`, no reboot | Unchanged |
| Specialize, after the cleanup | `ok=19 changed=0 failed=0`. Port 443 refused from the controller (nothing listens), but ufw still lists `allow-https` | Unchanged |

`--syntax-check` passes on every playbook, including `site.yml`, and `check_converge_boundary.py` passes.

## Untested, and Why

The chain is verified on Debian 13 containers only. None of the following is known to work:

- `robertdebock.auditd`: skipped in containers, and no VM or bare-metal node was built.
- The firewalld path of `uc_firewall`: no Red Hat family node.
- `robertdebock.selinux` and its `Reboot` handler, which shares its name with the handler in `robertdebock.hostname`: which handler runs, whether the node reboots when SELinux is first configured, and whether `getenforce` reports `Enforcing` are unchecked. No Red Hat family node.
- The `webserver` role on a Red Hat family node: no Red Hat family node.
- Ubuntu 24.04: `ubu2404` ran onboard and normalize earlier, but not specialize or the final from-scratch run. It was removed before the final verification.
- `site.yml` as one invocation: only syntax-checked; every stage was run as its own command.
- The hostname-change reboot: the hostname never changed on `deb13`.

## Open Questions and Things Not Done

- **Port 443 on `deb13`.** The data no longer opens 443, but the node keeps the `allow-https` rule from the earlier specialize run, and so does the `30-webserver` snapshot. To match the data, delete the rule by hand (`ufw delete allow from any to any port 443 proto tcp`) or restore `20-normalized` and run specialize again, then retake `30-webserver`.
- **Snapshot hangs.** A known issue in the design document: the cause is unknown and stopping the instance does not prevent it. The time limit bounds it, and a single retry has worked every time so far. The host disk is at 94 % with 59 GB free.
- **Warning in normalize.** `Using run_once with the free strategy is not currently supported` comes from the vendored `robertdebock.selinux` role in the free-strategy converge play. Harmless with one host, and the vendored role was not edited.
- **known_hosts.** `~/.ssh/known_hosts` line 97 still holds the old host key for `10.119.134.49`, so a plain `ssh` to `deb13` fails host key verification. It was not edited. Remove it with `ssh-keygen -R 10.119.134.49` if you want plain `ssh` to work.
- **Stray fragment.** `en/docs/dev/sessions/manual-testing.md` has a half-written code block (`-i inventories/raw/hosts.yml ingress/playbooks/10_onboard.yml`), committed as it was in `cbde5dd`.
- **Empty group.** After normalize, `onboard/dev/hosts.yml` keeps an empty `webservers` group. Harmless.
