# Kickoff: Onboard Contract Nodes

A kickoff prompt for Claude Code CLI, run from the root of the uc-controller repository on the workstation that hosts the Incus test instances. It follows the raw node admission kickoff, whose final report lists what this one must change. Paste everything under Prompt into a new session.

## Prompt

This prompt asks you to onboard raw nodes that were admitted under the raw node contract, so that they leave onboarding as the onboarding egress contract requires: reached as `initial` with its key, with sudo asking for a password unique to the node, held by the controller. Work through the phases in order and stop at each checkpoint.

### Read First

- In uc-contracts (https://github.com/steelcj/uc-contracts), all authoritative, none to be changed:
  - the onboarding egress contract 0.3.0, `en/docs/node-onboarding-pipeline/2-ansible-ingress-egress-contract/uc-onboarding-egress-contract.md`;
  - the raw node contract 0.3.1;
  - the privileged access policy 0.1.0, `en/docs/node-policies/privileged-access/uc-privileged-access-policy.md`;
  - the decision record `en/docs/decisions/uc-privileged-access-decision-v0.3.0.md`.

  If a clause cannot be met as written, or seems wrong, stop and tell me.
- `en/docs/sessions/2026-11-18--17-13-55-final-report-raw-node-admission.md`, above all "What the onboarding kickoff must change" and the privileged access policy table, and the session record beside it.
- `en/docs/uc-controller-v0.1.7.md`: Admission, Secrets, Raw Inventory, and the `10_onboard.yml` and `20_normalize.yml` sections.
- `en/docs/guides/vault-guide.md` and `en/docs/admitting-a-raw-node.md`.
- `ansible.cfg`, `ingress/playbooks/05_admit.yml`, `ingress/playbooks/10_onboard.yml`, `converge/playbooks/20_normalize.yml`, `inventories/raw/group_vars/admitted/main.yml`, `inventories/onboard/dev/group_vars/all.yml`, `scripts/promote_node.py`, `scripts/demote_node.py`, `tests/test_admit_playbook.py`.

### Project Context

- **The lifecycle:** `00_discover`, `05_admit` and `10_onboard` (ingress), then `20_normalize` and `30_specialize` (converge). Converge must not know where a node came from, and `scripts/check_converge_boundary.py` holds it to that.
- **Admitted nodes.** A node admitted by `05_admit.yml` sits in the `admitted` group of `inventories/raw/admitted.yml`, with `raw_node_batch` and its other `raw_node_*` fields.
  - It is reached over SSH as `initial` with `onboard_ssh_private_key_file` alone, with strict host key checking against the committed `ssh/known_hosts` under `HostKeyAlias=<inventory_hostname>`.
  - Its become password is its batch passphrase, `vault_raw_batch_passwords[raw_node_batch]`, from `inventories/raw/group_vars/admitted/vault.yml`, vault ID `batches`.
  - `10_onboard.yml` targets `raw:!admitted` today and prints one line saying admitted nodes are left for this kickoff.
- **Onboarding today assumes a root connection,** over Incus or SSH as root: the bootstrap, the baseline roles, then a switch to SSH as `initial`. Specifically:
  - The re-onboarding guard (`id initial`) is commented out, because `initial` exists on every contract node.
  - `inventories/onboard/dev/group_vars/all.yml` still gives `initial` `sudo_options: "ALL=(ALL) NOPASSWD: ALL"`. That is OE-CON-02, retired in contract 0.3.0.
- **Promotion.** `promote_node.py` keeps a host's strict host key settings when it promotes it out of raw. It does not carry a become password: that is a group variable of `admitted`, and onboarding is to replace the batch passphrase with a password unique to the node (OE-ACC-03).
- **Secrets** are plain Ansible Vault. One vault ID per kind of secret, each with a passphrase file `~/.config/uc-controller/vault/<id>` (mode 600), named in `vault_identity_list` in `ansible.cfg`. `batches` exists. `node` is reserved for secrets of single nodes, and has no passphrase file yet. Every Ansible run reads every vault ID listed, so adding `node` means every operator needs its file.
- **The test node** is `deb13-vt-0001`, a uc-ventoy metal node at 203.0.113.10, contract 0.3.0, baseline 0.4.0, batch `raw-1970-01-01-01`. Its keys are in `ssh/known_hosts`, but `inventories/raw/admitted.yml` is generated and not committed, so it must be admitted again on this checkout first. It is metal: there are no snapshots. Onboarding it changes it for good, and repeating a run from raw means rebuilding it with uc-ventoy.
- **Direction.** Raw node creation is to move out of this controller, so that every raw node arrives through admission. The root-connection sources, Incus and the subnet scan's root SSH, stay for now. This kickoff does not remove them.
- `scripts/` Python must run on Linux, macOS and Windows.

### Ground Rules

- **Worktree.** Work in a git worktree beside the repository, such as `../uc-controller-onboard`. Never switch branches in `~/areas/development/uc-controller`, and never touch its uncommitted files.
- **Branches.** One branch per phase, each created from the previous phase's branch, starting from `main`. Small commits with clear messages. Never push, never merge, never rebase. I review, merge and push.
- **Roles.** Do not edit anything under `roles/` (vendored Galaxy roles).
- **Secrets.** Never print, log or commit a secret in plain text: not a passphrase, a password, or vault contents. Tasks that handle one use `no_log`. Show me commands, not values. No secret is ever written unencrypted inside the repository, and not to a plain file outside it either, except a vault passphrase file of mode 600.
- **Dependencies.** Ask before adding any dependency, Python or Ansible.
- **Machines.** Ask before the first `incus` command that changes an instance, and before connecting to any machine that is not an Incus instance on this workstation. For `deb13-vt-0001`, ask before each run that changes the node, and stop and report after each one.
- **Checks.** `python3 tests/run_tests.py` and `python3 scripts/check_converge_boundary.py` must pass at the end of every phase, and every playbook must pass `--syntax-check`.
- **Exit status.** Keep the rule from admission: a playbook that leaves a node in a state needing the operator exits non-zero, after its report.
- **Documents.** Write them in the house style from sat-doc-automa: commas rather than em dashes, no heading numbers, no horizontal rules, no hard-wrapped prose, subsections as lower-level headings, and APA 7 Citation Anchor Pairs where you cite.
- **Conflicts.** If something in the repository contradicts this prompt, the repository is the truth. Report the contradiction and ask.

### Out of Scope

- The firewall clauses OE-FW-01 to OE-FW-05 and OE-FWM-01 to OE-FWM-03 (Foomuuri). They stay "Not yet" unless I decide otherwise at the Phase 1 checkpoint.
- Phone-home discovery, proposed in the admission final report.
- Making Incus or any other source produce contract nodes, and moving raw node creation out of this controller.
- Normalization's own work under the privileged access policy: the automation and administrator accounts, deleting `initial`, locking `root`, the console clauses, and password expiry.
- Converting the design document to Citation Anchor Pairs, a separate follow-up.

### Phase 1: Design and Node Secrets

Branch: `feat/onboard-contract-nodes-design`

Propose, in a short section of a new design document version (v0.1.8), before implementing anything. Each item states the choice and why:

- **Where node passwords live.**
  - The file or files, encrypted with the vault ID `node`.
  - How a playbook in any stage finds a node's password, as onboarding, normalization and specialization will all need it as the become password.
  - What happens to it when a node is promoted, demoted, reset or retired.
  - Whether `promote_node.py` must change.
- **How a node's password is made and stored.**
  - Generated on the controller, never chosen, at least 15 characters, letters and digits (PA-PWD-01, OE-ACC-03).
  - Unique to the node (PA-PWD-02).
  - Never displayed and never written in plain text.
  - Say whether the Ansible version in the controller's virtual environment can do this with what it ships (the `password` lookup, the `vault` filter, `password_hash`), or whether it needs something new. Python 3.12 still has the deprecated `crypt` module, 3.13 does not. If a dependency is needed, stop and ask.
- **How the password is set on the node and becomes the become password.**
  - Setting it on the node, with `robertdebock.users` (`password`, `update_password`) or another way, without breaking the next task's become.
  - The order of the steps, so that no run can leave a node whose password the controller does not hold.
  - What a run does if it fails between setting the password and storing it.
- **The `node` vault ID.**
  - Its passphrase, made with dice by the operator, as for `batches`.
  - Its file, and its entry in `vault_identity_list`.
  - What the vault guide must add.
- **How `10_onboard.yml` handles admitted nodes.**
  - A separate play or a source-aware path.
  - How it connects (as `initial`, become with the batch passphrase).
  - How it bootstraps Python with `raw` and become when the confirmation reported none.
  - What replaces the re-onboarding guard.
  - How it promotes into the onboard inventory.
- **Whether the root-connection sources change too.** Contract 0.3.0 retires OE-CON-02 for every onboarded node. Say whether Incus and root-SSH nodes also move to a per-node password and sudo with a password in this kickoff, what that means for the converge test loop on `deb13`, `ubu2404` and `rky9`, and what you recommend. I decide at the checkpoint.

Then add the `node` vault ID to the vault guide, as a section I can follow, and stop. The `ansible.cfg` change waits until I have made the passphrase file.

Checkpoint: commit, then stop and report the proposals. Wait for my go-ahead before Phase 2.

### Phase 2: Onboarding Admitted Nodes

Branch: `feat/onboard-contract-nodes`

Implement the design as agreed. At least:

- **`10_onboard.yml` onboards admitted nodes.** It connects as `initial` with the batch passphrase for sudo, bootstraps Python when needed, and applies the onboard baseline. It leaves the root-connection sources as agreed in Phase 1.
- **sudo asks for a password.** No sudoers rule for `initial` contains `NOPASSWD` or `!authenticate` (OE-ACC-04). The play tests this by searching `/etc/sudoers` and `/etc/sudoers.d`, with comment lines ignored.
- **A password unique to the node.** `initial` gets one, generated, stored encrypted under the vault ID `node`, and set on the node (OE-ACC-03). The batch passphrase no longer works for that node.
- **Become proved.** `initial` obtains root with that password, tested by running `id` with become and the password from the vault (OE-CON-05).
- **SSH proved key-only.** `sshd -T` shows `passwordauthentication no`, `kbdinteractiveauthentication no`, `permitemptypasswords no` and `permitrootlogin no` (OE-SSH-03).
- **Promotion.** The node is written to the onboard inventory with its connection settings, strict host key settings and a become password that resolves to its own password. The run leaves no node whose password the controller does not hold.
- **Run again.** A second run on an onboarded node changes nothing and does not generate a new password.
- **Tests.** Offline tests for whatever can be tested offline: any new script, the guard, the order of password steps, and that no password or passphrase is printed at `-vvv`. Use stand-ins in the style of `tests/test_admit_playbook.py` where the real roles are not needed.

Checkpoint: commit, report, and stop. Wait for my go-ahead before Phase 3, which changes the metal node.

### Phase 3: Verification on deb13-vt-0001

Branch: `test/onboard-contract-nodes`

Ask before each step, and stop and report after each one:

1. Admit `deb13-vt-0001` on this checkout, with a candidates file and the fingerprint I read at the console. It must be reported `known` against `ssh/known_hosts`, or admitted with the same keys.
2. Before onboarding, show me what the run will change on the node. Run `10_onboard.yml` with `--check --diff` first, if the roles support it, or list the roles and settings that apply.
3. Onboard it. Report every clause of the onboarding egress contract this kickoff touches, with how it was proved.
4. Show that the batch passphrase no longer gives root, that the node's own password does, and that no password is printed.
5. Run onboarding again: nothing changes and the password stays the same.
6. Run `20_normalize.yml` only if I agree at that point. It changes much more on a metal node.

If the node ends in a state the controller cannot reach with its own credentials, stop at once and tell me what you know. Do not try to repair it without asking.

### Phase 4: Documents

Branch: `docs/onboard-contract-nodes`

- **Design document:** v0.1.8, with the onboarding path for admitted nodes, node secrets and the verification results.
- **`en/docs/contracts.md`:** updated for what onboarding now delivers.
- **The vault guide:** the `node` vault ID, and what to do when a node's password is exposed.
- **The operator's guide:** a guide for onboarding an admitted node, or a section in `en/docs/admitting-a-raw-node.md` that continues it. Your call, with the reason.
- **Session record and final report** in `en/docs/sessions/`, named as the sessions README says, the report in the format of the raw node admission final report.

### Done When

- Every phase is committed on its branch, with the tests, the syntax checks and the boundary check passing.
- The final report has:
  - a table with one row per onboarding egress clause, saying whether it is delivered, not yet delivered or retired, and how it is proved. At least OE-CON-01 to OE-CON-05, OE-ACC-01 to OE-ACC-04, OE-SSH-01 to OE-SSH-03 and OE-INV-01;
  - one row per privileged access policy clause this kickoff touches, saying met, partly met or not yet met. At least PA-PWD-01, PA-PWD-02, PA-ESC-01 and PA-NET-01;
  - what normalization now receives, against the contract's "What normalization receives";
  - the root-connection sources: what was decided for them and what remains;
  - follow-ups for the next kickoff.
