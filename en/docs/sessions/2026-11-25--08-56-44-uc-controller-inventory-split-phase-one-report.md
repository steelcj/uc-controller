---
title: Inventory Split for uc-controller, Phase One Report
description: What the first phase of the inventory split changed, the checks it ran and their results, the variable comparison, what it decided beyond the plan, and what is left for later.
version: 0.1.3
status: provisional
date: 2026-11-26
language: en-CA
---

# Inventory Split for uc-controller, Phase One Report

## Summary

The phase is done, on the branch `inventory-split` in the worktree `../uc-controller-inventory-split`, in nine commits, unmerged and unpushed. uc-controller no longer holds hosts, client values, trusted host keys or secrets. Batch passwords are read from `~/.secrets/uc/fleet/batches/<batch>.yml` through one lookup, `uc_secret` (the fleet and build split was added after the phase, in version 0.1.1 of this report). The logic half of the inventories is `inventory-defaults/<stage>/`, and every client's hosts and values live in a client inventory repository made from `inventory-template/` with `scripts/new-inventory`. Every playbook refuses to run without a client inventory, given with `scripts/inventory-args`.

The step 6 comparison shows that, for the two stage combinations the plan names, every variable is as before except the four allowed kinds of difference. A third combination, which this phase added, shows that the stage environments now receive the onboard policy, which the old `onboard/stage` inventory lacked; see The step 6 comparison. The suite grew from 34 tests to 91, and all pass.

The plan is unchanged by the phase. Merging is yours.

## Where it started

| | |
| :-- | :-- |
| Main checkout | clean (`git status --porcelain` empty), not switched |
| Worktree | `../uc-controller-inventory-split`, made with `git worktree add ../uc-controller-inventory-split -b inventory-split main` |
| Started from | `4a40154d513d8b8d1a9924d80f267a69b154ba97`, `docs: inventory split plan 0.1.12` |
| Ansible | ansible-core 2.21.6, in `~/.venvs/ansible/current` |
| Suite before | 34 tests, all passing |

## Commits

| Step | Commit | Subject |
| :-- | :-- | :-- |
| 0 | none | The baseline, recorded outside the repository |
| 1 | `651465f` | feat: add the uc_secret lookup |
| 2 | `6d0d3c2` | feat: read batch passwords through uc_secret, not ansible-vault |
| 3 | `6e5014a` | feat: add inventory-defaults, the logic half of the inventories |
| 4 | `46377c5` | feat: add the client inventory template and its tools |
| 5 | `2821584` | feat: run every playbook against a client inventory |
| 6 | `5c3feef` | test: prove the inventory split leaves every variable as it was |
| 7 | `ddbe0f5` | docs: document client inventories and batch secrets |
| 7 | `9469f57` | test: use example addresses in the inventory split fixtures |
| 8 | this report's commit | docs: inventory split phase one report |

## Step 0: the baseline

A copy of `inventories/` in a temporary directory, with one static host in each raw source group (`example-incus-01` in `incus`, `disc-203-0-113-20` in `discovered`, `example-vt-0001` in `admitted` with `raw_node_batch: raw-1970-01-01-01`), one in each of `onboard/dev`, `onboard/stage`, `normalized/dev` and `normalized/stage`, the normalized ones also in `webservers`. The copy kept every value the group_vars held.

- `raw/incus.yml` was deleted and the incus host listed statically, so nothing asked the Incus server what exists.
- `raw/group_vars/admitted/vault.yml` was deleted, and `ansible-inventory` ran with `ANSIBLE_CONFIG` set to a copy of `ansible.cfg` without `vault_identity_list`. `ansible-config dump` confirmed no vault identity was configured. A check for vault values in the outputs matched only the variable's name inside the become expression; no decrypted variable was present, and `debug -a var=users` on the admitted host failed with "`vault_raw_batch_passwords` is undefined" until a throwaway become password was given, which proves nothing was decrypted.
- Recorded: `ansible-inventory --list --yaml` for raw with onboard/dev, onboard/dev with normalized/dev, and, added by this phase, onboard/stage with normalized/stage; and the resolved `users` for the admitted, onboarded, discovered and incus hosts.

Ad hoc `debug` on a host with a templated become password evaluates that password even with `ANSIBLE_BECOME=false`. Every resolution check in this phase therefore gives either a throwaway `-e ansible_become_password` or a made-up batch file under `UC_SECRETS_DIR`.

## Step 1: the uc_secret lookup

`shared/plugins/lookup/uc_secret.py`, registered by `lookup_plugins = ./shared/plugins/lookup` in `ansible.cfg`. Its first line names the OpenBao backend that will replace the file read. It is a plain reader with no backend switch.

- Reads `<root>/<path>.yml`, root `~/.secrets/uc/fleet` or `UC_SECRETS_DIR`, and returns the value under the required `key`.
- Refuses, with what to fix and never the value: an empty, absolute or `~` path; `..`, `.` or empty parts; a symlink leading outside the root; a missing root; a root or directory below it not mode 0700; a file not mode 0600; anything not owned by the user; a missing file or key; a value that is not a string, or is empty; a file that is not a mapping, or not valid YAML, for which only the line is given, since the parser's message can quote the file.
- Returns the value through `wrap_var`. In ansible-core 2.21 that is a plain `str`, since values not marked as trusted are never templated; a test through Ansible itself shows that `{{ 6 * 7 }}` in a value stays literal.

Checks: `tests/test_uc_secret.py`, 20 tests, all passing. The plugin is loaded through Ansible's plugin loader, so its documented options are registered.

## Step 2: replacing ansible-vault

- The admitted group's become password is `{{ lookup('uc_secret', 'batches/' ~ raw_node_batch, key='initial_password') }}`.
- `05_admit.yml` reads the batch through `uc_secret` in a `set_fact` that keeps only `admit_batch_short`, a boolean. It does not set `no_log`, so a missing or unsafe batch file fails with `uc_secret`'s own message, which holds no value; the result is a boolean, never the password. `admit_batch_id` still has no default, and the RN-ACC-08 warning is unchanged.
- `vault_identity_list` and its comment are gone from `ansible.cfg`, the encrypted-file branch from `promote_node.py`, and `vault.yml` from the repository.
- `test_admit_playbook.py` writes `raw-1970-01-01-01` and `raw-1970-01-01-02` batch files, with modes 0700 and 0600, under its own `UC_SECRETS_DIR`. The batch names in the tests are example names now, as the ground rules ask.
- The example batch name changed after the phase, from `raw-EXAMPLE-01` to `raw-1970-01-01-01`, the Unix epoch, a date no real batch can have, because `raw-EXAMPLE-01` did not follow the `raw-YYYY-MM-DD-NN` pattern real batches use. The test batch with a short password is `raw-1970-01-01-02`. This report uses the new names; the kickoff plan keeps the old one, as it records what was asked.

Guides, read before deciding:

| File | Decision | Reason |
| :-- | :-- | :-- |
| `en/docs/guides/vault-guide.md` | Removed | The ansible-vault batch passphrase guide |
| `en/docs/guides/plain-vault-batch-passwords.md` | Removed | The earlier draft of the same procedure |
| `en/docs/guides/vault-check.md` | Removed | Not about a vault product: five lines showing `head -1` of `secrets/raw-batches/raw-1970-01-01-03.vault`, an ansible-vault batch file |
| `en/docs/guides/ssh/plain-vault-batch-passwords.md` | Kept | Despite its name, its subject is where documents and an offline Diceware kit belong, and a console fingerprint check. It is misnamed, and names a private address and the controller's key file; the ROADMAP records it |

`en/docs/guides/batch-secrets.md` replaces them. Its creation recipe was run as written, with a throwaway `HOME` and a password containing a quote: the modes came out as 0700 and 0600, the password round-tripped, the hash verified against the password with `openssl passwd -6 -salt`, and `uc_secret` read the file. Links to the removed guides were updated in `admitting-a-raw-node.md` and `contracts.md`; the session records and `uc-controller-v0.1.7.md` were left as the records they are.

The step's grep checks, over everything but the session records and the versioned design documents v0.1.3 to v0.1.7: no file lookup on a secrets path, no `~/.config/uc-controller/vault`, no variable beginning with `vault_`, and no mention of the `batches` vault ID. Suite: 54 tests, all passing.

## Step 3: inventory-defaults

| Path | Holds |
| :-- | :-- |
| `inventory-defaults/raw/hosts.yml` | `raw` with `incus`, `discovered` and `admitted`, no hosts |
| `inventory-defaults/raw/group_vars/all.yml` | `needs_python_bootstrap: true` |
| `inventory-defaults/raw/group_vars/discovered.yml`, `incus.yml` | How each source is reached |
| `inventory-defaults/raw/group_vars/admitted.yml` | SSH as `initial`, the strict host key settings with `UserKnownHostsFile={{ uc_known_hosts_file }}`, and the `uc_secret` become password |
| `inventory-defaults/onboard/hosts.yml` | The `onboarded` group, no hosts |
| `inventory-defaults/onboard/group_vars/all.yml` | umask, openssh hardening, and `users`, with `authorized_keys: "{{ onboard_initial_authorized_keys }}"` and `sudo_options` exactly as before |
| `inventory-defaults/normalized/hosts.yml` | The `normalized` group, no hosts, and no group_vars, since the stage has no logic |

A check found none of the client values in it, and neither `uc_client_inventory` nor `uc_known_hosts_file` has a default there.

## Step 4: the template and its tools

`inventory-template/` holds `raw/` (the Incus plugin config, empty `admitted.yml` and `discovered.yml` with their headers, `group_vars/all.yml` with `uc_client_inventory: true`, `group_vars/raw.yml` with `uc_known_hosts_file`), `onboard/dev`, `onboard/stage`, `normalized/dev`, `normalized/stage` (each `hosts.yml`, `group_vars/all.yml` with placeholder values and `uc_client_inventory: true`, and `onboarded.yml` or `normalized.yml` with `uc_known_hosts_file`), `normalized/dev/group_vars/webservers.yml`, an empty `ssh/known_hosts`, `README.md`, `.yamllint` and `.githooks/pre-commit`. Placeholders that must be replaced say `CHANGE-ME`; example addresses use the documentation ranges.

`uc_known_hosts_file` is on each stage's own group, through `realpath`. A test checks that every host resolves it to the client's `ssh/known_hosts` with each stage alone and for raw with onboard/dev and onboard/dev with normalized/dev. Moving the value back into `all.yml`, the 0.1.4 layout, made exactly the combined raw with onboard/dev case fail, so the test catches that mistake.

- `scripts/inventory-args` prints absolute paths, defaults first, each defaults directory once, then the client's directories, and refuses an unknown or malformed stage, a missing directory, a stage given twice, and a path with whitespace.
- `scripts/new-inventory` copies the template, runs `git init`, sets `core.hooksPath`, makes no commit and no remote, and refuses a path that exists and is not empty.
- `scripts/check_inventory.py` has the forbidden variables as `FORBIDDEN_VARIABLES` under the comment the plan names. It refuses them under `group_vars/` and `host_vars/`, and allows them per host in the hosts files. It refuses a vault header, a crypt hash and a private key block in any file, a lookup (`lookup`, `query`, `q`, `uc_secret`) inside a template in a YAML file, and an admitted host without `raw_node_batch` or without an entry in `ssh/known_hosts`, hashed entries included.
- The hook runs `check_inventory.py .` through `UC_CONTROLLER`, then `yamllint`. A test commits through it: refused without `UC_CONTROLLER`, accepted on the template, refused when `ansible_user` is added to a group_vars file.

Checks: `tests/test_client_inventory.py`, 29 tests, all passing. Secret-shaped test values are made at run time: the vault file from a header assembled in code and random hex, the hash with `openssl passwd -6 -stdin`, the key with `ssh-keygen -t ed25519 -N ''`.

## Step 5: pointing the controller at client inventories

- `ansible.cfg` names no inventory.
- `shared/tasks/require-client-inventory.yml` is the only task of the first play of every playbook, on localhost with `gather_facts: false`, through `import_tasks`. It fails, naming `scripts/inventory-args`, unless `uc_client_inventory` is true. It then takes the `-i` sources outside `<uc-controller>/inventory-defaults/` (found from `ansible_config_file`), strips `/raw` or `/<stage>/<environment>`, fails unless they give one root, and sets `uc_client_root` and `uc_client_stages` on localhost.
- `05_admit.yml` and `00_discover.yml` write under `uc_client_root`. The candidate tasks find uc-controller's scripts through `admit_scripts`, since `admit_repo`, the raw directory two levels up, is no longer uc-controller.
- `promote_node.py`, `demote_node.py`, `match_raw_identity.py` and `reset_inventories.py` take `--inventory <client root>` and use `<root>/ssh/known_hosts` without Ansible. `inventory_hosts.py` takes the root and skips `.git/`.
- `inventories/` and `ssh/` are removed with `git rm`, nothing moved, and their `.gitignore` lines with them.
- Every test builds its client inventory with `scripts/new-inventory`. `test_admit_playbook.py` now also checks a run without a client inventory, which fails before any node is contacted; the first admission into a client inventory with no raw hosts; that the admitted file starts with the template's header; and that `check_inventory.py` passes after admission and after promotion.

Checks: the suite, 89 tests, all passing; `--syntax-check` of every playbook and `site.yml` with a client inventory, passing; and a run of `10_onboard.yml` against a scratch client whose only host is admitted, which passed the check play and skipped the node as before.

## Step 6: the comparison

The step 0 fixture was made into a client inventory with `scripts/new-inventory`, with the same hosts and values, and `ansible-inventory --list --yaml` was run through `scripts/inventory-args` for the same combinations. The outputs were compared as parsed data: group membership and every host's variables. Each difference was classified against the plan's list:

| Combination | Differences found | Verdict |
| :-- | :-- | :-- |
| raw with onboard/dev | `ansible_become_password` on the admitted host, vault expression to `uc_secret`; `UserKnownHostsFile` in its `ansible_ssh_common_args`, repository file to `{{ uc_known_hosts_file }}`; `users` authorized key, literal to `{{ onboard_initial_authorized_keys }}`, on all four hosts; `uc_client_inventory`, `uc_known_hosts_file` and `onboard_initial_authorized_keys`, new, on all four | All allowed |
| onboard/dev with normalized/dev | `users` authorized key, and the three new variables, on both hosts | All allowed |
| onboard/stage with normalized/stage, added by this phase | The three new variables, and the onboard policy: `umask`, `umask_system`, `umask_home_mode`, `umask_users`, the four `openssh_*` settings, and `users` | The policy is a difference the plan's list does not name; see below |

The resolved `users`, checked with the debug module, gives the same key as before for the admitted, onboarded, discovered and incus hosts.

**The stage environments now get the onboard policy.** The old `inventories/onboard/stage/group_vars/all.yml` set only its firewall rule, so onboarding a stage node would have created no `initial` user and then failed to switch to SSH as `initial`. Step 3 puts the policy in `inventory-defaults/onboard/`, for every environment, so stage now has it. That follows from the plan's decisions and closes a gap, so the phase keeps it, and the test records it as an expected difference for the stage combination only. If stage was meant to have no policy, say so, and a stage-specific default can be added.

`tests/test_inventory_split.py` makes the same client inventory from `tests/fixtures/inventory-split/client/` and compares the parsed output with `expected/` using `==`, for all three combinations, and checks the resolved key. The expected files were made from the step 0 baseline by applying only the allowed changes, not copied from the new output. The operator's public key and key path, and the monitoring source, are replaced by example values on both sides. Changing one default, `umask`, made the test fail.

Other checks:

| Check | Result |
| :-- | :-- |
| Suite | 91 tests, all passing |
| `ansible-playbook --syntax-check`, every playbook and `site.yml`, client inventory from the template | All pass |
| ansible-lint, same playbooks | 113 findings before, 113 after, none new |
| yamllint, default settings | 147 findings before, 174 after. The increase is `line-length` over 80 (lines up to 112 characters: Jinja expressions, the `import_tasks` path, and generated-file headers indented inside `copy` content, which must stay byte-identical to the template) and `document-start` warnings on the template's generated files, which must match what the code writes. The template's own `.yamllint`, which the hook uses, passes on the template and on promoted and admitted files |

The repository already failed both linters before the phase. `ingress/playbooks/artifacts/` holds earlier versions of `10_onboard.yml` that are not run, and was not checked.

## Step 7: documentation

- `en/docs/admitting-a-raw-node.md`: the `inventory-args` invocation, batch files, committing `raw/admitted.yml` and `ssh/known_hosts` in the client repository, and a changelog row. Its examples now use the example batch, address and fingerprint.
- New `en/docs/guides/client-inventories.md`, with what the hook means for a client who takes their repository over.
- `en/docs/uc-controller-v0.1.8.md`, copied from v0.1.7, which is byte-for-byte untouched: a v0.1.7 to v0.1.8 changelog table, and the layout, a new Inventories section, the raw stage, variable precedence, firewall placement, usage, admission, secrets and `ansible.cfg` sections. The embedded playbook and script listings are regenerated from the files; those of `10_onboard.yml` and `promote_node.py` had already fallen behind in v0.1.7. Older changelog entries and the Verification Status are left as history.
- ROADMAP: see What is left.
- `README.md`, the uc-repo template, filled in. Its Layout table keeps every row and gains `ingress/`, `converge/`, `shared/`, `roles/`, `inventory-defaults/`, `inventory-template/` and `tests/`. The `scripts/` row's text now says the directory holds more than the release scripts.
- `en/docs/sessions/README.md`, version 0.1.4: `<repo-name>` filled in the prose and the examples, kept in the pattern and field definitions.
- `CHANGELOG.md`: entries under `## [Unreleased]` with each step. No released section, `VERSION` or release script was touched.

## Decided beyond the plan

| Decision | Why |
| :-- | :-- |
| The shared task also sets `uc_client_stages`, and `10_onboard.yml` and `20_normalize.yml` take their environments from it, so `-e onboard_inventory` and `-e normalized_inventory` are gone | The plan asks for those paths "under uc_client_root"; deriving the environment from `-i` keeps the two from disagreeing. Both playbooks refuse a run with not exactly one environment of the stage they write |
| `check_inventory.py` also refuses a forbidden variable set on a group inside a hosts file (`vars:`) | That is group-level logic too; per-host settings stay allowed |
| The template has a `.yamllint` that disables `document-start` and accepts unindented sequences | `to_nice_yaml` and `yaml.safe_dump` write neither, so the hook's `yamllint` would otherwise refuse the first commit after an admission. A test lints a promoted inventory with it |
| `promote_node.py` sets `UC_CONTROLLER` for its own commits when it is not set | Otherwise the client repository's hook fails every commit the script makes |
| A third comparison, for the stage environments | It found the policy difference above |
| The promote-then-check test is in step 5's commit | `promote_node.py` gained its client inventory interface there |
| Example values in the step 6 fixtures | The operator's public key, key path and monitoring range would otherwise return to uc-controller's history in a test |

## Things to know

- **Broken link.** `README.md` and `CONTRIBUTORS.md` link to `en/docs/guides/releases/cut-and-publish-a-release.md`, which is not in the repository. Not written, as asked; it is yours to settle.
- **Vendored test keys.** `roles/robertdebock.users/molecule/default/ssh_keys/` holds private key files from the vendored role, from before this phase. The later rewrite's checks do not look for private keys, and GitHub's secret scanning may refuse the push to the recreated repository because of them.
- **The hook checks the working tree**, not what is staged.
- **Playbooks run from the uc-controller checkout.** Scripts are found as `uc_scripts_dir | default('scripts')`, against the current directory, as before.
- **Onboarding admitted nodes, later.** `10_onboard.yml` adds onboarded nodes to the in-memory `onboarded` group. For an admitted node, which keeps `inventory_dir` at `raw/`, both `raw` and `onboarded` would then set `uc_known_hosts_file`, at the same group depth; Ansible orders such groups by name, so `raw`'s value wins, which is the right one. The onboarding of contract nodes should not rely on that by accident: test it there.
- **Real values kept on purpose.** The ROADMAP names the real batches it says to change, `uc-controller-v0.1.8.md` keeps v0.1.7's historical Verification Status with its node and address, and `00_discover.yml` keeps its default subnet.
- **The baseline files** are in the session's scratchpad, which is temporary: `/tmp/claude-1000/-home-initial-areas-development-uc-controller/82b304d6-3dfd-452d-bbaa-7c14fb3bbd7a/scratchpad/baseline`. The test fixtures carry what matters of them.

## What is left

In the ROADMAP:

- Change the test values of the two test batches made before the batch files, and of `vaults/*_secrets.yml`, which were public.
- Recreate the repository once this phase works, as the plan's "Later: recreating the repository" section describes. Its list of guides to remove from history is the three removed in step 2, plus `en/docs/guides/using-vault-for-batched-passwords.md`.
- The OpenBao backend for `uc_secret`.
- `NOPASSWD: ALL` during onboarding, against the privileged access policy.
- Admission on a branch, merged to admit, once a second person admits nodes.
- Checking `confirmation.yml` and candidates on commit, in the handoff phase.
- Bringing nine older walkthroughs under `en/docs/` up to client inventories, and the misnamed `guides/ssh/plain-vault-batch-passwords.md`.

For you, in this order:

1. Review the branch: `git -C ../uc-controller-inventory-split log --stat 4a40154..inventory-split`.
2. Before merging, make your client inventory, `scripts/new-inventory ~/uc-inventories/<client>`, and copy into it the hosts, values and `ssh/known_hosts` from your main checkout's `inventories/` and `ssh/`. Merging deletes the tracked ones, `ssh/known_hosts` and every group_vars file among them, from the main checkout; only the gitignored generated files, such as `inventories/raw/admitted.yml`, stay on disk. They remain in git history until the repository is recreated.
3. Create the batch files, `~/.secrets/uc/fleet/batches/<batch>.yml`, with `initial_password` only, as `en/docs/guides/batch-secrets.md` describes. Your vault passphrase file is no longer read.
4. Merge `inventory-split` into `main` when you are satisfied.

## Changelog

| Version | Date | Change |
| :-- | :-- | :-- |
| 0.1.3 | 2026-11-26 | Real host, address, subnet, batch, MAC and machine id values replaced by example values before the repository is recreated, and the item on the test batches reworded so it no longer names them |
| 0.1.2 | 2026-11-26 | The example batch name is `raw-1970-01-01-01`, and why, under the test changes |
| 0.1.1 | 2026-11-26 | Added after the phase, on the same branch: the firewall values renamed and shaped for `steelcj.foomuuri`, with `shared/vars/uc_firewall_interim.yml` feeding `uc_firewall` until the switch; and the batch file split, so `uc_secret`'s root is `~/.secrets/uc/fleet` and a batch file holds `initial_password` only, with uc-node's hashes later in `~/.secrets/uc/build/`. The paths here follow; `2026-11-26--13-18-39-uc-controller-inventory-split-session.md` records that work |
| 0.1.0 | 2026-11-25 | First version |
