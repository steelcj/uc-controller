# Changelog

All notable changes to this repository are recorded here, in the format of [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). The repository follows [Semantic Versioning](https://semver.org/).

Write entries in the Unreleased section below as work happens. `scripts/cut-release.py` turns that section into a dated version section when a release is cut.

## [Unreleased]

For 0.2.0: admission's sources and names change, and the firewall role changes on every stage.

### Added

- `en/docs/sessions/2026-11-26--16-20-08-uc-controller-repository-recreation-session.md`, the record of cleaning the tree of real values, the merge, the recreated repository and release 0.1.7.
- The handover work's records: the plan and kickoff, `en/docs/sessions/2026-11-27--17-58-28-uc-controller-handover-plan-and-kickoff.md`, the step report for steps one to five, `…-19-42-25-uc-controller-handover-step-report.md`, and the run report for step six on example-org, `…-20-03-53-uc-controller-handover-run-report.md`.
- `05_admit.yml` admits uc-node's candidates with `admit_from_candidates=true`: every file in the client inventory's `candidates/` whose `raw_node_batch` is `admit_batch_id`. Each gives the node's name, address, port and the host key fingerprint uc-node read through its platform. A `dev`, `stage` or `prod` candidate is refused, before it is contacted, unless the run's onboard stage is `onboard/<label>`; a `raw` one goes with any. A candidate file that is not valid is reported and skipped, and the run exits 2. Admission never changes `candidates/`.
- `scripts/read_candidates.py` reads the candidates of a batch with PyYAML's `BaseLoader` and checks each against the raw node handoff design's candidate fields, for admission and for `check_inventory.py`.
- `inventory-template/` gains `intake/` and `candidates/`, uc-node's, each with a `.gitkeep` and a line in its README.
- `check_inventory.py` checks every file in `candidates/` as admission reads it, and refuses a host that came through admission whose name is not a fully qualified domain name: every admitted host, and every onboarded or normalized host carrying `raw_node_batch`.
- `en/docs/guides/admit-and-onboard.md`: admitting from `candidates/`, the admitted name, admitting by address with `admit_client_domain`, moving a node admitted under its hostname, and the Foomuuri fragments each stage writes.
- `roles/steelcj.foomuuri`, vendored at the commit `requirements.yml` pins, as the other roles are.
- `tests/test_firewall_fragments.py` renders the fragment each playbook's `steelcj.foomuuri` call writes, from the client inventory template's values.

### Changed

- Admission names an admitted node by its fully qualified domain name, never its hostname alone: the candidate's name, or `<hostname>.<admit_client_domain>` for `admit_addresses` and `admit_from_discovered`, which now require `admit_client_domain`. It refuses a confirmation whose hostname is not the name's first label, and a name that is not fully qualified. The name is used in `raw/admitted.yml`, `ssh/known_hosts` and `HostKeyAlias`, the identity match and the report. A node admitted before 0.2.0 under its hostname is stopped as known under another name, until its entry and keys are removed.
- `match_raw_identity.py` takes `--name` in place of `--hostname`, and compares the whole name.
- The firewall is `steelcj.foomuuri` on every stage. `10_onboard.yml` writes the base fragment `10-base` from `firewall_onboard_ssh`, replacing uc-node's bootstrap rule, and refuses to run unless it gives SSH on the port the controller uses. `20_normalize.yml` writes `20-normalize` and `30_specialize.yml` writes `30-specialize` from their service lists, each refusing a node without `10-base`. Every call keeps the other two fragments and removes any other, and a stage with no service removes its own fragment. The role removes ufw and firewalld. The client inventory's variables keep their names and shape.
- `scripts/new-inventory` makes the branch `main`, and prints the path it made, that no commit was made, and the next step, uc-node's guide 0.
- The client inventory template's yamllint `line-length` is a warning at 120, which the pre-commit hook shows and does not stop on, since public key lines run past any limit.
- `inventory_hosts.py`, and so the identity match, skips `intake/` and `candidates/`.
- `en/docs/guides/client-inventories.md` 0.2.0, `en/docs/guides/batch-secrets.md` 0.1.5, `05_admit.yml`'s usage comment, the README and the ROADMAP follow these changes. Commands use `~/.private/uc/example-org/uc-inventory` and `raw-YYYY-MM-DD-NN`. `en/docs/admitting-a-raw-node.md` says it describes 0.1.x and points at the new guide.
- Tests use the safe values register's host names, machine IDs and MAC addresses.

### Removed

- `admit_candidates`, the list of `{address, fingerprint}` given with `-e @<file>`. A run that gives it is refused with a message naming `admit_from_candidates`.
- `shared/roles/uc_firewall`, `shared/vars/uc_firewall_interim.yml` and `tests/test_uc_firewall_interim.py`.

## [0.1.7] - 2026-11-26

This is the first release from the recreated repository. Earlier releases were published from the earlier repository, which no longer exists.

### Added

- `LICENSE` holds the GNU Affero General Public License version 3, and `README.md`'s License section states `SPDX-License-Identifier: AGPL-3.0-or-later` with the notice that the program may be used under version 3 or any later version.
- `uc_secret`, a lookup plugin in `shared/plugins/lookup/`, is the one way anything reads a secret. It reads `~/.secrets/uc/fleet/<path>.yml`, uc-controller's half of `~/.secrets/uc/`, and refuses a path outside that root, directories that are not mode 0700, files that are not mode 0600, and files or directories not owned by the user.
- `en/docs/guides/batch-secrets.md`: the layout and modes of batch files, how to create one without the password reaching shell history or the process list, and how to retire a batch.
- `inventory-defaults/`, one directory per stage (`raw/`, `onboard/`, `normalized/`), holding the group structure and every piece of logic, and no hosts or client values. Client inventories are loaded after it.
- `inventory-template/`, the layout of a client inventory repository: facts only, with generated files committed, `ssh/known_hosts`, and a pre-commit hook.
- `scripts/new-inventory` makes a client inventory repository from the template; `scripts/inventory-args` prints the `-i` options for a client's stages, defaults first; `scripts/check_inventory.py` refuses a client inventory that holds logic or secrets.
- `en/docs/guides/client-inventories.md`: what a client inventory repository holds and never holds, making one, running playbooks against it, its pre-commit hook, and handing it to a client who leaves.
- `en/docs/uc-controller-v0.1.8.md`, the design for client inventories and batch files; v0.1.7 is kept as it was.
- `README.md` describes uc-controller, its stages, what lives outside it, and the guides.
- `shared/vars/uc_firewall_interim.yml` turns the client inventory's per-stage firewall values into the rule list `uc_firewall` reads, until the switch to `steelcj.foomuuri`; `tests/test_uc_firewall_interim.py` checks it gives the rules the old lists gave.

### Changed

- Batch passwords are read through `uc_secret` from `~/.secrets/uc/fleet/batches/<batch>.yml`, a file holding `initial_password` only (uc-node will read the hashes from its own file, `~/.secrets/uc/build/batches/<batch>.yml`), for the admitted group's become password and for the RN-ACC-08 check in `05_admit.yml`. Runs no longer need a vault passphrase file, and `ansible.cfg` no longer sets `vault_identity_list`.
- Every playbook runs against a client inventory, given with `scripts/inventory-args`, and refuses to run without one. Its first play, on localhost, runs `shared/tasks/require-client-inventory.yml`, which also finds the client inventory's root and stages from the `-i` sources. `ansible.cfg` no longer names an inventory.
- `10_onboard.yml` and `20_normalize.yml` take their onboard and normalized environments from the stages loaded, instead of `-e onboard_inventory=...` and `-e normalized_inventory=...`. `00_discover.yml` and `05_admit.yml` write into the client inventory's `raw/` and `ssh/known_hosts`.
- `en/docs/admitting-a-raw-node.md` gives the new invocation, batch files, and committing `raw/admitted.yml` and `ssh/known_hosts` in the client inventory repository.
- `promote_node.py`, `demote_node.py`, `match_raw_identity.py` and `reset_inventories.py` take the client inventory's root with `--inventory`, and stages by name (`--from raw --to onboard/dev`). The generated files' headers say they are committed.
- The 2026-11-16 raw node admission kickoff shows the form of a batch ID as `raw-1970-01-01-01`, the register's general example.
- Every tracked file names example values in place of the real node's host name, address, MACs and machine id, the real subnet, and the two real batches, so the recreated repository starts clean. `00_discover.yml`'s default `discover_subnet` is `198.51.100.0/24`. The real 0.1.0 confirmation fixture is `fail-real-deb13-vt-0001-contract-0.1.0.yml`, with its shape and failures kept.
- `requirements.yml` pins `community.general` 14.0.1 and `robertdebock.bootstrap` 7.3.1, adds `steelcj.foomuuri` from git at a pinned commit, since it has no release yet, quotes every version, says why each collection is needed, and lists roles under consideration as comments.
- Every SHA256 fingerprint in documents and test fixtures is one of the register's examples, `SHA256:EXAMPLEexampleEXAMPLEexampleEXAMPLEexample0` and up, 43 characters after `SHA256:` as `ssh-keygen -l` prints them, or a prefix of one. Where several host keys are listed, each has its own: `…example0` for ed25519, `…example1` for ecdsa.
- Addresses on the workstation's Incus bridge are examples under `10.0.0.0/24`: the `ex2-test` container is `10.0.0.21`, the bridge's own address `10.0.0.1`, other hosts keep their last number, and SSH config wildcards name `10.0.0.*`. The shell prompt in `setup-ansible-venvs.md` is `operator@workstation`.
- Example outputs and paths on the controller use the home `/home/operator`; paths on a node keep `/home/initial`, the bootstrap account's home. A key fingerprint in `manual-testing.md` is an example value.
- Key file names use `example-org` in place of the client's name, as in `~/.ssh/example-org-raw-initial-id_ed25519`, and the older versioned docs use `203.0.113.11` in place of a LAN address. The real key path stays in the client inventory, as `onboard_ssh_private_key_file`.
- The plan's last section recreates the repository with no history, and `CONTRIBUTORS.md` records that as the one exception to never reusing tags and releases.
- Examples and tests use the batch name `raw-1970-01-01-01`, the Unix epoch, a date no real batch can have, in place of `raw-EXAMPLE-01`, which did not follow the `raw-YYYY-MM-DD-NN` pattern. Nothing validates the pattern; `05_admit.yml` and `scripts/check_inventory.py` require only a non-empty name, and `uc_secret` only a safe path.
- The firewall values are renamed and shaped for `steelcj.foomuuri`: `firewall_rules_onboard` becomes `firewall_onboard_ssh` (`port`, `sources`), and `firewall_rules_normalize` and `firewall_rules_specialize` become `firewall_normalize_services` and `firewall_specialize_services`, lists of `name`, `protocol`, `sources` and `state`, as `foomuuri_services` takes them. The rules applied are the same.

### Removed

- `inventories/raw/group_vars/admitted/vault.yml`, the encrypted batch passwords.
- `inventories/` and `ssh/known_hosts`. Hosts, values and trusted host keys live in client inventory repositories.
- The ansible-vault guides `vault-guide.md`, `plain-vault-batch-passwords.md` and `vault-check.md`, replaced by `batch-secrets.md`.

## [0.1.6] - 2026-11-25

Releases up to 0.1.6 were published from the earlier repository, which no longer exists. This repository was recreated from the files as they stood at 0.1.6, with no history, and its first release will be 0.1.7.

### test release and publish

### Session uc-controller-inventory-split-plan-and-kickoff started


### Added uc-repo files

cut-release.py and publish-release.py and support files added
