# Pre-Freeze Decisions Session

This session carried out the kickoff prompt in `en/docs/dev/sessions/kickoff-pre-freeze-decisions-and-fixes.md`. It ran over three Claude Code sessions on 2026-11-12 and 2026-11-13, two of them cut short by the usage limit. It applied the three decisions and the fixes of Phases 1 and 2, moved `uc_firewall` to `shared/roles/`, tested a host that fails normalize, investigated the snapshot hangs, and added the `webserver` specialize role in Phase 3. Phase 4, the Rocky 9 node, was skipped by decision, and the final verification ran on `deb13` alone. The final report is in `pre-freeze-decisions-final-report-2026-11-13.md` beside this file.

## Setup

The five stacked branches of the previous kickoff, ending with `perf/ansible-cfg`, were not merged into `main`, so work started from the tip of that stack. Ansible came from `~/.venvs/ansible/current/bin/activate`. The test nodes were the Incus containers `deb13` and `ubu2404`, each with `raw`, `10-onboarded` and `20-normalized` snapshots.

## Phase 1: Decisions

Branch `fix/pre-freeze-decisions`, 6 commits.

- **Hostname reboot.** `hostname_reboot` stays at the role default. A comment beside the role list in `20_normalize.yml` says `robertdebock.hostname` must stay after `robertdebock.selinux`, which flushes handlers partway through. Testing showed that the reboots seen in earlier sessions came from SELinux, not from a hostname change: `robertdebock.selinux` notifies a handler named `Reboot`, `robertdebock.hostname` defines one of the same name, and the log labelled the reboot with the hostname role.
- **SELinux.** `robertdebock.selinux` runs only when `os_family` is `RedHat`. Normalize on `deb13` then ran with no reboot and no hostname change.
- **Vault instruction.** Replaced in `en/docs/onboarding-a-raw-dev-node.md` with one sentence saying the secrets pattern is not decided.
- **Scaffold.** `tools/scaffold.yml` was deleted. Nothing depended on it, and its design document entry became a changelog note.
- **uc_firewall** moved from `roles/` to `converge/roles/`, so that `roles/` holds only vendored roles. It later moved again; see below.
- Design document v0.1.5 was started, with v0.1.4 kept.

## Phase 2: Promotion and Demotion

Branch `fix/normalize-promotion`.

- `20_normalize.yml` ends with a play on the linear strategy that calls `promote_node.py` once on the controller, with `--no-commit`, and moves each host that completed the converge play from `onboard_inventory` to `normalized_inventory`. Both variables are required. The prompt asked only for the destination; `onboard_inventory` is required as well because it is the source of the move.
- The validation play also targets `normalized`, so normalize can be rerun. A host already in the normalized inventory is left where it is.
- Moves between onboard and normalized keep every group other than the stage group, in both directions. Testing found that demotion to onboard reapplied the connection settings and demanded `--key-file`; the settings are now written only on promotion out of raw.

Checks: on a temporary copy of the inventories, a host with two extra groups and a host with none made the round trip onboard → normalized → onboard unchanged, and a repeat promotion replaced the entry instead of duplicating it. On `deb13`, restored to `10-onboarded` and demoted, normalize ran as its own command with `failed=0`, and the final play moved the host to `normalized/dev` with its settings and `webservers`.

## Changes Requested Before Phase 3

- `10_onboard.yml` uses `uc_firewall` to open SSH, so a role in `converge/roles/` was used by an ingress playbook. `uc_firewall` moved to a new `shared/roles/`, for repository roles used by both concerns. `roles_path` lists `./roles`, `./shared/roles`, `./ingress/roles` and `./converge/roles`.
- `check_converge_boundary.py` now also fails when an ingress playbook uses a role from `converge/roles/` or a converge playbook uses one from `ingress/roles/`. Role names built from a variable are skipped.
- The role-directory rule is in design document v0.1.5.

## Failing-Host Test

The test was meant to run on a `tmp-` snapshot, but `incus snapshot create deb13 tmp-normfail` hung on both attempts, 90 seconds each, with the container running. By decision the test ran against the nodes as they were, without a snapshot.

A temporary task in `20_normalize.yml` failed the host named by `-e uc_test_fail_host=ubu2404`. Result: `ubu2404` `failed=1` and stayed in `onboard/dev` with `webservers`; `deb13` `failed=0` and moved to `normalized/dev` with `webservers`. The temporary task was removed and the playbook matched the commit again. A clean rerun on both nodes finished with `failed=0` and no reboot, moved `ubu2404`, left `deb13` in place, and emptied `onboard/dev`.

## Snapshot Hang Investigation

Read-only, about ten minutes.

- Incus daemon log: no snapshot, freeze or timeout messages. The only errors were `SFTP server stopped with error` at instance stops.
- Kernel log: no btrfs, loop device, hung task, out-of-space or I/O errors.
- Storage pool: btrfs in a 150 GiB loop image at `/var/lib/incus/disks/default.img`, 44 % used.
- Host root filesystem: dnsmasq logged `No space left on device` for its leases file under `/var/lib/incus` at 20:07 and 20:08, so the host disk filled once, between the two hangs rather than during either. It was at 94 % with 55 GB free afterwards.
- Inside `deb13` around the second hang: `apt-listchanges.service` initialised its database in about two seconds, and `systemd-tmpfiles-clean` ran. No apt, unattended-upgrades or role tasks were running.

No simple cause was found. From then on every stage snapshot is taken with the instance stopped: stop, snapshot, start, each under a time limit, then wait for SSH. The rule is in design document v0.1.5 and in *Incus: Instance Naming* v0.1.3; v0.1.2 of that document moved to `en/docs/artifacts/`.

## Fresh deb13

Between sessions `deb13` was recreated from `images:debian/13` with `pristine` and `raw` snapshots, at `10.119.134.49`, and `ubu2404` was removed. A new guide, `en/docs/onboarding/onboarding-a-new-incus-node-deb13.md`, walks the node from launch onwards. The operator onboarded and normalized the fresh `deb13` with it and took `10-onboarded` and `20-normalized`, which served as the from-scratch test before Phase 3.

## Phase 3: A Minimal Specialize Role

Branch `feat/specialize-webserver`.

- `converge/roles/webserver` installs nginx, enables and starts it, and writes `index.html` with the host's inventory name into the default document root: `/var/www/html` on the Debian family, `/usr/share/nginx/html` on the Red Hat family. Other OS families fail with a clear message. The role opens no port.
- HTTP is opened only by `allow-http` in `firewall_rules_specialize` in `inventories/normalized/dev/group_vars/webservers.yml`, which was already in place from `feat/firewall-rules`. That file also opens 443, which nothing serves.
- `30_specialize.yml` includes the specialize role and `uc_firewall` with `include_role`, after an assert on `specialize_role`. Without it the run stops with `Set the role this stage applies, for example -e specialize_role=webserver.` A `roles:` entry named by an undefined variable fails while the playbook is parsed, so the assert could not run before it. `--syntax-check` now passes without the variable.
- Specialize needs the onboard inventory loaded, because `firewall_rules_onboard`, with the SSH rule, lives there.

Checks on `deb13`: before specialize, port 80 timed out from the controller and SSH worked. The run finished with `ok=19 changed=3 failed=0`. Afterwards `curl` returned `deb13`, SSH worked, and ufw listed `allow-ssh`, `allow-monitoring` from `10.0.0.0/24`, `allow-http` and `allow-https`. A second run reported `changed=0`. The `30-webserver` snapshot was taken stopped. Right after the start, `curl` was refused once: nginx came up about three seconds after SSH answered.

The guides were updated so the chain from raw to specialized can be followed as written: step 9 in the deb13 guide, and current commands in `onboarding-a-raw-dev-node.md`, which still used `ex2-test.default.local`, `-l 'ex2-test*'` and `-i inventories/raw/incus.yml`.

## Phase 4: Skipped

By decision, no other node was built or tested. `rky9` was not launched and `ubu2404` was not recreated. See Verification Status in design document v0.1.5 for what that leaves untested.

## Final Verification

On `deb13` only. Host root filesystem: 60 GB free before starting, above the 30 GB floor.

1. `incus snapshot restore deb13 raw`, then `python3 scripts/reset_inventories.py`, which cleared `normalized/dev` and one fact cache file. The node had no `initial` user and no Python; both stage inventories matched their committed, empty state.
2. Onboard: `ok=178 changed=33 failed=0 rescued=1`. The rescued task is the bootstrap ping test, which fails before Python is installed. `onboard/dev` held `deb13` in `onboarded` and `webservers` with the connection settings; `normalized/dev` was empty.
3. `10-onboarded` replaced: the old snapshot was deleted, the instance stopped, and `incus snapshot create` ran into its 120-second limit with the instance stopped. No snapshot was created, the daemon showed no pending operation and logged nothing, and the kernel log showed nothing. The instance was started, SSH answered, and an immediate retry with the instance stopped again finished in under a second.
4. Normalize: `ok=51 changed=6 failed=0`, no reboot handler. `deb13` moved to `normalized/dev` with `webservers`, and `onboard/dev` was left with empty groups.
5. `20-normalized` replaced, stopped: every step finished in a second or less.
6. Specialize: port 80 timed out beforehand. `ok=19 changed=3 failed=0`. `curl` returned `deb13`; SSH, sudo and all four firewall rules were present; nginx enabled and active. The inventory did not change.
7. `30-webserver` replaced, stopped: every step finished in a second or less.
8. Normalize again: `ok=48 changed=1 failed=0`. The one change is the in-memory `add_host` in the validation play, which reports `changed` on every run. No reboot handler ran, the boot ID was unchanged, and the hostname stayed `deb13`.
9. Specialize again: `ok=19 changed=0 failed=0`.
10. Both inventory files were byte-identical before and after the two reruns.

The manual SSH checks failed host key verification after the restore, because the node had new host keys and `~/.ssh/known_hosts` held the old one for `10.119.134.49`. Ansible does not check host keys in this configuration, so no run was affected. The checks were repeated with a throwaway known-hosts file, and `~/.ssh/known_hosts` was not edited.

`--syntax-check` passes on `00_discover.yml`, `10_onboard.yml`, `20_normalize.yml`, `30_specialize.yml` and `site.yml`, and `check_converge_boundary.py` passes.

Each normalize log carries `Using run_once with the free strategy is not currently supported`. It comes from the first task of the vendored `robertdebock.selinux` role, which sets `run_once: true` and runs in the free-strategy converge play. The persist play is on the linear strategy and is not affected.
