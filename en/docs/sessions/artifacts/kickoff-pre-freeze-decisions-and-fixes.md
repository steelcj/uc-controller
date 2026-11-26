# Kickoff: Pre-Freeze Decisions and Fixes

A kickoff prompt for Claude Code CLI, run from the root of the uc-controller repository on the workstation that hosts the Incus test instances. It follows the multi-source raw inventory, Option A review, and speed settings kickoff, and it closes the items left open in that session's final report. Paste everything under Prompt into a new session.

## Prompt

This prompt asks you to apply three decisions and five fixes so that the architecture can be frozen. Work through the phases in order and stop at each checkpoint.

### Read First

- The session record and final report of the previous kickoff, under `en/docs/dev/sessions/`.
- The current design document, the newest `en/docs/uc-controller-v*.md`.
- The Incus instance naming document, if it is in the repository.
- `converge/playbooks/20_normalize.yml`, `converge/playbooks/30_specialize.yml`, `ingress/playbooks/10_onboard.yml`, `scripts/promote_node.py`, `scripts/demote_node.py`.

### Project Context

- The project is in its dev phase. There are no production nodes. Test nodes are Incus containers and VMs on this machine and can be rebuilt freely.
- Lifecycle: `00_discover` then `10_onboard` (ingress), then `20_normalize` and `30_specialize` (converge). Inventories are staged: `inventories/raw/`, `inventories/onboard/<env>/`, `inventories/normalized/<env>/`.
- Onboarding is not idempotent, and that is accepted. Normalize and specialize are expected to be safe to rerun.
- Incus instances are named by OS code only (`deb13`, `ubu2404`, `rky9`) and are never renamed. State lives in snapshots: `raw` is the origin, then `10-onboarded`, `20-normalized`, `30-<role>`. `tmp-` is scratch.
- `scripts/promote_node.py` is the only code that writes host entries into stage inventories. Playbooks call it, they do not edit inventory YAML themselves. Python in `scripts/` must run on Linux, macOS and Windows.

### Ground Rules

- Find the starting point first. The previous kickoff left five stacked branches, ending with `perf/ansible-cfg`. If they are merged into `main`, start from `main`. If not, start from the tip of the stack. If the state is anything else, stop and ask.
- One branch per phase, each created from the previous phase's branch. Small commits with clear messages. Never push, never merge, never rebase. I review, merge and push by hand.
- Do not edit anything under `roles/` (vendored Galaxy roles) or `vaults/`. Do not print secrets or vault contents. Repository-owned roles go in `converge/roles/` or `ingress/roles/`.
- Ask before the first `incus launch`, `incus restore`, `incus delete` or `incus snapshot create` of the session, and name the instances involved. Never overwrite a `raw` snapshot.
- Leave live host entries in the stage inventories uncommitted.
- `python3 scripts/check_converge_boundary.py` must pass at the end of every phase.
- If something in the repository contradicts this prompt, the repository is the truth. Report the contradiction and ask.

### Out of Scope

These are planned for after the freeze. Do not start them, and do not design around them.

- A stage marker fact on the node
- Pinning role and collection versions
- The secrets and vault pattern
- An automated end-to-end check, `ansible-lint`, or commit hooks

### Phase 1: Decisions

Branch: `fix/pre-freeze-decisions`

#### Hostname Reboot Stays

- Leave `hostname_reboot` at the role default. A reboot after a hostname change is wanted.
- The reboot is a handler that runs after all roles in the play, and only when the hostname changed. `robertdebock.selinux` flushes handlers partway through its own tasks, so `robertdebock.hostname` must stay after `robertdebock.selinux` in the role list, or the reboot would fire mid-play.
- Add a comment to that effect beside the role list in `20_normalize.yml`, and record it in the design document.

#### SELinux Only on Red Hat Family Nodes

- Apply `robertdebock.selinux` only when `ansible_os_family == 'RedHat'`. On Debian and Ubuntu its defaults would install a policy, set enforcing mode and reboot, on systems that use AppArmor.
- A condition on OS family is not a source condition and is allowed in converge.
- Do not change the role's variables for Red Hat family nodes.

#### Vault Instruction Removed From the Onboarding Guide

- In `en/docs/onboarding-a-raw-dev-node.md`, remove the instruction that tells readers to create vault files.
- Replace it with one sentence saying the secrets pattern is not decided yet and nothing in the lifecycle reads a vault today.

#### Experimental Scaffold Removed

- Delete the experimental scaffold playbook and remove references to it from the guides. It writes the wrong data type, nothing depends on it, and git keeps the history. Move its entry in the design document to a one-line changelog note.
- If you find that something does depend on it, stop and ask instead.

Checkpoint: commit, report, and continue without waiting unless something contradicted this prompt.

### Phase 2: Promotion and Demotion

Branch: `fix/normalize-promotion`

#### Normalize Persists Its Own Promotion

- Give `20_normalize.yml` the same ending that `10_onboard.yml` has: a final play that calls `promote_node.py` on the controller to move each successfully normalized host from the onboard inventory to the normalized inventory.
- One task, `run_once: true`, `delegate_to: localhost`, `become: no`, looping over the hosts that completed the play, with `--no-commit`. Keep this play on the default linear strategy even though the converge play uses `strategy: free`.
- Take the destination from a required variable, named to match the one onboarding uses, and fail early with a clear message if it is missing.
- The host's connection settings and group memberships carry over unchanged. A host that failed normalize is not promoted.

#### Demotion Keeps Group Memberships

- Demoting from normalized to onboard currently drops extra groups such as `webservers`. Make it keep every group the host was in, other than the stage group itself.
- Demotion to raw is unchanged.

#### Verify Phase 2

- Exercise promote and demote against a temporary copy of the inventories: onboard to normalized and back with a host in an extra group, a host in no extra group, and a repeat promotion.
- From `10-onboarded` on one existing node, run normalize as its own command and confirm the host is in the normalized inventory on disk afterwards with its groups and connection settings, and gone from the onboard inventory.

Checkpoint: commit, then stop and report. Wait for my go-ahead before Phase 3.

### Phase 3: A Minimal Specialize Role

Branch: `feat/specialize-webserver`

`30_specialize.yml` has never run. This phase proves the fourth stage and the third firewall layer with the smallest role that can do it.

- Create a repository-owned role `webserver` in `converge/roles/`. It installs nginx, enables and starts it, and serves a one-line static page that names the host. It must work on Debian family and Red Hat family nodes. Nothing else.
- Open HTTP at the specialize layer through the firewall mechanism that the `feat/firewall-rules` branch put in place, as inventory data for the `webservers` group. Do not open the port from inside the role, and do not invent a second mechanism.
- Make `30_specialize.yml` fail early with a clear message when `specialize_role` is not set.
- No TLS, no virtual hosts, no templated site configuration. This role exists to exercise the stage.

#### Verify Phase 3

- Before specialize, from the controller, port 80 on the node is closed and SSH works.
- Run `30_specialize.yml` with `-e specialize_role=webserver` as its own command. `failed=0`.
- After specialize, `curl` from the controller returns the page, SSH still works, and the rules from the onboard and normalize layers are still present.
- Run `30_specialize.yml` a second time. It reports no changes.
- With my go-ahead, take a `30-webserver` snapshot.

Checkpoint: commit and continue.

### Phase 4: A Red Hat Family Node

Branch: `test/rky9`

The auditd and firewalld paths, and now the SELinux role, are untested. One Rocky 9 node covers all three.

- With my go-ahead, launch a Rocky 9 instance named `rky9` as a virtual machine, not a container. SELinux and auditd need their own kernel. Take the `raw` snapshot after first boot has finished.
- Confirm the raw inventory lists it and that onboarding can reach it. If the VM cannot be reached the way raw containers are, report what is needed and ask before changing anything in `ingress/`.
- Run the whole chain from `raw`, each stage as its own command: onboard, normalize, specialize with `webserver`. Take the stage snapshots as each stage passes.
- Fix what breaks in repository-owned files. If the fix would have to be made inside a vendored role, stop and report it instead.
- Run normalize a second time and confirm there is no reboot and no hostname change.

Checkpoint: commit and continue.

### Final Verification

On the final branch, with my go-ahead for the restores:

1. Restore `deb13` and `rky9` to `raw` and run `python3 scripts/reset_inventories.py`.
2. Run onboard, normalize and specialize in order, each as its own command, against both nodes. Every run ends with `failed=0`.
3. Confirm each stage inventory on disk matches where each node is.
4. Confirm `ansible-playbook --syntax-check` passes on every playbook, including the root `site.yml`.
5. Confirm `python3 scripts/check_converge_boundary.py` passes.

### Documentation

Do each item on the branch of the phase it belongs to.

- Design document: add a new version following the file's existing versioning and changelog pattern. Cover the hostname and SELinux decisions, normalize's persisted promotion, the demotion rule, the `webserver` role and how a specialize role contributes firewall rules, and the removal of the scaffold.
- Guides under `en/docs`: update the commands so the full chain from raw to specialized can be followed as written.
- Session record: add one under `en/docs/dev/sessions/`, following the existing pattern.

### Final Report

Print the final report and also write it to a file beside the session record, so it survives the terminal.

- Branches in merge order, with commit counts.
- Each decision and each fix in this prompt, with its status: done, done with a caveat, or needs my decision.
- The result of the final verification, per node and per stage.
- Anything untested, and why.
- Open questions and anything you chose not to do, with the reason.
