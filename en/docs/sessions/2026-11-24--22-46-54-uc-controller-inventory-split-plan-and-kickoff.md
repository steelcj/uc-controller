---
title: Inventory Split for uc-controller, Plan and Kickoff Prompt
description: The plan for taking secrets and client inventories out of uc-controller, behind one secret lookup that OpenBao can later replace, and the Claude Code kickoff prompt that carries it out.
version: 0.1.14
status: provisional
date: 2026-11-26
language: en-CA
---

# Inventory Split for uc-controller, Plan and Kickoff Prompt

## Why

uc-controller is a public repository, and it holds two kinds of things that do not belong there:

- Secrets. `inventories/raw/group_vars/admitted/vault.yml` holds the batch passphrases, encrypted with ansible-vault. Ciphertext in a public repository can be attacked offline, for as long as the history exists. The history holds more: `secrets/raw-batches/raw-1970-01-01-03.vault`, also encrypted, and `vaults/raw_secrets.yml`, `vaults/onboard_secrets.yml` and `vaults/normalized_secrets.yml`. All of them held test values only, which are changed regardless.
- Client data. Once real nodes are admitted, `ssh/known_hosts` and the inventories name client domains and addresses. The uc-node README already forbids committing either.

Secrets move to `~/.secrets/`, read through one lookup that OpenBao can later replace. Client inventories move to one private repository per client. uc-controller keeps only code, defaults and a template. Once this phase works, the repository is recreated with the old history rewritten, as the last section describes.

This is the first of three phases. The second makes uc-node read the same batch files and moves its `inventory/group_vars/all/` to playbook-level `group_vars/`. The third builds the handoff: uc-node writes `confirmation.yml` and a candidates entry into the client's inventory repository, and uc-controller admits from there.

## Where the repository stands

At commit `980f37e` on `main`. The commits after it only add this plan, and the worktree records the head it starts from. Since `0b5359b`, three commits had landed:

- `040f7e6` reorganized the documents, moving them from `onboarding/` to `design/` and `guides/`. Its message is pasted `git status` output, which the later rewrite replaces.
- `cfb7b2e` added the files from uc-repo: `VERSION`, `CHANGELOG.md`, `CONTRIBUTORS.md`, a `README.md` that is still the unfilled template, `scripts/cut-release.py` and `scripts/publish-release.py`.
- `980f37e` released version 0.1.6.

The table describes the code, which these commits did not change.

The repository's own version is 0.1.6, in `VERSION`. It is separate from this plan's version and from the design document's, `uc-controller-v0.1.7.md`. The release `v0.1.6` is on GitHub, with `uc-controller-0.1.6.tar.gz` and `SHA256SUMS` attached. Its tarball is built with `git archive`, so it contains `inventories/raw/group_vars/admitted/vault.yml` and `ssh/known_hosts`. `README.md` and `CONTRIBUTORS.md` link to `en/docs/guides/releases/cut-and-publish-a-release.md`, which is not in the repository.

Besides `main`, origin has 10 branches and 3 tags, `v0.1.3-layout`, `v0.1.5-freeze` and `v0.1.6`. Every branch is already merged into `main`, and every one still carries `vault.yml`, `secrets/` or `vaults/` in its history.

| Area | State |
| :-- | :-- |
| `ansible.cfg` | `inventory = ./inventories/raw`, and `vault_identity_list = batches@~/.config/uc-controller/vault/batches`, so every run needs the vault passphrase file |
| `inventories/raw/hosts.yml` | Group structure only: `raw` with children `incus`, `discovered` and `admitted` |
| `inventories/raw/group_vars/` | Connection logic per source (`all.yml`, `discovered.yml`, `incus.yml`, `admitted/main.yml`) and the encrypted `admitted/vault.yml` |
| `inventories/raw/group_vars/admitted/main.yml` | `UserKnownHostsFile={{ ansible_config_file \| dirname }}/ssh/known_hosts`, and `ansible_become_password: "{{ vault_raw_batch_passwords[raw_node_batch] }}"` |
| `inventories/raw/incus.yml` | The `community.general.incus` plugin configuration |
| `inventories/onboard/dev/group_vars/all.yml` | Policy (umask, openssh hardening, the `users` structure with `NOPASSWD: ALL`) mixed with values (`onboard_ssh_private_key_file`, locale, time zone, firewall rules, the initial user's public key) |
| `inventories/onboard/stage/`, `inventories/normalized/*/` | Firewall rules, which are per-client values |
| `ssh/known_hosts` | Committed, so git history records when keys were trusted |
| `ingress/playbooks/05_admit.yml` | Reads `vault.yml` directly, checks the batch is in it and its length, and derives `admit_known_hosts` from the repository |
| `scripts/` | `inventory_hosts.py`, `match_raw_identity.py`, `promote_node.py`, `demote_node.py` and `reset_inventories.py` default to `inventories/...` and `ssh/known_hosts`; `promote_node.py` passes over encrypted files |
| `tests/` | `test_admit_playbook.py` builds an encrypted `vault.yml` with a passphrase of its own |
| History only | `secrets/raw-batches/` (`index.yml` and the encrypted `raw-1970-01-01-03.vault`), `vaults/*_secrets.yml`, `scripts/vault-client.py`, `scripts/new_raw_batch.py`, `tests/test_new_raw_batch.py`, and the vault guides `using-vault-for-batched-passwords.md` and `plain-vault-batch-passwords.md` |

## Decisions

### One lookup for every secret

A lookup plugin, `uc_secret`, is the only way any playbook, group variable or script reads a secret. Its file backend reads `~/.secrets/uc/<path>.yml`. Replacing it with OpenBao later changes the plugin, not the playbooks. A lookup is evaluated only when the variable is used, so a run that never becomes root never reads the file.

### Batch files

One file per batch, `~/.secrets/uc/batches/<batch>.yml`, mode `0600` in directories of mode `0700`, holding `initial_password` for uc-controller and `initial_password_hash` for uc-node. The batch name itself is not secret, and is what inventories and node definitions carry. The path maps directly onto an OpenBao KV path, `uc/batches/<batch>`.

### Code and data meet through several inventory sources

Ansible merges inventory sources in the order they are given, and group variables from a later source override those from an earlier one. uc-controller keeps a defaults inventory, `inventory-defaults/<stage>/`, with the group structure and every piece of logic. The client repository supplies hosts and values. The order is all the defaults directories first, then all the client directories, so a client value always overrides a default, whichever stages a run combines. Playbook-level `group_vars/` would have been simpler, but they take precedence over inventory variables, which would block client overrides. `scripts/inventory-args` prints the `-i` options, so invocations stay short.

A run that combines stages, such as admission with `raw` and `onboard/dev`, merges their `all` groups, and the last source wins for every host. Raw hosts already receive the onboard policy this way, which `10_onboard.yml` relies on. Two rules follow:

- A value set in `group_vars/all.yml` means the same thing at every stage, such as `uc_client_inventory: true`.
- A value that differs by stage is set on the stage's own group: `raw`, `onboarded` or `normalized`. `uc_known_hosts_file` is one, since it is built from `inventory_dir`, which is one level deep for `raw` and two for the others.

A single flat `inventory-defaults/` was considered and set aside. Per-stage defaults keep each stage complete when it runs on its own, and a stage's own group is where anything stage-specific goes in either layout. The cost is one directory and one mapping entry for each new stage, which is small while the stages are few and stable.

### The template lives in uc-controller

`inventory-template/` holds the client layout with placeholder values, and `scripts/new-inventory` makes a new client repository from it. The template is versioned with the code that reads it, so the two cannot drift. A client repository starts with its own history, not with uc-controller's.

### Rewriting history, later

This phase does not rewrite history. The vault files held test values only, which are changed regardless. Christopher recreates the repository once the phase works, so that its public history holds no secrets or client data, even test ones. As of version 0.1.13, no history is carried over at all: the new repository starts from the cleaned files of the tree, as the last section of the plan describes. The rest of this section records the rewrite first planned, which that replaces.

The repository is recreated rather than force-pushed. After a force push, GitHub still serves old commits by their IDs and through `refs/pull/*`, so only recreating it removes the old history completely. The old repository is deleted, not archived or renamed. Its release assets are downloads of their own, and a rewrite does not reach them, so only deleting it removes the `v0.1.6` tarball that holds `vault.yml`. The new repository holds the rewritten `main` and all three tags, rewritten. The merged branches are not carried over, since their work is already in `main`.

`CONTRIBUTORS.md` says tags and releases are never reused. Recreating the repository is the one exception, and `CONTRIBUTORS.md` says so. The rewritten tags keep their names but point at rewritten commits. `v0.1.6` is published again from the new repository with `scripts/publish-release.py`, and since its tarball comes from `git archive`, it is clean once the history is. Every path that held secrets or client data is removed from every commit: `inventories/`, `ssh/`, `secrets/`, `vaults/`, the vault scripts and their test, and the vault guides that this phase replaces. That is the same approach taken for uc-node on 2026-11-23. The rewrite is prepared and checked locally. Recreating the repository is done by hand.

Rewriting does not reach clones or forks that already exist, and that includes Christopher's own. His main checkout and any worktree still hold the old history afterwards, and one stray push would publish it again, so they are replaced by a fresh clone of the new repository.

The history checks look for real secrets, not for words. Many documents, this plan among them, mention `$ANSIBLE_VAULT` or a key file's name. So the checks match the shape of a secret instead:

- the 80-hexadecimal-character lines of ansible-vault ciphertext
- a vault header at the start of a line
- a full crypt hash

The key file name `example-org-raw-initial` is not a secret and is not checked.

### Deferred

- Admission as a reviewed event, on a branch that is merged to admit, matters once a second person admits nodes. It goes in the ROADMAP.
- Checking `confirmation.yml` and candidate files on commit belongs to the handoff phase, which introduces them. This phase adds the hook and the checks the split itself needs.
- `NOPASSWD: ALL` for `initial` during onboarding conflicts with the privileged access policy. This phase moves it to the defaults unchanged and records the conflict in the ROADMAP.

## Prompt

```text
Read en/docs/sessions/2026-11-24--22-46-54-uc-controller-inventory-split-plan-and-kickoff.md first: it holds the reasons and decisions behind this prompt.

Run every command with the Ansible virtual environment active (. ~/.venvs/ansible/current/bin/activate).

Never switch branches in the main checkout. Check that it is clean with git status --porcelain, and stop and tell me if it is not. Then make a worktree for this phase from the head of main, and record that commit ID for the report:
   git worktree add ../uc-controller-inventory-split -b inventory-split main
Work only in the worktree, in this order, and commit after each step.

Ground rules for the whole phase:
- Never read anything under ~/.secrets/ or ~/.config/uc-controller/, never decrypt a vault file, never open a file under secrets/ or vaults/ in any commit, and never print a secret. Tests make their own secrets in temporary directories.
- Never run a playbook against the repository's own inventories or a real node. No admissions during this phase.
- Nothing is pushed, force-pushed or tagged, and history is not rewritten. Recreating the repository comes later, as the plan's last section describes.
- Examples use example.org, 203.0.113.0/24, 198.51.100.0/24 and the batch name raw-EXAMPLE-01, never a real name, address or batch.
- No em dashes in documents, no heading numbers, no horizontal rules, no hard-wrapped prose.
- No committed file contains a literal crypt hash, a vault header line, vault ciphertext or a private key, not even as a test fixture or an example. The later rewrite would remove such a file from history, and GitHub's secret scanning may refuse a push that holds a private key. Tests make these at run time in their temporary directory: a hash with openssl passwd -6, a key with ssh-keygen -t ed25519 -N '', and a vault file by writing a header line and lines of hex into a temporary file. Guides show the command, never its output.
- Each step that changes something the repository's users would notice adds its entry under ## [Unreleased] in CHANGELOG.md, in the same commit, as CONTRIBUTORS.md asks. Never edit a released section, never change VERSION, and never run cut-release.py or publish-release.py.

0. Record the baseline. In a temporary directory outside the repository, make a fixture inventory from a copy of inventories/, with one static host in each raw source group (incus, discovered, admitted, the admitted one with raw_node_batch: raw-EXAMPLE-01), one in onboard/dev and one in normalized/dev. Delete raw/incus.yml from the copy and list the incus host statically instead, so that no fixture ever asks the Incus server what exists: the step 0 and step 6 outputs must come from files, not from two different moments. The same rule holds for every test fixture made from the template. Delete raw/group_vars/admitted/vault.yml from the copy too, and run ansible-inventory with ANSIBLE_CONFIG set to a copy of ansible.cfg, in that temporary directory, without the vault_identity_list line. The repository's ansible.cfg names a vault password file that exists, so with it, ansible-inventory would decrypt vault.yml as it loads and write the batch passwords into the baseline, breaking the ground rules on decrypting and printing secrets. Without the vault identity, a vault file left in the copy stops the run with "no vault secrets found" instead. Setting ANSIBLE_VAULT_IDENTITY_LIST to an empty value does not do this, since Ansible reads the empty value as the current directory. The copy keeps every value the current group_vars hold, in particular, from inventories/onboard/dev/group_vars/all.yml, onboard_ssh_private_key_file, locale_lang, locale_timezone, ntp_timezone, firewall_rules_onboard and the initial user's public key, and the firewall rules of onboard/stage and normalized/*. Step 6 needs every one of them in the client inventory it builds. Save the output of ansible-inventory --list --yaml for two combined runs, raw with onboard/dev, and onboard/dev with normalized/dev, to that directory. These are the before picture for step 6. This step produces no commits.

1. Add the secret lookup. Write shared/plugins/lookup/uc_secret.py and set lookup_plugins in ansible.cfg. Interface: lookup('uc_secret', 'batches/' ~ raw_node_batch, key='initial_password'). The file backend reads <root>/<path>.yml, where root is ~/.secrets/uc, or UC_SECRETS_DIR when set (for tests). It refuses, with a message saying what to fix and never the value:
   - a path that is absolute, contains .., or leaves the root
   - a root or directory on the way that is not mode 0700, or a file that is not 0600, or one not owned by the user
   - a missing file or key
   The plugin is a file reader, not a dispatcher: no backend variable and no branch. A one-line comment at the top of the file says that an OpenBao backend, at uc/batches/<batch>, will replace the file read here. Return every value as unsafe text, so a password containing {{ is never templated. Any task that prints a value read through uc_secret sets no_log: true. Add tests/test_uc_secret.py covering each refusal and a good read, and add it to tests/run_tests.py.

2. Replace ansible-vault. 
   - The admitted group's become password reads lookup('uc_secret', 'batches/' ~ raw_node_batch, key='initial_password').
   - In 05_admit.yml, replace the vault file checks with a uc_secret read of the batch, and keep the rule that admit_batch_id has no default. Keep the warning for a password under 15 characters: RN-ACC-08 is a clause of the raw node contract, measured on the controller because the node cannot measure it, so the identifier and the warning both stay.
   - Remove vault_identity_list from ansible.cfg, the encrypted-file handling from promote_node.py, and every other mention of the batches vault ID.
   - Change test_admit_playbook.py to write a batch file under UC_SECRETS_DIR, with the right modes, instead of an encrypted vault.yml.
   - git rm inventories/raw/group_vars/admitted/vault.yml.
   - List every guide under en/docs/ whose subject is ansible-vault batch passwords. They include vault-guide.md and plain-vault-batch-passwords.md. Read vault-check.md and any other candidate before deciding, since a guide about checking a vault product is not one of them. Remove those guides, and in the report name each file removed and each candidate kept, with the reason. The later rewrite removes the same files from history.
   - Replace them with en/docs/guides/batch-secrets.md: the layout and modes of ~/.secrets/uc/batches/<batch>.yml, how to create one without the password reaching shell history or the process list (read it from the terminal, hash it with openssl passwd -6 for initial_password_hash), how to retire a batch, and that the same file will serve uc-node and, later, OpenBao at uc/batches/<batch>. Update every link to the removed guides.
   - grep must find no lookup('file' or lookup('ansible.builtin.file' whose path contains ~/.secrets or ~/.config/uc-controller, no other mention of ~/.config/uc-controller/vault, and no variable name beginning with vault_.
   Run tests/run_tests.py.

3. Split code from data. Create inventory-defaults/ with one directory per stage, raw/, onboard/ and normalized/, holding group structure and logic only:
   - raw/: hosts.yml with the raw group and its children, and no hosts; group_vars/all.yml (needs_python_bootstrap), discovered.yml, incus.yml and admitted.yml (connection settings, host key settings, the become lookup from step 2).
   - onboard/: the policy half of inventories/onboard/dev/group_vars/all.yml: the umask settings, the openssh hardening, and the users structure, with its authorized key taken from a variable, onboard_initial_authorized_keys, that the client inventory sets. Keep sudo_options exactly as it is now.
   - normalized/: group structure only, unless something there is logic.
   Every value that describes a client, an operator or an environment stays out of inventory-defaults/: onboard_ssh_private_key_file, locale and time zone values, firewall_rules_onboard, firewall_rules_normalize, firewall_rules_specialize, the public key, and the Incus plugin configuration. Each file keeps a comment saying what it holds, as now.
   uc_client_inventory and uc_known_hosts_file are set only by the client inventory, never in inventory-defaults/. A default for either would let a run without a client inventory pass the check in step 5.

4. Add the client inventory template and its tools.
   - inventory-template/ holds the client layout: raw/ (incus.yml plugin config, an empty admitted.yml and discovered.yml with their header comments, group_vars/all.yml with no logic), onboard/dev/, onboard/stage/, normalized/dev/, normalized/stage/ (hosts.yml and group_vars/all.yml with the values from step 3, as placeholders), ssh/known_hosts (empty), a README saying the repository holds facts only, never secrets or logic, and .githooks/pre-commit.
   - In a client repository, admitted.yml, discovered.yml and ssh/known_hosts are committed. Nothing in the template is gitignored for being generated.
   - The known hosts file is the client repository's ssh/known_hosts at every stage. Playbooks and the defaults refer to it only as uc_known_hosts_file, so that promote_node.py and demote_node.py keep the host key settings identical across stages, as they do now. It is built from inventory_dir, which is one level deep for raw and two for the others, so it is set on each stage's own group and never in group_vars/all.yml: in a run that combines stages, all.yml from the last source wins for every host, and a raw host would get the two-level expression and a path outside the client repository. So the template sets it in raw/group_vars/raw.yml as {{ (inventory_dir ~ '/../ssh/known_hosts') | ansible.builtin.realpath }}, and in onboard/*/group_vars/onboarded.yml and normalized/*/group_vars/normalized.yml with '/../../ssh/known_hosts'. realpath gives every stage the same clean path. Never an absolute path. A test checks that every host resolves it to the same file, both with each stage on its own and in the combined runs the playbooks use: raw with onboard/dev, and onboard/dev with normalized/dev. It makes its own client inventory with scripts/new-inventory, with one host in each of raw, onboard/dev, onboard/stage, normalized/dev and normalized/stage, since it tests path resolution, not the full inventory. ansible-inventory does not template variables, so the test resolves the value with ansible <host> -m ansible.builtin.debug -a var=uc_known_hosts_file. The debug action runs on the controller and does not connect to the host, so fixture addresses that reach nothing are fine.
   - uc_client_inventory: true goes in every stage's group_vars/all.yml. It is the same at every stage, so it does not matter which source wins, and the implicit localhost reads it too.
   - The template's README states the rule: a value in group_vars/all.yml must mean the same at every stage, and a value that differs by stage goes on the stage's own group.
   - The scripts do not resolve uc_known_hosts_file. They take the client inventory's root as an argument and use <root>/ssh/known_hosts, without calling Ansible to find it.
   - scripts/inventory-args <client inventory> <stage> [<stage> ...] prints the -i options: all the defaults directories first, then all the client directories, each in the order the stages are given, so that a client value always overrides a default. For example, raw onboard/dev gives -i inventory-defaults/raw -i inventory-defaults/onboard -i <client>/raw -i <client>/onboard/dev. Usage: ansible-playbook $(scripts/inventory-args ~/uc-inventories/example.org raw onboard/dev) ingress/playbooks/05_admit.yml ...
   - scripts/new-inventory <path> copies the template, runs git init, sets core.hooksPath to .githooks, and refuses a path that exists and is not empty. It creates no remote.
   - scripts/check_inventory.py <client inventory> fails when a client inventory holds logic or secrets. The forbidden variables are the code and data boundary, so they are a named constant at the top of the file, under the comment "# Variables that indicate logic leaked into a client inventory.": ansible_connection, ansible_user, ansible_ssh_common_args, ansible_ssh_host_key_checking and ansible_become_password. The script fails when one of them is set anywhere under a group_vars/ or host_vars/ directory. They are allowed per host in the hosts files the scripts write: raw/admitted.yml and raw/discovered.yml, written by admission and discovery, and onboard/*/hosts.yml and normalized/*/hosts.yml, where promote_node.py writes its connection contract for each host it promotes. The script also fails, in any file, on an $ANSIBLE_VAULT header, a crypt hash ($6$, $y$, $2b$), a private key block, or a uc_secret or other lookup. It also fails when an admitted host has no raw_node_batch, or has no entry in ssh/known_hosts. A test promotes a host with promote_node.py and checks that the result passes. The template's pre-commit hook runs it as "${UC_CONTROLLER:?set UC_CONTROLLER to the uc-controller checkout}/scripts/check_inventory.py" ., then yamllint.
   - Tests for inventory-args, new-inventory and check_inventory.py, added to run_tests.py.

5. Point the controller at client inventories.
   - Remove inventory = from ansible.cfg. Write the check once, in shared/tasks/require-client-inventory.yml: it fails, with a message naming scripts/inventory-args, when uc_client_inventory is not true. Every playbook starts with a play on localhost, with gather_facts: false, whose only task includes the file. A play on a group runs nothing when no client inventory was given, so the check cannot live there. The implicit localhost reads the all group's variables, so it sees uc_client_inventory.
   - The same task finds the client inventory's root, for plays that run on localhost. Localhost has no inventory_dir and is in no stage group, and at a first admission no raw host exists whose variables it could borrow. What it does have is ansible_inventory_sources, the absolute -i paths. The task takes the sources outside uc-controller's inventory-defaults/ directory and strips the stage from each: /raw from raw, and /<stage>/<environment> from onboard/dev and the others. It fails unless they all give one and the same root, and then sets uc_client_root on localhost. Plays read it as hostvars['localhost'].uc_client_root.
   - Replace the raw_inventory, onboard_inventory and normalized_inventory defaults that point into the repository with paths under uc_client_root. The localhost plays in 05_admit.yml, which today use raw_inventory | default('inventories/raw') and admit_raw_dir | dirname | dirname, take the raw directory and the known hosts file from uc_client_root too. No default inside the repository remains. A test runs these localhost plays with a client inventory that has no raw hosts yet.
   - Give inventory_hosts.py, match_raw_identity.py, promote_node.py, demote_node.py and reset_inventories.py a required argument naming the client inventory's root, and make them use <root>/ssh/known_hosts, as step 4 says.
   - git rm -r inventories/ and ssh/. Move nothing with git mv: the client repositories start fresh. Remove the .gitignore lines for inventories/raw/discovered.yml, cloud.yml and admitted.yml, and their comment, since nothing under inventories/ remains.
   - Update the tests to build a client inventory with scripts/new-inventory in a temporary directory.

6. Prove the variables are the same. Make the baseline fixture from step 0 into a client inventory made with scripts/new-inventory, with the same hosts and values. Run ansible-inventory --list --yaml with scripts/inventory-args for the same stage combinations, and compare with the step 0 output as parsed data, never as text, since Ansible may order keys differently between releases. The only differences allowed are:
   - ansible_become_password: the vault expression replaced by the uc_secret lookup
   - UserKnownHostsFile: the repository's ssh/known_hosts replaced by the client inventory's
   - the users authorized key: the literal replaced by onboard_initial_authorized_keys. ansible-inventory shows the expression, not its value, so check the value separately with ansible <host> -m ansible.builtin.debug -a var=users, which must give the same key as before
   - uc_client_inventory, uc_known_hosts_file and onboard_initial_authorized_keys, which are new
   Any other difference is a bug, fixed before going on. Turn the comparison into tests/test_inventory_split.py, with the expected variables as a YAML fixture loaded and compared with ==, and add it to run_tests.py. Run the whole suite, yamllint, ansible-lint, and ansible-playbook --syntax-check on every playbook with a client inventory from the template.

7. Documentation.
   - en/docs/admitting-a-raw-node.md: the new invocation, batch files instead of the vault, and committing ssh/known_hosts in the client repository. Add a changelog row.
   - New en/docs/guides/client-inventories.md: what a client repository holds and never holds, making one with scripts/new-inventory, keeping it private, the -i order and why defaults come first, the pre-commit hook and UC_CONTROLLER, and giving a leaving client their repository and their batch files. Say that the hook refuses every commit until UC_CONTROLLER points at a uc-controller checkout, so a client who takes their repository over either installs uc-controller, removes .githooks/pre-commit, or commits with --no-verify.
   - Copy en/docs/uc-controller-v0.1.7.md to en/docs/uc-controller-v0.1.8.md, leaving v0.1.7 untouched, and update the sections on inventories, secrets and admission, with a changelog row.
   - ROADMAP: change the test values of the two test batches made before the batch files and of vaults/*_secrets.yml, which were for testing only; recreate the repository once this phase works, as the plan's "Later: recreating the repository" section describes; NOPASSWD: ALL during onboarding against the privileged access policy; admission on a branch, merged to admit, once a second person admits nodes; the OpenBao backend for uc_secret; checking confirmation.yml and candidates on commit, in the handoff phase.
   - README.md is the unfilled uc-repo template. Fill it in: what uc-controller is, its stages, that inventories and secrets live outside it, and links to the guides. Keep its Layout table and its existing rows, and add rows for ingress/, converge/, shared/, roles/, inventory-defaults/, inventory-template/ and tests/. Fill in the <repo-name> placeholders in en/docs/sessions/README.md too.
   - en/docs/guides/releases/cut-and-publish-a-release.md, which README.md and CONTRIBUTORS.md link to, is not in the repository. Do not write it. Name it in the report as a broken link for me to settle.

8. Write the phase report, named by en/docs/sessions/README.md, with the same front matter as this file, version 0.1.0, status provisional:
   touch "en/docs/sessions/$(date +%Y-%m-%d--%H-%M-%S)-uc-controller-inventory-split-phase-one-report.md"
   Cover the commit the worktree started from, each step, its commits and checks, the guides removed and kept in step 2, the step 6 comparison, and everything left in the ROADMAP. Commit it in the worktree, with this plan if the phase changed it; the worktree already starts with the plan, since main holds it. Merging the branch into main is mine to do.
```

## Later: recreating the repository

Christopher recreates the GitHub repository once this phase is merged and working. No history survives: the new repository starts from the files in the tree at that moment, with one new first commit, so no filter-repo step is needed. What matters is that tree, so its files are cleaned on `inventory-split` before the merge: no real host, address, MAC, machine id or batch, as the phase's session records list.

1. Merge `inventory-split` into `main`.
2. Remove the worktree: `git worktree remove ../uc-controller-inventory-split`.
3. Delete the repository on GitHub, and create an empty one with the same name. Delete it, not archive or rename it, so that its release assets go too.
4. In the main checkout, delete `.git`.
5. Before anything is added, remove what must not be published and is not ignored: `inventories/`, left on disk with an untracked `admitted.yml` that holds the real node, and anything else `git status` will show after `git init`.
6. `git init`, add the files, and check what is staged before committing: `git status`, and `git grep --cached` for the real values the cleanup removed. Then commit, add the new repository as `origin`, and push `main`.
7. Tag and publish a fresh release with `scripts/cut-release.py` and `scripts/publish-release.py`, if one is wanted.
8. Replace every other clone with a fresh clone of the new repository. An old clone still holds the old history, and one push from it would publish that history again.

The old tags and releases, `v0.1.6` among them, go with the old repository. The new one starts with none until a fresh release is tagged. `CONTRIBUTORS.md` records recreating the repository as the one exception to never reusing tags and releases.

## Changelog

| Version | Date | Change |
| :-- | :-- | :-- |
| 0.1.14 | 2026-11-26 | The client's name replaced in key file names by `example-org`, and the prompt's ROADMAP item describes the two test batches instead of naming example ones |
| 0.1.13 | 2026-11-26 | Recreating the repository carries no history: merge, remove the worktree, delete the GitHub repository and create it empty, delete `.git`, `git init`, commit, push, tag a fresh release if wanted, and replace other clones, with no filter-repo step. The old tags and releases go with the old repository, and `CONTRIBUTORS.md` records the exception. The real host, address, subnet, batches, MACs and machine id in the plan's text replaced by example values, since the new repository starts from these files |
| 0.1.12 | 2026-11-25 | Step 0 removes vault.yml from its copy and runs with an ansible.cfg that has no vault identity, since ansible-inventory would otherwise decrypt vault.yml into the baseline; step 0's two runs named as combined; onboard_initial_authorized_keys added to step 6's new variables; step 8 no longer commits the plan, which main already holds; the later rewrite may read release names with gh release list |
| 0.1.11 | 2026-11-25 | A ground rule that no committed file holds a literal crypt hash, vault header, ciphertext or private key, so tests make them at run time and guides show commands, not output; the later merge check covers local branches too; the Why section no longer says the vault files may have been plain text; the head after 980f37e explained |
| 0.1.10 | 2026-11-25 | Recreating the repository moved out of this phase, to be done once it works: the rewrite and its checks become the plan's last section, a prompt of its own run from main as it then stands; the git-filter-repo check and the CONTRIBUTORS.md exception go with it; the vault values were test-only, so the ROADMAP changes them rather than investigating them |
| 0.1.9 | 2026-11-25 | After the 0.1.6 release: the old repository is deleted, not archived, since its release assets survive a rewrite; all three tags kept and rewritten, and v0.1.6 published again, as the one exception to the no-reuse rule, which CONTRIBUTORS.md now states; CHANGELOG.md entries with each step; the README template filled in; dead .gitignore lines removed; the missing release guide reported, not written; the repository's version told apart from this plan's and the design document's |
| 0.1.8 | 2026-11-25 | git-filter-repo installed with pip in the Ansible virtual environment, so every command runs with that environment active |
| 0.1.7 | 2026-11-25 | After a review of 0.1.6: check for git filter-repo before starting; run filter-repo on the untouched clone, then reset main and delete branches; match 040f7e6 by its full original ID; the report names the rewritten ID it was built on; a leftover sentence about force-pushing removed |
| 0.1.6 | 2026-11-25 | After a review that ran 0.1.5 against the repository: localhost plays find the client root from ansible_inventory_sources, through the same shared task; check_inventory.py's boundary is the group_vars/ and host_vars/ directories, since promote_node.py writes connection variables into the stage hosts files; the repository is recreated rather than force-pushed, with main and the two tags, dropping the 10 merged branches, and the old checkout and worktree are replaced; fixtures list the incus host statically instead of asking the Incus server; commit 040f7e6's message is replaced in the rewrite; a misplaced sentence in step 4 moved back |
| 0.1.5 | 2026-11-25 | After checking against the full history: uc_known_hosts_file set on each stage's own group, since combined runs keep the last all.yml for every host, and tested combined; -i order is all defaults then all clients; the reason for per-stage defaults corrected; work in a worktree after the documents reorganization is committed on main; secrets/, vaults/, the vault scripts and the replaced guides removed from history; history checks match ciphertext, crypt hashes and line-start vault headers rather than words; raw-1970-01-01-03 and vaults/ added to the rotation; the client inventory check runs in a play on localhost |
| 0.1.4 | 2026-11-24 | After a fourth review: uc_known_hosts_file passed through realpath, since inventory_dir arithmetic gives a different unnormalized path at each stage; the step 4 test makes its own fixture with a host in every stage; debug confirmed not to connect to the host |
| 0.1.3 | 2026-11-24 | After a third review: step 8's grep matches the dollar sign as text; resolved values checked with the debug module, since ansible-inventory does not template; client-inventories.md says what the hook means for a departing client |
| 0.1.2 | 2026-11-24 | After a second review: uc_client_inventory and uc_known_hosts_file never set in the defaults; how the template derives uc_known_hosts_file per stage, and how the scripts find the known hosts file without Ansible; the step 2 grep made mechanical; the values the step 0 fixture must carry named |
| 0.1.1 | 2026-11-24 | After review: uc_secret is a plain file reader with a comment naming OpenBao, the client inventory check is one shared task file, check_inventory.py names its forbidden variables as a constant, the step 6 comparison parses rather than diffs, RN-ACC-08 is explained, step 0 produces no commits, step 8 checks file names and contents separately, and the flat defaults layout is recorded as considered |
| 0.1.0 | 2026-11-24 | First version |
