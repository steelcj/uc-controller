# Multi-Source Raw Inventory, Review Fixes, Firewall, Normalize and Speed Session

This session carried out `kickoff-multi-source-raw-inventory-option-a-review-fixes-and-speed-settings.md` and its update, `en/docs/dev/kickoff-remaining-phases-guard-firewall-normalize-and-speed.md`, which replaced the speed, documentation and final report sections and added the firewall role and the runnable normalize stage. Work started from the unmerged `option-a` branch, and each phase branch stacks on the previous one. Nothing was pushed or merged.

## Test Nodes

`deb13` (Debian 13) and `ubu2404` (Ubuntu 24.04) were launched as Incus containers from the `default` variant of the `images:` remote, the lightest image of each OS, and snapshotted as `raw` before Ansible touched them. `ex2-test` was stopped and kept. Both nodes now hold `raw`, `10-onboarded` and `20-normalized` snapshots. One snapshot creation hung and a retry worked; every later snapshot and restore call ran with a timeout and one retry, and none hung again.

## Reconnaissance

The plugin already created an `incus` group through its default groups, so `raw/group_vars/incus.yml` applied; the observation that it did not was wrong. The discovery path had been fixed in the previous session. Bootstrap ran unconditionally and installs sudo. No firewall list reached the firewall, because `robertdebock.firewall` read only `firewall_services`. `20_normalize.yml` named five missing roles. No instance had a `raw` snapshot, and the ingress playbooks had no `ansible_connection` conditions.

## Inventory Structure

`inventories/raw/hosts.yml` became a hand-maintained static file declaring `incus` and `discovered` as children of `raw`. `incus.yml` lost `groups: raw: true` and gained `host_fqdn: false`, so hosts appear as plain `deb13` and `ubu2404`. `raw/group_vars/all.yml` sets `needs_python_bootstrap: true`, and `raw/group_vars/discovered.yml` reaches scanned nodes over SSH as root. `reset_inventories.py` no longer rewrites `raw/hosts.yml`. The naming document moved to v0.1.2 with the scope note, and the design document v0.1.4 was started.

## Review Fixes and Additions

Discovery writes only `raw/discovered.yml`, or `raw/cloud.yml` for the cloud placeholder, both ignored by git, with provisional `disc-<ip>` names and `name_provisional: true`. Two discovery runs left a hand-added `hosts.yml` entry unchanged. `promote_node.py` finds a host in any static file in the source stage; `raw/hosts.yml` is read-only to scripts. Demotion to raw removes the entry and writes nothing under `inventories/raw/`, and demotion from normalized to onboard moves the entry back. `promote_node.py` is resolved from the repository root. The bootstrap play is gated on `needs_python_bootstrap`.

The re-onboarding guard runs `raw: id initial` first and ends the play for a host that is already onboarded; the later plays target an in-memory `onboarding` group holding only the hosts promoted in the run. A second run against onboarded nodes skipped both and changed nothing. The Incus plugin's `filters` accept config keys with exact or regular-expression matching but no negation; a `user.uc_stage` filter is documented as a possible second layer.

`vaults/` held three unencrypted placeholders and was deleted.

## Firewall Role

`roles/uc_firewall` applies `firewall_rules` (`name`, `port`, `protocol`, optional `source`) with ufw on the Debian family and firewalld on the Red Hat family. It asserts an SSH rule before enabling anything, applies allow rules before the default deny, and is additive. `robertdebock.firewall` was removed. After onboarding from `raw`, both nodes showed default deny incoming with only 22/tcp, and SSH as `initial` worked. A temporary rule restricted to the controller's address answered the controller and timed out from `ubu2404`, and was removed. The firewalld path is untested.

## Normalize Stage

`pam`, `limits`, `motd`, `timezone` and `chrony` were removed, and a time sync proposal was written. `robertdebock.auditd` is gated off in containers, where its service is masked. The validation play needed `become: no`, because its reachability check runs on the controller. `20_normalize.yml` runs with `failed=0` on both nodes from `10-onboarded`, and `9100/tcp` is allowed only from `10.0.0.0/24`. Restoring `deb13` to `10-onboarded`, demoting it from normalized to onboard and normalizing again also passed.

Two vendored role behaviours were found and left unchanged: `robertdebock.selinux` installs the SELinux policy packages on Debian, and `robertdebock.hostname` reboots the node through its `Reboot` handler.

## Speed Settings

Each change was a commit of its own, timed on a 30-task throwaway play over SSH as `initial` against both nodes.

| Change | Throwaway play (median) |
|--------|------------------------|
| Baseline | 8.93 s (paired rerun: 8.24 s) |
| Pipelining | 6.98 s |
| Fact cache in `~/.ansible/fact_cache/uc-controller` | 7.06 s |
| Fresh facts in the onboard converge play | 7.07 s |
| `forks = 20` | 7.48 s |
| `strategy: free` on converge plays | 7.00 s |

| Full run | Before | After |
|----------|--------|-------|
| `10_onboard.yml` from `raw` | 192.8 s | 162.2 s |
| `20_normalize.yml` from `10-onboarded` | 279.1 s | 260.4 s |

Pipelining is the only change with a measurable gain on two nodes, about 15% on the throwaway play and most of onboarding's 16%. The others are kept as harmless. The normalize difference is not attributable: its dominant task is a package install whose time depends on the network. No target needed a `requiretty` exemption. The speed overview moved to v0.1.3 with these figures.

## Branches

In merge order, each starting from the previous one:

- `feat/multi-source-raw-inventory`, 5 commits
- `fix/option-a-review`, 11 commits
- `feat/firewall-rules`, 3 commits
- `fix/normalize-runnable`, 2 commits
- `perf/ansible-cfg`, 10 commits including this record

The live entries for `deb13` and `ubu2404` in `inventories/normalized/dev/hosts.yml`, and the emptied `inventories/onboard/dev/hosts.yml`, are left uncommitted.

## Left Open

- `en/docs/onboarding-a-raw-dev-node.md` still describes creating vaults under `vaults/`.
- The experimental scaffold writes a mapping where the firewall plays expect a list.
- `auditd` and the firewalld path are untested; a VM test node would cover the first, and a Red Hat family VM both.
- Demotion from normalized to onboard does not carry extra group memberships such as `webservers`.
- `20_normalize.yml` has no persist play; promotion to normalized is done by hand.
- `30_specialize.yml` and `site.yml` need `-e specialize_role`, and no specialize role exists yet.
- Renaming discovered nodes at onboarding is a proposal only.
