# Option A Migration Session

This session carried out the kickoff prompt in `en/docs/sessions/option-a-migration-kickoff.md`. It closed the two handoff gaps on `main`, added a round of changes requested before Phase 2, and migrated the repository to the Option A layout on the `option-a` branch. The specification was `en/docs/onboarding/option-a-migration-advantages-and-disadvantages-v0.1.1.md`. Every command and its output is recorded in `en/docs/sessions/manual-testing.md`.

## Setup

The prompt named two paths that did not match the repository. The analysis was at `en/docs/onboarding/option-a-migration-advantages-and-disadvantages-v0.1.1.md`, and that location was confirmed. `reset_inventories.py` was under `en/docs/onboarding/` and was moved into `scripts/` by hand. Ansible was not on the path, so the session used `~/.venvs/ansible/current/bin/activate`, which provides ansible-core 2.21.6. The test instance was confirmed as `ex2-test.default.local` in the `raw` group.

## Phase 0: Baseline

The working tree had untracked files. `scripts/reset_inventories.py` was committed on its own, then the remaining untracked documents, `ROADMAP.md`, and `scripts/timestamp_prefix.py` were committed together. The tag `v0.1.3-layout` was created on that commit. A dry run of `reset_inventories.py -n` found every stage inventory already empty and one file in the fact cache.

## Phase 1: Closing the Two Gaps

### Gap 1, the Connection Contract

`inventories/onboard/dev/group_vars/all.yml` defines `onboard_ssh_private_key_file: ~/.ssh/gradus-raw-initial-id_ed25519` once. The `add_host` re-target in `10_onboard.yml` sets `ansible_ssh_private_key_file` from it, alongside the existing `ansible_connection`, `ansible_user` and `ansible_host`.

### Gap 2, Persisted Promotion

`promote_node.py` gained `--address` and `--key-file`. When the host is missing from the source `hosts.yml` and `--address` is given, it creates the destination entry. Without `--address` it keeps the "host not found" error. Promotion into onboard writes the contract onto the host entry, and a repeat promotion replaces the entry. The source file is rewritten only when the host was found in it. `--group`, `--no-commit` and the static-host path are unchanged.

`10_onboard.yml` now asserts at the start that `onboard_inventory` and `onboard_ssh_private_key_file` are defined, and ends with a play that calls `promote_node.py`. That play's single task uses `run_once`, `delegate_to: localhost` and `become: no`, and loops over `ansible_play_hosts`. It passes `--address`, `--key-file`, `--no-commit`, and `--group` when `target_group` is set. Paths are resolved with the `realpath` filter against the directory `ansible-playbook` is started from.

The `{{ playbook_dir }}/../inventories` paths in `00_discover.yml` and `scaffold.yml` resolved to `playbooks/inventories`. They were corrected to `../../`.

### Problems Found During Phase 1

The first promote and demote tests showed that promotion from onboard to normalized stripped the contract. Normalized nodes are still reached over SSH as `initial`, so stripping was limited to moves back to raw.

The first from-scratch run failed at the final SSH check with `Connection refused`. fail2ban had banned the controller. The onboarding key was not in the SSH agent, the agent offered 14 other keys first, sshd's `MaxAuthTries 6` ran out, and each `wait_for_connection` retry added a failure. The key on the node was correct. The ban was lifted with `fail2ban-client set sshd unbanip`, and the key was loaded with `ssh-add`.

The second and third runs passed every check but wrote the key path as `/home/initial/.ssh/...`. Reading `onboard_ssh_private_key_file` instead of `ansible_ssh_private_key_file` did not fix it, because the `command` module expands `~` in arguments by default. The persist task now sets `expand_argument_vars: false`, and the fourth run wrote `~/.ssh/gradus-raw-initial-id_ed25519`.

### Phase 1 Verification

`10_onboard.yml`, `00_discover.yml` and `scaffold.yml` pass `--syntax-check`. The scripts were tested against a temporary copy of the inventories: a static host, a plugin host with `--address`, a repeat promotion, onboard to normalized and back, a demotion, and three error cases. The fourth from-scratch run from the `fresh` snapshot finished with `ok=174 changed=33 failed=0 rescued=1`. The rescued task is the bootstrap connection test, which is expected to fail before Python is installed. `ansible-inventory --host` showed `ssh`, `initial`, `10.119.134.207` and the `~/` key path with the raw and onboard inventories loaded in either order. Ping and `id` with become succeeded from the onboard inventory alone.

## Changes Requested Before Phase 2

`ansible_ssh_common_args: "-o IdentitiesOnly=yes"` is now part of the host-level contract, in both the `add_host` re-target and the entry `promote_node.py` writes. It is not in group variables.

An entry `promote_node.py` creates from `--address` is marked `uc_origin: plugin`. On demotion to raw, a marked host is removed and not written to `raw/hosts.yml`, because its inventory plugin still supplies it. An unmarked host moves back to raw and keeps `ansible_host`. Only `ansible_connection`, `ansible_user`, `ansible_ssh_private_key_file` and `ansible_ssh_common_args` are removed. The temporary-copy checks were extended to both cases, including a plugin host demoted straight from normalized to raw.

`reset_inventories.py` was run and the five empty `hosts.yml` files were committed on their own.

Two from-scratch runs followed. The plan was to unload the key with `ssh-add -d`, but GNOME Keyring kept offering it and prompted for its passphrase during the run. That run therefore had the key available. It passed every check, and fail2ban recorded 0 failures. To make the key truly unavailable, the second run had `SSH_AUTH_SOCK`, `SSH_ASKPASS`, `DISPLAY` and `WAYLAND_DISPLAY` unset. It failed at the SSH check with nothing written to the inventory, and fail2ban recorded 0 failures and no ban. sshd logged only `Connection closed by authenticating user initial [preauth]`, which fail2ban's default sshd filter does not count. OpenSSH's own `PerSourcePenalties` dropped the remaining retries for a short time and cleared on its own.

## Phase 2: The Option A Layout

On the `option-a` branch, `git mv` moved `00_discover.yml`, `10_onboard.yml` and `artifacts/` to `ingress/playbooks/`. It moved `20_normalize.yml` and `30_specialize.yml` to `converge/playbooks/`, `site.yml` to the repository root with its imports updated, and `scaffold.yml` to `tools/`. The stray root `10_onboard.yml` was deleted after a diff showed it was the older copy, missing the umask role and the container time-sync skip. `ingress/roles/` and `converge/roles/` were created with `.gitkeep` files, and `roles_path` is now `./roles:./ingress/roles:./converge/roles:~/.ansible/roles:/usr/share/ansible/roles`.

The ingress playbooks keep `../../`, because `ingress/playbooks/` is the same depth as `playbooks/lifecycle/`. `tools/scaffold.yml` now uses `../`, and its regeneration comment names `tools/scaffold.yml`. `scripts/check_converge_boundary.py` scans every text file under `converge/`, ignores comment lines, and fails with file and line for `ansible_connection`, the raw module, or a source connection plugin such as `community.general.incus` or `community.libvirt.libvirt`. A `.gitignore` covers `__pycache__/`, and `scripts/__pycache__/` is no longer tracked.

The commands in `bootstrapping an incus container.md`, `onboarding-a-raw-dev-node.md` and `fragment-001.md` now use `ingress/playbooks/10_onboard.yml`. Their run commands also gained `-e onboard_inventory=inventories/onboard/dev`, which the playbook now requires. The snapshot reset step in the bootstrapping guide now includes the demotion, or a full `reset_inventories.py`, as the analysis's Order of Work asks. `uc-controller-v0.1.3.md` is unchanged.

### Phase 2 Verification

`ingress/playbooks/00_discover.yml`, `ingress/playbooks/10_onboard.yml` and `tools/scaffold.yml` pass `--syntax-check`. `site.yml` and `converge/playbooks/20_normalize.yml` fail with `The role 'robertdebock.pam' was not found`, which is the out-of-scope role list. The search path in that error confirms the three role directories are in use. `30_specialize.yml` passes when `specialize_role` is given.

`ansible-galaxy role list` finds all 17 vendored roles under `./roles` and lists the two new directories as empty.

`check_converge_boundary.py` passes on the migrated tree. With a temporary `when: ansible_connection == 'ssh'` in `20_normalize.yml` it reports `converge/playbooks/20_normalize.yml:9` and exits 1. With the line removed it passes again. A scratch file also showed it catches `connection: community.general.incus`, `raw:` and `ansible.builtin.raw:`, and ignores a comment and the near-miss name `community.general.incusx`.

The search for `playbooks/lifecycle`, excluding `roles/` and the v0.1.3 document, finds only documents that describe the migration or record earlier commands: the Option A proposal, both versions of the analysis, the kickoff prompt, and the earlier sections of `manual-testing.md`.

The from-scratch cycle using `ingress/playbooks/10_onboard.yml` finished with `ok=174 changed=33 failed=0 rescued=1`. The inventory checks matched Phase 1 in both orders, with `IdentitiesOnly` and `uc_origin: plugin` present. Ping and `id` with become succeeded, and fail2ban recorded 0 failures.

## Left Undone and Out of Scope

These were noted and not fixed:

- `20_normalize.yml` names roles that do not exist (`pam`, `limits`, `timezone`, `motd`, `chrony`), so it and `site.yml` cannot run.
- The firewall variables do not match. The playbooks build `firewall_rules`, while `robertdebock.firewall` reads `firewall_services`.
- Time sync on VMs is not handled.
- On the openssh role, sshd logs `AuthorizedKeysCommand path is not absolute` on every login, although `sshd -T` reports `authorizedkeyscommand none`. Logins are not affected.
- `20_normalize.yml` still uses `wait_for` on port 22 and `add_host` without the contract. It runs in the converge stage, and its handoff to normalized is a later step.

Other observations:

- A demoted static host does not get its original `ansible_user: root` back, because promotion replaced it with `initial` and demotion removes `ansible_user`.
- The guides' `-l ex2-test` limits do not match the plugin's host name, `ex2-test.default.local`. The guides were otherwise left as written.
- With the jsonfile fact cache enabled, `ansible-inventory --graph --vars` prints every cached fact.
- Onboarding needs the key's passphrase. Under GNOME Keyring, the first use in a session raises a passphrase prompt, and a run fails cleanly if the prompt is not answered.
- `inventories/onboard/dev/hosts.yml` holds the live entry for `ex2-test` from the last run. It is left uncommitted on `option-a`, since the empty state is what is committed.
- The SSH key-loading documents in `en/docs` are untracked and were left alone.

## Commits and Tag

The tag `v0.1.3-layout` points at `8252e32`.

On `main`:

- `87e6f3c` Add scripts/reset_inventories.py dev helper
- `8252e32` docs: add onboarding notes, Option A analysis, and session prompt
- `33ca850` Close the onboarding handoff gaps: connection contract and persisted promotion
- `709cb91` Add IdentitiesOnly to the contract and mark plugin-origin hosts
- `fc1fd56` Reset stage inventories to empty
- `1eace4a` docs: record key-loaded and key-unavailable onboarding runs

On `option-a`, not merged:

- `9911d17` Migrate to the Option A layout: ingress/, converge/, shared inventories
- The commit that adds this report

Nothing was pushed.
