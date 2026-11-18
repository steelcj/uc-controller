# Kickoff: Raw Node Admission

A kickoff prompt for Claude Code CLI, run from the root of the uc-controller repository on the workstation that hosts the Incus test instances. It follows the pre-freeze decisions and fixes kickoff. Paste everything under Prompt into a new session.

## Prompt

This prompt asks you to teach the controller to admit a raw node that meets the raw node contract into the raw inventory, so that onboarding can reach it. Work through the phases in order and stop at each checkpoint.

### Read First

- The raw node contract, version 0.3.0: uc-contracts, `en/docs/node-onboarding-pipeline/1-raw-node-egress/uc-raw-node-contract.md`. https://github.com/steelcj/uc-contracts. It is authoritative. Do not change it. If a clause cannot be relied on as written, or seems wrong, stop and tell me.
- In the same repository: the onboarding egress contract 0.3.0, the privileged access policy `en/docs/node-policies/privileged-access/uc-privileged-access-policy.md`, and the decision record `en/docs/decisions/uc-privileged-access-decision-v0.3.0.md`.
- The pre-freeze session record and final report under `en/docs/dev/sessions/`, and the newest `en/docs/uc-controller-v*.md`.
- `ansible.cfg`, `inventories/raw/` (every file), `ingress/playbooks/00_discover.yml`, `ingress/playbooks/10_onboard.yml`, `scripts/promote_node.py`, `scripts/demote_node.py`, `scripts/reset_inventories.py`.

### Project Context

- Lifecycle: `00_discover`, then `10_onboard` (ingress), then `20_normalize` and `30_specialize` (converge). Raw is what the sources report. Each source is a child group of `raw`, with its connection settings in `inventories/raw/group_vars/<source>.yml` and its hosts in its own root-level file in `inventories/raw/`.
- Today there are two sources: `incus` (reached as root through the Incus API) and `discovered` (reached over SSH as root). A node built by uc-ventoy refuses root over SSH, so neither source can reach it. This kickoff adds a third.
- A contract node is reached over SSH as `initial` with the controller's key. Its sudo asks for a password, the batch password, which the controller must hold. Its SSH server accepts keys only. It reports itself in `/var/lib/raw-node/confirmation.yml`, readable by `initial` without sudo.
- `ansible.cfg` sets `host_key_checking = False`, with a comment saying to revisit it before any non-test node is managed. Contract nodes are that point for this source.
- The secrets pattern was put off until after the freeze. Admission needs it now, because the batch password must be stored.
- `scripts/` Python must run on Linux, macOS and Windows.

### Ground Rules

- Start from `main`. If the pre-freeze branches are not all merged into `main`, stop and ask.
- One branch per phase, each created from the previous phase's branch. Small commits with clear messages. Never push, never merge, never rebase. I review, merge and push by hand.
- Do not edit anything under `roles/` (vendored Galaxy roles). Do not print secrets, vault contents or the batch password, in output, logs or commits. No secret is ever written unencrypted inside the repository.
- Do not change `10_onboard.yml` beyond what Phase 3 names. Bringing onboarding in line with the raw node contract is the next kickoff.
- Ask before adding any dependency, Python or Ansible.
- Ask before the first `incus` command that changes an instance, and before connecting to any machine that is not an Incus instance on this workstation.
- `python3 scripts/check_converge_boundary.py` must pass at the end of every phase.
- If something in the repository contradicts this prompt, the repository is the truth. Report the contradiction and ask.

### Out of Scope

- Changing `10_onboard.yml` to onboard contract nodes as `initial` with a password, and the onboarding egress clauses marked "Not yet".
- Implementing the privileged access policy in normalize.
- Making Incus or any other source produce contract nodes.
- Phone-home or DHCP-based discovery.

### Phase 1: Secrets and the Batch Password

Branch: `feat/secrets-and-batch-password`

#### The Secrets Pattern

- Propose a secrets pattern before implementing it, in a short section of the design document. My default is `ansible-vault`, which adds no dependency: encrypted files committed in the repository, and the vault password supplied by a client script named in `ansible.cfg` that reads it from outside the repository (an environment variable or a file under `~/.config/`), never from a file in the repository.
- The proposal says where encrypted files live, how a vault ID separates raw batch secrets from future per-node secrets, how a new operator sets up the vault password, and what `.gitignore` must exclude.
- The privileged access policy calls this "the controller's secret store" and does not name a tool. Keep the policy's wording out of the code.

#### The Batch Password Script

- An import option adds an existing batch, such as raw-2026-11-17-manual, which was made by hand before this script existed. It reads the password from standard input or a prompt, never from the command line, checks that it is at least 15 characters of letters and digits, stores it under the given batch ID, and can mark it current.
- `scripts/new_raw_batch.py` creates a batch: it generates a password of at least 24 characters from letters and digits with Python's `secrets` module, stores it encrypted under a batch ID such as `raw-2026-11-17-01`, marks that batch as the current one, and prints only the batch ID and a SHA-512 crypt hash for uc-ventoy's `initial_password_hash`.
- The password itself is never printed. A separate, explicit option may print it once, for an operator who needs the console, and says so in its help text.
- Python 3.13 has no `crypt` module. Find a way to make the hash that keeps the script cross-platform without a new dependency, such as `openssl passwd -6` when present. If there is none, stop and ask before adding `passlib` or similar.
- Earlier batches stay in the store, so a node built before the current batch can still be admitted. Retiring a batch is a separate, explicit option.

Checkpoint: commit, then stop and report the proposed pattern. Wait for my go-ahead before Phase 2.

### Phase 2: Reading and Checking a Confirmation

Branch: `feat/raw-node-confirmation-check`

- `scripts/check_raw_confirmation.py` reads a confirmation file and checks it against raw node contract 0.3.0. It prints a JSON result: pass or fail, each finding with the clause or field it concerns, and the normalized values the admission play needs. Exit status 0 on pass, 1 on a contract failure, 2 on unreadable input.
- Read the YAML with PyYAML's `BaseLoader`, so that every scalar stays a string. A MAC address of decimal digits, such as `52:54:00:12:34:56`, or an all-digit `machine_id`, is otherwise read as a base 60 integer. uc-ventoy reported this. Convert booleans and the port yourself.
- Checks: exactly one top-level key, which is a valid hostname and not an installer default; every field in the contract's field table present with the right shape; `contract` in a list of supported versions, which starts as `0.3.0` only; `user` equal to the expected `initial_username`; `sudo` true; `sudo_nopasswd` false; `ssh_password_auth` false; `ssh_port` equal to the expected port; at least one host key, each with a type and a `SHA256:` fingerprint; at least one interface address.
- Unknown extra fields are reported as notes, not failures, because a minor contract version may add fields.
- Add fixtures under `tests/fixtures/raw-confirmations/`: one passing file for contract 0.3.0, one per failure, the base 60 MAC case, and the real confirmation below, which is contract 0.1.0 and must fail on its version. Add a test runner that needs only the standard library and PyYAML.

```yaml
deb13-vt-55b1:
  contract: 0.1.0
  baseline: 0.3.0
  timestamp: 2026-11-16T21:46:45-05:00
  machine_id: 726cd88f9b6247428eede867b300aeb6
  user: initial
  sudo: true
  ssh_port: 22
  firewall: foomuuri
  firewall_active: true
  python: /usr/bin/python3
  interfaces:
    - name: enp2s0
      type: ethernet
      mac: 50:b7:c3:6a:55:b1
      state: up
      default_route4: true
      default_route6: false
      ip: [192.168.1.109]
      ip6: []
    - name: wlp1s0
      type: wireless
      mac: c4:85:08:c8:c7:1f
      state: down
      default_route4: false
      default_route6: false
      ip: []
      ip6: []
```

Checkpoint: commit, report, and continue without waiting unless something contradicted this prompt.

### Phase 3: Admission

Branch: `feat/raw-node-admission`

#### A New Raw Source

- Add a source group, `admitted`, as a child of `raw` in `inventories/raw/hosts.yml`, with its connection settings in `inventories/raw/group_vars/admitted.yml`: SSH, user `initial`, the controller key from `onboard_ssh_private_key_file` offered alone, `ansible_become_password` from the current batch in the secret store, and strict host key checking against the controller's known hosts file below.
- Its hosts live in `inventories/raw/admitted.yml`, generated, never committed, and written only by the admission playbook, in the same way `discovered.yml` is written by discovery. Each host carries `ansible_host`, `ansible_port`, `raw_node_contract`, `raw_node_baseline`, `raw_node_machine_id`, `raw_node_macs`, `raw_node_batch` and `raw_node_admitted` (a timestamp).
- Teach `promote_node.py` and `reset_inventories.py` about `admitted.yml`, as they know `discovered.yml`.

#### Host Keys

- Admitted nodes are checked against a known hosts file kept by the controller, not against `~/.ssh/known_hosts`. Propose where it lives and whether it is committed. Host keys are public, so committing is acceptable.
- `host_key_checking = False` stays for the other sources, because Incus test nodes are rebuilt often. Strict checking applies to the `admitted` group through its own settings. If that cannot be done per group, stop and ask.

#### The Admission Playbook

`ingress/playbooks/05_admit.yml`, run on the controller, for one or more candidate addresses given as `-e admit_addresses=...`, or for every host in `discovered.yml` with `-e admit_from_discovered=true`. For each candidate:

1. Fetch the host keys with `ssh-keyscan` on the contract port, into a temporary file only.
2. Connect as `initial` with the controller key, trusting only those scanned keys, and read the confirmation with a plain command, since Python is reported, not promised. A node that refuses the key is not a contract node: report it and move on.
3. Run `check_raw_confirmation.py` on it. On failure, report the findings and do not admit the node.
4. Compare the confirmation's `ssh_host_keys` with the scanned keys. Admit only when they match. If `-e admit_expected_fingerprint=SHA256:...` is given, from the console printout, it must also match. Without it, print a warning that the host key was trusted on first use.
5. Match identity against every stage inventory, using the contract's machine_id and MAC table. Same hostname, same `machine_id`: already known, report and skip. Same hostname, new `machine_id`, known MACs: a reinstall, stop for that node and tell me what to demote. Same hostname with no common identifier: a collision, stop for that node. New on every count: admit.
6. Write the host into `admitted.yml` under its confirmed hostname, add its host keys to the controller's known hosts file, and confirm with an Ansible ping as `initial` and a become with the batch password, both over the strict connection.

The play changes nothing on the node. It may run any number of times.

#### Onboarding

- `10_onboard.yml` targets `raw`, so it would now pick up admitted hosts and handle them wrongly. Exclude the `admitted` group from it with the smallest change that does that, and print one line saying that onboarding contract nodes comes in a later kickoff.

Checkpoint: commit, then stop and report. Wait for my go-ahead before Phase 4.

### Phase 4: Verification and Documents

Branch: `docs/raw-node-admission`

#### Verify Phase 4

- Fixture tests pass.
- Against the uc-ventoy metal node at 192.168.1.109, which I will have rebuilt to contract 0.3.0 with a batch created in Phase 1: admission succeeds, the host is in `admitted.yml` with every field, its keys are in the controller's known hosts file, and ping and become work. Ask before connecting to it. If it still reports contract 0.1.0, admission must refuse it with the version finding; record that and stop.
- Run admission again: the node is reported as already known and nothing changes.
- Change one byte of the known host key on the controller side: the connection must fail. Restore it.
- `admit_from_discovered=true` after a subnet scan admits the contract node and reports every other scanned host as not a contract node, without failing the run.

#### Documents

- Design document: a new version with the `admitted` source, the secrets pattern, the known hosts file and the admission flow.
- `en/docs/contracts.md`, as the uc-contracts README describes: `raw-node` 0.3.0, Ingress; `onboarding-egress` 0.3.0, Egress; `privileged-access` 0.1.0, Implements (partly, from this kickoff on).
- A guide, `en/docs/admitting-a-raw-node.md`: creating a batch, giving uc-ventoy the hash, building and installing, reading the fingerprint at the console, and admitting.
- Record this session in `en/docs/dev/sessions/raw-node-admission-session.md`, and write a final report beside it in the format of the pre-freeze report.

### Done When

- Every phase is committed on its branch, with the boundary check passing.
- The final report has a table with one row per raw node contract clause and field that admission relies on, saying how admission checks it, and one row per privileged access policy clause this kickoff touches (PA-PWD-01, PA-PWD-02, PA-HOST-01, PA-KEY-02), saying whether it is met, partly met or not yet met.
- The final report lists what the next kickoff, onboarding contract nodes, must change in `10_onboard.yml`, with the onboarding egress clauses it will deliver.
