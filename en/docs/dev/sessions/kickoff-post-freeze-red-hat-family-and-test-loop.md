# Kickoff: Post-Freeze, Red Hat Family Verification and the Test Loop

A kickoff prompt for Claude Code CLI, run from the root of the uc-controller repository on the workstation that hosts the Incus test instances. It follows the pre-freeze decisions and fixes kickoff, whose work is merged into `main` and tagged `v0.1.5-freeze`. It picks up what that session left untested or open, then starts two of the items deferred until after the freeze. Paste everything under Prompt into a new session.

## Prompt

This prompt asks you to verify the lifecycle on a Red Hat family VM and on Ubuntu, pin the roles and collections, and add a repeatable end-to-end check. Work through the phases in order and stop at each checkpoint. Before Phase 0, ask me the questions under Questions for Me, then wait for my answers.

### Read First

- The final report and session record of the previous kickoff: `en/docs/dev/sessions/pre-freeze-decisions-final-report-2026-11-13.md` and `en/docs/dev/sessions/pre-freeze-decisions-session.md`.
- The design document `en/docs/uc-controller-v0.1.5.md`, especially Verification Status, Known Issues, Snapshot Alignment, Firewall Layering (Known Limitation) and Time Sync (Proposal).
- *Incus: Instance Naming*, `en/docs/incus--instance-naming-v0.1.3.md`.
- The guide `en/docs/onboarding/onboarding-a-new-incus-node-deb13.md`, which is the procedure to follow for every node, adjusted for its OS.
- `requirements.yml`, `ansible.cfg`, `inventories/raw/incus.yml`, `ingress/playbooks/10_onboard.yml`, `converge/playbooks/20_normalize.yml`, `converge/playbooks/30_specialize.yml`.

### Project Context

- The architecture is frozen at `v0.1.5-freeze`. Changes in this kickoff fix what verification finds, pin dependencies, and add test tooling. They do not redesign the lifecycle. If a fix would change the architecture, stop and ask.
- The lifecycle is verified on Debian 13 containers only. Untested, and not to be described as working until verified here: `robertdebock.auditd`, the firewalld path of `uc_firewall`, `robertdebock.selinux` and its `Reboot` handler, which has the same name as the handler in `robertdebock.hostname`, and the `webserver` role on a Red Hat family node. Also untested: Ubuntu beyond onboard and normalize, `site.yml` as one invocation, and a reboot caused by an actual hostname change.
- `uc_firewall` is additive: it never removes a rule that is missing from the list.
- `requirements.yml` pins nothing. Roles have no versions, `steelcj.umask` tracks `master`, and `collections: []` is empty although `community.general` and `ansible.posix` are required. Installed at the freeze: `community.general` 13.5.1 and `ansible.posix` 2.2.2.
- On the Red Hat family `robertdebock.ntp` installs chrony, so the Debian trixie `ntp` problem should not apply to a Rocky 9 VM. Do not assume it; check it.

### Ground Rules

- Start from `main` at `v0.1.5-freeze` or later. If `main` is behind the tag, or the working tree holds uncommitted changes other than the live host entries in `inventories/onboard/dev/hosts.yml` and `inventories/normalized/dev/hosts.yml`, stop and ask.
- One branch per phase, each created from the previous phase's branch. Small commits with clear messages. Never push, merge or rebase; I do that by hand.
- Do not edit anything under `roles/`. If a fix would have to go inside a vendored role, stop and report it with options.
- Ask before the first `incus launch`, `incus snapshot restore`, `incus delete` or `incus snapshot create` of the session, and name the instances involved. Never overwrite a `raw` snapshot.
- Free disk space before anything that launches an instance. Check `df -h /` and the pool with `incus storage info default`. If the host root filesystem has less than 30 GB free, or less than the space the next launch needs, stop. List what could be removed, with sizes, and delete nothing without my go-ahead.
- Take every stage snapshot with the instance stopped: `timeout 120` on stop, snapshot and start, then wait for SSH. Check `incus snapshot list` before starting the instance. If a snapshot timed out and was not created, retry it once, still stopped. If the retry also fails, stop and report. When replacing a stage snapshot, delete the old one first.
- Leave live host entries in the stage inventories uncommitted.
- Do not edit `~/.ssh/known_hosts`. If a rebuilt node's host key gets in the way of a manual check, use a throwaway known-hosts file for that check and tell me the `ssh-keygen -R` command.
- `python3 scripts/check_converge_boundary.py` must pass at the end of every phase.
- If something in the repository contradicts this prompt, the repository is the truth. Report the contradiction and ask.

### Questions for Me

Ask these before starting, all together, and wait for the answers. Ask any others that reading the repository raises. During the session, ask me whenever a decision belongs to me rather than guessing, and use the checkpoints for it.

1. **Disk space.** Report free space on the host root filesystem and in the Incus pool, and list instances, images and snapshots with their sizes. Which may be deleted? A Rocky 9 VM needs more room than a container.
2. **Port 443 on `deb13`.** `deb13` and its `30-webserver` snapshot still have the `allow-https` rule from before 443 was removed from the inventory data. Restore `20-normalized`, rerun specialize and retake `30-webserver` (recommended), delete the rule by hand, or leave it?
3. **rky9 as a VM.** Confirm `rky9` is a virtual machine, not a container, so that SELinux and auditd get their own kernel. What CPU, memory and root disk size should it have? Without an answer, use the image defaults and report them.
4. **ubu2404.** Recreate `ubu2404` from `images:ubuntu/24.04` and run the whole chain on it, or skip Ubuntu again?
5. **Pinning policy.** Pin roles and collections to exact versions (recommended), or to minimum versions? For the umask fork, pin to a commit, or should I wait while you tag a release in that repository?
6. **End-to-end check scope.** May the check script restore snapshots by itself when given an explicit flag, or should it only run the playbooks and check results on a node I have already reset?
7. **ansible-lint.** Run it on repository-owned files and report only, fix what it finds, or skip it this round?
8. **Time sync.** If chrony works on the Rocky 9 VM through `robertdebock.ntp` in onboarding, should the Time Sync proposal be closed for the Red Hat family, or left open until the move to normalize?

### Out of Scope

Planned for later. Do not start them, and do not design around them.

- A stage marker fact on the node
- The secrets and vault pattern
- Moving time sync from onboarding to normalize
- TLS for the web server
- Raw sources other than Incus

### Phase 0: Housekeeping

Branch: `docs/post-freeze-housekeeping`

- If `en/docs/onboarding/onboarding-a-new-incus-node-deb13.md` has uncommitted changes, commit them first, as they are.
- Apply my answers to questions 1 and 2. Free the space I approve, and nothing else.
- If 443 is to be removed from `deb13`: after the restore and the specialize run, confirm `ufw status` no longer lists `allow-https` and that `curl` still returns the page. Then retake `30-webserver`, stopped.

Checkpoint: commit, report, and continue without waiting unless something needs my decision.

### Phase 1: A Red Hat Family Node

Branch: `test/rky9`

- With my go-ahead, launch `rky9` from `images:rockylinux/9` with `--vm`, sized as I answered. Use the default image variant, the lightest one. Wait for the guest agent (`incus exec rky9 -- true`), then take the `raw` snapshot, stopped.
- Confirm the raw inventory lists it and that onboarding can reach it over the Incus connection. If the VM cannot be reached the way containers are, report what is needed and ask before changing anything in `ingress/`.
- Run the chain from `raw`, each stage as its own command: onboard with `-e target_group=webservers`, normalize, then specialize with `webserver`. Take each stage snapshot as the stage passes.
- Fix what breaks in repository-owned files. Report anything that would need a vendored role changed.

#### Verify Phase 1

- **SELinux.** From the normalize log, name the handler that runs (`robertdebock.selinux` or `robertdebock.hostname`, both called `Reboot`) and how you know. Confirm the node reboots when SELinux is first configured, compare boot IDs before and after, and confirm `getenforce` reports `Enforcing` afterwards. Do not edit either role.
- **auditd.** `auditd` is active and enabled, and `auditctl -s` shows it enabled.
- **firewalld.** Before specialize, `firewall-cmd --list-all` shows SSH open to all and 9100 open only to `10.0.0.0/24`, as a rich rule. Port 80 is closed from the controller. After specialize, 80 is open, SSH still works, and the earlier rules are still there.
- **webserver.** `curl` from the controller returns `rky9` with SELinux enforcing. Report what the page file replaced (a symlink to the test page, or a file) and its SELinux context.
- **Time sync.** Report whether onboarding installed and started chrony.
- **Reruns.** Normalize again: `failed=0`, `changed=0`, no reboot and no hostname change. Specialize again: `changed=0`.

Checkpoint: commit, then stop and report. Wait for my go-ahead before Phase 2.

### Phase 2: Ubuntu 24.04

Branch: `test/ubu2404`. Skip this phase if my answer to question 4 says so, and say that it was skipped.

- With my go-ahead, launch `ubu2404` from `images:ubuntu/24.04`, a container, default variant. Take the `raw` snapshot, stopped.
- Run the chain from `raw` as in Phase 1, with stage snapshots, and verify as for `deb13` in the guide: login, sudo, umask, the three firewall layers, the page, reruns with `changed=0`.

Checkpoint: commit and continue.

### Phase 3: Pin Roles and Collections

Branch: `chore/pin-versions`

- Pin every role in `requirements.yml` to the version installed now, and list the collections the plays use with their versions, following my answer to question 5. Pin `steelcj.umask` as I answered.
- Install from the pinned file into a temporary roles path and collections path, and compare the result with what is installed now. They must match. Do not touch `roles/` itself.
- Add a short section to the design document on how to bump a pinned version and what to test afterwards.

Checkpoint: commit and continue.

### Phase 4: An End-to-End Check

Branch: `test/e2e-check`

- Add `scripts/e2e_check.py`. For one named node it runs onboard, normalize and specialize, each as its own `ansible-playbook` command with the inventories and extra vars from the guide. After each stage it checks `failed=0` in the recap and that the stage inventories on disk hold the node where they should. Then it reruns normalize and specialize and checks `changed=0`. It exits non-zero on the first failure and prints a short summary.
- Restoring snapshots and resetting the node's inventory entries happen only as my answer to question 6 allows, and only behind an explicit flag. Without it the script refuses a node that is not in raw.
- Python in `scripts/` must run on Linux, macOS and Windows. Incus commands only run where Incus is installed, so the script checks for it and says so if it is missing.
- If my answer to question 7 says so, run `ansible-lint` on `ingress/`, `converge/`, `shared/` and `site.yml`, and report or fix as I answered. Never on `roles/`.

#### Verify Phase 4

- Run the script on `deb13` from `raw`, and on every other node built in this session. Each run passes.
- Make one stage fail on purpose with a temporary extra var, as in the earlier failing-host test, confirm the script stops and reports it, then remove the temporary change.

Checkpoint: commit and continue.

### Final Verification

On the final branch, with my go-ahead for the restores:

1. Check disk space first, as in the ground rules.
2. Restore every test node built or kept in this session to `raw` and run `python3 scripts/reset_inventories.py`.
3. Run `scripts/e2e_check.py` against each node in turn. Every stage ends with `failed=0`, and every rerun with `changed=0`.
4. Run `site.yml` once as a single invocation against one node from `raw` (`deb13`, unless I say otherwise), and report whether it passes. This has never been run.
5. `ansible-playbook --syntax-check` passes on every playbook, including `site.yml`, and `check_converge_boundary.py` passes.

### Documentation

Do each item on the branch of the phase it belongs to.

- Design document: start v0.1.6, following the existing versioning and changelog pattern, and keep v0.1.5 as it is. Update Verification Status to match what was actually verified, per OS and per node type. Do not describe anything as working that was not verified. Record any change to Known Issues.
- Guides: add what differs for a Red Hat family VM and for Ubuntu to the onboarding guide, or write a sibling guide if the differences are large, and say which you chose. Document the end-to-end check script.
- Session record: add one under `en/docs/dev/sessions/`, following the existing pattern.

### Final Report

Print the final report and also write it to a file beside the session record, so it survives the terminal.

- Branches in merge order, with commit counts.
- Each phase and each answer to Questions for Me, with what was done: done, done with a caveat, skipped, or needs my decision.
- The result of the final verification, per node and per stage, including `site.yml`.
- Disk space before and after the session.
- Anything still untested, and why.
- Open questions and anything you chose not to do, with the reason.
