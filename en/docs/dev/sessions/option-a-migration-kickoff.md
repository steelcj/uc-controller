# Option A Migration Kickoff

A kickoff prompt for Claude Code CLI, run from the root of the uc-controller repository on the workstation that hosts the Incus test instances. Paste everything under Prompt into a new session.

## Prompt

You are working in the uc-controller repository, an Ansible controller configuration that moves nodes through discover, onboard, normalize, and specialize. Your job is to close two gaps in the handoff between onboarding and the later stages, then migrate the repository to the Option A layout: one repository with separate `ingress/` and `converge/` directories and shared inventories.

### Read First

Read these before changing anything. If the first one is missing, stop and ask for it.

- `en/docs/option-a-migration-advantages-and-disadvantages-v0.1.1.md`, the analysis this work implements. Its sections Two Gaps to Close First and Order of Work are the specification.
- `playbooks/lifecycle/10_onboard.yml`, the working onboard flow. It is the source of truth for playbook content.
- `scripts/promote_node.py`, `scripts/demote_node.py`, `scripts/reset_inventories.py`
- `ansible.cfg`, `requirements.yml`, and everything under `inventories/`
- `en/docs/bootstrapping an incus container.md`, for the commands used to run and verify onboarding

### Decisions Already Made

Do not reopen these.

- Migrate this repository in place. Do not create a new repository.
- Onboarding is a one-shot transition, not an idempotent one. Running it twice against the same node does not need to work.
- This is the dev phase. No production nodes exist. Existing inventory entries can be swept with `python3 scripts/reset_inventories.py`, and test instances can be reset or recreated.
- The connection contract is four host-level variables in the onboard inventory: `ansible_host`, `ansible_connection: ssh`, `ansible_user: initial`, `ansible_ssh_private_key_file`.
- The key file is `~/.ssh/gradus-raw-initial-id_ed25519`. Define it once as a variable in the onboard inventory's group variables and reference the variable; do not hardcode the path in playbooks or scripts.
- `promote_node.py` is the only code that writes `hosts.yml` entries. Playbooks call it; they do not edit inventory YAML themselves.
- Keep `./roles` on `roles_path`. The Galaxy roles vendored there stay where they are.
- Use the repository's current playbook bodies. Do not copy playbook content from the Option A proposal, which is older.
- Python scripts in `scripts/` must run on Linux, macOS, and Windows and use only the standard library plus PyYAML.

### Ground Rules

- Work in the phases below, in order. Commit at the end of each phase with a clear message. Do not push; pushing is done by hand.
- Stop and report at the end of Phase 1 and wait for a go-ahead before starting Phase 2.
- Do not read, print, copy, or modify private keys or anything under `vaults/`.
- Ask before deleting or restoring any Incus instance or snapshot. Assume the test instance is `ex2-test` (inventory name `ex2-test.default.local`) and confirm that with `ansible-inventory -i inventories/raw/incus.yml --graph` before relying on it.
- Use the activated Ansible virtual environment. If `ansible --version` fails, stop and say so.
- If something in the repository contradicts this prompt, stop and ask instead of guessing.
- Out of scope, do not fix: the firewall variable redesign (`firewall_rules` versus `firewall_services`), the role list in `20_normalize.yml` (it names roles that do not exist, so that playbook cannot run yet), time sync on VMs, and the openssh role issue. Note anything you find and move on.

### Phase 0: Baseline

1. Confirm the working tree is clean and you are on `main`. If `scripts/reset_inventories.py` is present but untracked, commit it on its own.
2. Tag the current commit `v0.1.3-layout`.
3. Run `python3 scripts/reset_inventories.py -n` and report what it would clear. Do not clear anything yet.

### Phase 1: Close the Two Gaps on main

#### Gap 1: Connection Contract

1. In `10_onboard.yml`, the task that re-targets the node over SSH as `initial` already sets `ansible_connection`, `ansible_user`, and `ansible_host`. Add `ansible_ssh_private_key_file` from the new inventory variable.
2. Add that variable to `inventories/onboard/dev/group_vars/all.yml` with a short comment.

#### Gap 2: Persisted Promotion

1. Extend `promote_node.py`:
   - Accept `--address`. When the host is not in the source `hosts.yml` and `--address` is given, create the destination entry instead of failing. Without `--address`, keep the current "host not found" error.
   - When the destination stage is onboard, write the four contract variables onto the host entry. Take the address from `--address` when given, otherwise from the existing entry. Add `--key-file` for the key path.
   - Replace an existing entry for the same host; never add a second one.
   - Keep `--group`, `--no-commit`, and the current behaviour for hosts that are in a static file.
2. Make `demote_node.py` remove the contract variables when a host leaves the onboard stage.
3. Add a final play to `10_onboard.yml` that persists the promotion by calling `promote_node.py` on the controller:
   - one task with `run_once: true`, `delegate_to: localhost`, and `become: no`, looping over `ansible_play_hosts`, so writes to the file are serialized
   - pass `--address`, `--key-file`, `--no-commit`, and `--group` when `target_group` is set
   - take the destination from a variable named `onboard_inventory` (for example `inventories/onboard/dev`), and fail with a clear message at the start of the playbook if it is not defined. Do not derive the path from `playbook_dir`.
4. Fix the existing path bug in `00_discover.yml`: `{{ playbook_dir }}/../inventories` does not resolve to the repository's `inventories/` directory. Do the same for `scaffold.yml`.

#### Verify Phase 1

1. Syntax-check `10_onboard.yml`.
2. Exercise `promote_node.py` and `demote_node.py` with `--no-commit` against a temporary copy of the inventories: a static host, a plugin-style host with `--address`, a repeat promotion of the same host, a demotion, and the error case.
3. With my go-ahead for the instance reset, run the cycle from scratch: reset the instance to its raw state, run `python3 scripts/reset_inventories.py`, then onboard with `-l` on the test instance, `-e target_group=webservers`, and `-e onboard_inventory=inventories/onboard/dev`.
4. Confirm the contract is on disk at host level and wins with the raw inventory loaded in either order:

```sh
ansible-inventory -i inventories/onboard/dev --graph --vars
ansible-inventory -i inventories/raw -i inventories/onboard/dev --host ex2-test.default.local
ansible-inventory -i inventories/onboard/dev -i inventories/raw --host ex2-test.default.local
```

5. Confirm a separate run reaches the node from the onboard inventory alone, over SSH as `initial` with sudo:

```sh
ansible -i inventories/onboard/dev onboarded -m ansible.builtin.ping
ansible -i inventories/onboard/dev onboarded -b -m ansible.builtin.command -a id
```

6. Commit, then stop and report: what changed, the output of steps 4 and 5, and anything that did not work.

### Phase 2: Migrate to the Option A Layout

Do this on a new branch named `option-a`.

1. Move with `git mv`, so history follows:
   - `playbooks/lifecycle/00_discover.yml` and `10_onboard.yml` to `ingress/playbooks/`
   - `playbooks/lifecycle/20_normalize.yml` and `30_specialize.yml` to `converge/playbooks/`
   - `playbooks/lifecycle/artifacts/` to `ingress/playbooks/artifacts/`
   - `playbooks/site.yml` to `site.yml` at the repository root, with its imports updated
   - `playbooks/lifecycle/scaffold.yml` to `tools/scaffold.yml`
2. Delete the stray `10_onboard.yml` at the repository root after confirming the copy under `playbooks/lifecycle/` is the newer one.
3. Create `ingress/roles/` and `converge/roles/` with a `.gitkeep` each. Set `roles_path` in `ansible.cfg` to `./roles:./ingress/roles:./converge/roles:~/.ansible/roles:/usr/share/ansible/roles`.
4. Correct every path that depended on the old playbook locations, including the ones fixed in Phase 1 and the regeneration comment that `scaffold.yml` writes into its output.
5. Add `scripts/check_converge_boundary.py`. It exits nonzero and lists file and line when anything under `converge/` references `ansible_connection`, the `raw` module, or a connection plugin name such as `community.general.incus` or `community.libvirt.libvirt`. It must pass on the migrated tree.
6. Add a `.gitignore` covering `__pycache__/` and stop tracking `scripts/__pycache__/`.
7. Update the commands in the guides under `en/docs` that quote `playbooks/lifecycle/` paths. Leave `en/docs/uc-controller-v0.1.3.md` unchanged; it is a versioned document and v0.1.4 will be written separately.

#### Verify Phase 2

1. `ansible-playbook --syntax-check` on `ingress/playbooks/00_discover.yml`, `ingress/playbooks/10_onboard.yml`, and `site.yml` where the missing normalize roles allow it. Report, do not fix, any failure caused by the out-of-scope role list.
2. `ansible-galaxy role list` still finds the vendored roles.
3. `python3 scripts/check_converge_boundary.py` passes. Add a temporary `when: ansible_connection == 'ssh'` to a converge playbook, confirm the check fails, and remove it.
4. Search the repository, excluding `roles/` and the v0.1.3 document, for `playbooks/lifecycle` and report anything left.
5. With my go-ahead for the instance reset, repeat the from-scratch cycle from Phase 1 using the new playbook path, and repeat the inventory and ping checks.
6. Commit on `option-a`. Do not merge.

### Report

Finish by writing `en/docs/sessions/option-a-migration-session.md` with: what was done in each phase, the commands run for verification and their results, anything left undone or found out of scope, and the commits and tag created. Use plain Markdown with commas instead of em dashes, no numbered headings, no horizontal rules, and no hard-wrapped prose.
