---
title: Client Inventories
description: What a client inventory repository holds and never holds, uc-node's intake/ and candidates/ in it, how to make one, how uc-controller loads it after its own defaults, its pre-commit hook, and how to hand it to a client who leaves.
version: 0.2.0
status: provisional
date: 2026-11-27
language: en-CA
---

# Client Inventories

## Abstract

uc-controller is code: playbooks, scripts, and the defaults that say how each kind of node is reached and set up. Everything that describes one client, which nodes it has, at which stage, its locale, firewall rules and controller key, and the host keys trusted for its nodes, lives in a private repository of its own, one per client. Secrets live in neither: batch passwords are in `~/.secrets/uc/fleet/batches/`, as `en/docs/guides/batch-secrets.md` describes. A run loads uc-controller's `inventory-defaults/` first and the client's directories after them, so a client value overrides a default without anyone editing uc-controller.

## Contents

- [What a client repository holds](#what-a-client-repository-holds)
- [What it never holds](#what-it-never-holds)
- [Making one](#making-one)
- [Keeping it private](#keeping-it-private)
- [Running playbooks against it](#running-playbooks-against-it)
- [Where a value goes](#where-a-value-goes)
- [The pre-commit hook](#the-pre-commit-hook)
- [Scripts](#scripts)
- [When a client leaves](#when-a-client-leaves)
- [Changelog](#changelog)

## What a client repository holds

| Path | Holds | Written by |
| :-- | :-- | :-- |
| `intake/` | uc-node's node definitions, one per node it is to build, without secrets | uc-node's `scripts/new-node` |
| `candidates/` | uc-node's handoff records, one per node it built, which admission reads and never changes | uc-node, at the end of a build |
| `raw/admitted.yml` | Raw nodes admitted under the raw node contract, each under its fully qualified domain name and with its batch name, `raw_node_batch` | `ingress/playbooks/05_admit.yml` |
| `raw/discovered.yml` | Raw nodes found by a subnet scan | `ingress/playbooks/00_discover.yml` |
| `raw/incus.yml` | The Incus inventory plugin's settings, deleted when the client has no Incus server | By hand |
| `raw/group_vars/` | Values for the raw stage | By hand |
| `onboard/<environment>/hosts.yml` | Onboarded nodes of one environment, such as `dev` or `stage` | `scripts/promote_node.py` |
| `onboard/<environment>/group_vars/` | The controller key, the initial user's public keys, locale, time zone, and SSH into the node, `firewall_onboard_ssh`, for that environment | By hand |
| `normalized/<environment>/hosts.yml` | Normalized nodes, with their extra groups | `scripts/promote_node.py` |
| `normalized/<environment>/group_vars/` | The normalize firewall services, `firewall_normalize_services`, and a file per group, such as `webservers.yml`, for the specialize services, `firewall_specialize_services` | By hand |
| `ssh/known_hosts` | The host keys trusted for admitted nodes, at every stage | `05_admit.yml` |
| `.githooks/pre-commit` | The check run before every commit | `scripts/new-inventory` |

The generated files are committed. The history then records when each node was admitted, promoted and trusted, which the privileged access policy asks for host keys (PA-HOST-02).

`intake/` and `candidates/` are uc-node's, as the raw node handoff design in uc-contracts sets out, and are never inventory sources: `scripts/inventory-args` lists only stage directories. uc-node's guides say how its files are written and committed, and [Admit and Onboard](admit-and-onboard.md) how admission reads the candidates.

## What it never holds

- **Secrets.** No batch password or its hash, no private key, no ansible-vault file. Nodes carry only the name of their batch.
- **Logic.** No connection settings in `group_vars/` or `host_vars/` (`ansible_connection`, `ansible_user`, `ansible_ssh_common_args`, `ansible_ssh_host_key_checking`, `ansible_become_password`), and no lookups. How a node is reached is uc-controller's `inventory-defaults/`, the same for every client. The scripts that write hosts files do set connection settings per host, and that is allowed.
- **uc-controller's history.** A client repository starts with its own first commit, not as a fork or a copy of uc-controller.

## Making one

A client's inventory lives in the client's private folder, `~/.private/uc/<client>/uc-inventory`, beside its log, as uc-node's guide 0, Set Up a Client, sets up. From the uc-controller checkout:

```bash
scripts/new-inventory ~/.private/uc/example-org/uc-inventory
```

It copies `inventory-template/` there, runs `git init` with the branch `main`, whatever git's own default, and sets `core.hooksPath` to `.githooks`. It refuses a path that exists and is not empty, and it creates no remote and no commit. It says what it made and what comes next:

```text
Made a client inventory in /home/operator/.private/uc/example-org/uc-inventory
  a git repository on the branch main, with its pre-commit hook, no remote and no commit.
Next, as uc-node's guide 0, Set Up a Client (en/docs/guides/0-set-up-a-client.md in uc-node), describes:
  replace every CHANGE-ME value under /home/operator/.private/uc/example-org/uc-inventory/onboard,
  delete /home/operator/.private/uc/example-org/uc-inventory/raw/incus.yml if this client has no Incus server,
  then make the first commit with UC_CONTROLLER=/home/operator/uc-controller set.
Keep the repository private: it names the client's hosts and addresses.
```

Then:

1. Replace every `CHANGE-ME` value under `onboard/`: the controller's private key path, `onboard_ssh_private_key_file`, and the initial user's public keys, `onboard_initial_authorized_keys`. Set the locale, time zone and firewall rules the client needs.
2. Delete `raw/incus.yml` if the client has no Incus server.
3. Make the first commit, on `main`, with `UC_CONTROLLER` set, as the hook needs. uc-node's guide 0 says which of its own files go in it:

   ```bash
   cd ~/.private/uc/example-org/uc-inventory
   git add -A
   git diff --cached --stat
   UC_CONTROLLER=~/uc-controller git commit -m "Start the example-org inventory"
   ```

The template is versioned with the code that reads it, in uc-controller, so the two cannot drift. A client repository made from an older template keeps working as long as its layout does not change; when the template changes its layout, its changelog says so.

## Keeping it private

A client repository names the client's hosts and their addresses. Keep it on the controller, or in a private remote that only the people who manage the client can read. Never push it to a public host, and never add it to uc-controller as a submodule.

## Running playbooks against it

Run playbooks from the uc-controller checkout, with `scripts/inventory-args` giving the `-i` options for the stages the playbook needs:

```bash
ansible-playbook $(scripts/inventory-args ~/.private/uc/example-org/uc-inventory raw onboard/dev) \
  ingress/playbooks/05_admit.yml -e admit_batch_id=raw-YYYY-MM-DD-NN -e admit_from_candidates=true
```

| Playbook | Stages |
| :-- | :-- |
| `ingress/playbooks/00_discover.yml` | `raw` |
| `ingress/playbooks/05_admit.yml` | `raw onboard/<environment>` |
| `ingress/playbooks/10_onboard.yml` | `raw onboard/<environment>` |
| `converge/playbooks/20_normalize.yml` | `onboard/<environment> normalized/<environment>` |
| `converge/playbooks/30_specialize.yml` | `onboard/<environment> normalized/<environment>` |

`inventory-args` prints all of uc-controller's defaults directories first, then all the client's directories, each in the order the stages are given. For `raw onboard/dev`:

```text
-i <uc-controller>/inventory-defaults/raw -i <uc-controller>/inventory-defaults/onboard
-i <client>/raw -i <client>/onboard/dev
```

Ansible merges inventory sources in the order they are given, and group variables from a later source override those of an earlier one. Defaults first means a client value always overrides a default, whichever stages a run combines. Playbook-level `group_vars/` were set aside for this reason: they take precedence over inventory variables, and would block client overrides.

Every playbook starts with a play on localhost that refuses to run without a client inventory, naming `scripts/inventory-args`. It also finds the client inventory's root from the `-i` sources, so playbooks that write into the client inventory, such as admission and promotion, know where it is. `10_onboard.yml` writes promoted nodes into the one onboard environment loaded, and `20_normalize.yml` moves them into the one normalized environment loaded.

## Where a value goes

A run that combines stages merges their `all` groups, and the last directory loaded wins for every host. Two rules follow:

- A value in a `group_vars/all.yml` must mean the same at every stage. `uc_client_inventory: true` is one.
- A value that differs by stage goes on the stage's own group: `raw/group_vars/raw.yml`, `onboard/<environment>/group_vars/onboarded.yml` or `normalized/<environment>/group_vars/normalized.yml`. `uc_known_hosts_file` is one: it is built from each stage's directory, which is one level deep for `raw` and two for the others, and resolves to the repository's `ssh/known_hosts` at every stage.

## The pre-commit hook

`.githooks/pre-commit` runs uc-controller's `scripts/check_inventory.py` on the repository, then `yamllint` with the repository's `.yamllint`. `check_inventory.py` refuses:

- a connection variable from the list above set under a `group_vars/` or `host_vars/` directory, or on a group in a hosts file;
- an ansible-vault file, a password hash, or a private key, in any file, `intake/` and `candidates/` included;
- a lookup in a template, in any YAML file;
- an admitted host without `raw_node_batch`, or without an entry in `ssh/known_hosts`;
- a host that came through admission whose name is not a fully qualified domain name: every host in `raw/admitted.yml`, and every host in an `onboard/` or `normalized/` hosts file that carries `raw_node_batch`. Hosts from the Incus plugin or a subnet scan keep the names they arrive with;
- a file in `candidates/` that is not a candidate: one node, keyed by its fully qualified domain name and named after it, with every field of the raw node handoff design and no other, each of its form. It is read as admission reads it.

yamllint's line-length limit, 120 characters, is a warning, not an error. The hook shows the warning and commits. Public key lines run past any limit: an ed25519 key with a client's comment, such as `example-org-raw-initial-id_ed25519`, is about 130 characters, and an RSA key several hundred. Other yamllint findings still stop the commit.

The hook finds `check_inventory.py` through the `UC_CONTROLLER` environment variable, and refuses every commit until it points at a uc-controller checkout. Set it in the shell profile of everyone who commits to client repositories:

```bash
export UC_CONTROLLER=~/uc-controller
```

`promote_node.py` sets it for its own commits when it is not set.

## Scripts

The scripts that read or write a client inventory take its root with `--inventory`, and stages by name:

```bash
python3 scripts/promote_node.py --inventory ~/.private/uc/example-org/uc-inventory \
  --from raw --to onboard/dev --host dev.example.org --key-file ~/.ssh/example-org-raw-initial-id_ed25519
python3 scripts/demote_node.py --inventory ~/.private/uc/example-org/uc-inventory \
  --from onboard/dev --to raw --host dev.example.org
python3 scripts/reset_inventories.py --inventory ~/.private/uc/example-org/uc-inventory --dry-run
python3 scripts/check_inventory.py ~/.private/uc/example-org/uc-inventory
python3 scripts/read_candidates.py --inventory ~/.private/uc/example-org/uc-inventory --batch raw-YYYY-MM-DD-NN
```

They use `<root>/ssh/known_hosts` directly, without asking Ansible. Promotion and demotion carry a host's name unchanged. `read_candidates.py` prints, as JSON, the valid candidates of a batch and every candidate file that is not valid, as admission sees them.

## When a client leaves

A client who leaves takes their repository and their batch files, and nothing else:

1. Give them the repository, as a bundle or by pushing it to a remote they own: `git bundle create example-org.bundle --all`.
2. Give them the batch files their nodes were built with, `~/.secrets/uc/fleet/batches/<batch>.yml` for each `raw_node_batch` in their inventory, over a channel fit for secrets, never by email in clear text. Then retire those batches here, as `en/docs/guides/batch-secrets.md` describes.
3. Remove the repository from the controller.

The hook refuses every commit until `UC_CONTROLLER` points at a uc-controller checkout. A client who takes their repository over therefore either installs uc-controller and sets `UC_CONTROLLER`, removes `.githooks/pre-commit` (and `git config --unset core.hooksPath`), or commits with `git commit --no-verify`. Say so when you hand the repository over.

## Changelog

| Version | Date | Change |
| :-- | :-- | :-- |
| 0.2.0 | 2026-11-27 | uc-node's `intake/` and `candidates/` in the layout. The inventory in the client's private folder, `~/.private/uc/<client>/uc-inventory`. `new-inventory` makes the branch `main` and says what it made and what comes next, and the first commit follows uc-node's guide 0. Admission with `admit_from_candidates`. The hook's checks of names and candidates, and line-length as a warning. Examples name `dev.example.org` and the client's key file. Link to [Admit and Onboard](admit-and-onboard.md) |
| 0.1.3 | 2026-11-26 | The real host in the promote and demote examples replaced by `deb13-vt-0001` |
| 0.1.2 | 2026-11-26 | The example batch name is `raw-1970-01-01-01` |
| 0.1.1 | 2026-11-26 | The firewall values by their new names, and batch files in `~/.secrets/uc/fleet/batches/` |
| 0.1.0 | 2026-11-25 | First version, from the inventory split |
