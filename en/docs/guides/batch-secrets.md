---
title: Batch Secrets
description: Where uc-controller keeps the password of each raw node batch, how to create a batch file without the password reaching shell history or the process list, and how to retire a batch.
version: 0.1.4
status: provisional
date: 2026-11-26
language: en-CA
---

# Batch Secrets

## Abstract

A raw node is built with a batch password: the password of the `initial` user, shared by every node of one build batch. The controller needs the password itself, to become root on an admitted node, and uc-node needs only its hash, to build the node. So each batch has two files, outside every repository, one for each controller:

### uc-node

uc-node's file will hold the batch password's hashes, and no password. uc-node does not read it yet.

```text
~/.secrets/uc/build/batches/<batch>.yml
```

### uc-controller

uc-controller's file holds the batch password and nothing else. There is one file per batch, and so one password per file.

```text
~/.secrets/uc/fleet/batches/<batch>.yml
```

The raw node contract gives the producer (uc-node) only the hash, and the two files keep that promise. Playbooks and group variables read it only through the `uc_secret` lookup, which refuses a file whose modes or owner are wrong. The batch name is not secret: inventories and node definitions carry it, and nothing else.

## Contents

- [Layout](#layout)
- [What reads the file](#what-reads-the-file)
- [Choosing a password](#choosing-a-password)
- [Creating a batch file](#creating-a-batch-file)
- [Checking a batch file](#checking-a-batch-file)
- [Retiring a batch](#retiring-a-batch)
- [What never to do](#what-never-to-do)
- [Changelog](#changelog)

## Layout

```text
~/.secrets/                             0700
~/.secrets/uc/                          0700
~/.secrets/uc/fleet/                    0700, uc-controller's secrets root
~/.secrets/uc/fleet/batches/            0700
~/.secrets/uc/fleet/batches/<batch>.yml 0600
~/.secrets/uc/build/                    0700, uc-node's secrets root, later
~/.secrets/uc/build/batches/<batch>.yml 0600
```

Every directory, and each file, is owned by the operator who runs Ansible. `uc_secret` refuses the read, and says what to fix, when its root or a directory below it is not mode `0700`, when the file is not mode `0600`, or when any of them belongs to someone else.

uc-controller's batch file is a YAML mapping with one key:

| Key | Holds | Read by |
| :-- | :-- | :-- |
| `initial_password` | The password itself | uc-controller, as the admitted group's become password and to measure it against RN-ACC-08 during admission |

uc-node's batch file will hold `initial_password_hash`, the password's SHA-512 crypt hash, and `root_password_hash`, which uc-node reads when it builds the nodes of the batch. uc-node does not read batch files yet; its own guide will say how to make that file when it does. On one workstation the operator's account can read both files, so here the split holds by convention. In OpenBao, policies will enforce it.

This layout is an approach to try, as `en/docs/design/raw-node-handoff-inventories-and-secrets-v0.1.0.md` in uc-contracts proposes, and may change when it is tried.

Batch names follow `raw-YYYY-MM-DD-NN`. Examples in these documents use `raw-1970-01-01-01`, the Unix epoch, a date no real batch can have.

## What reads the file

The `uc_secret` lookup, in `shared/plugins/lookup/uc_secret.py`, is the only way anything reads a batch file:

```yaml
ansible_become_password: "{{ lookup('uc_secret', 'batches/' ~ raw_node_batch, key='initial_password') }}"
```

A lookup is evaluated only when its value is used, so a run that never becomes root on an admitted node never reads the file. The value comes back as unsafe text, so a password containing `{{` is never templated. Any task that prints a value read through `uc_secret` sets `no_log: true`.

`uc_secret` reads under `~/.secrets/uc/fleet/` only, so uc-controller never reads uc-node's file. Later, an OpenBao backend replaces the file read inside `uc_secret`, at `batches/<batch>` in the client namespace's `fleet` mount, which maps one to one onto the file's path. Playbooks and inventories do not change when that happens.

For tests, the environment variable `UC_SECRETS_DIR` names another secrets root. Tests make their own root in a temporary directory, with made-up values, and never read `~/.secrets/`.

## Choosing a password

RN-ACC-08, a clause of the raw node contract, asks for a batch password of at least 15 characters. The node cannot measure the password it was built with, so admission measures it on the controller and warns when it is shorter. A passphrase of six or more words chosen with dice from a published word list meets the clause easily, and can be typed at a console.

## Creating a batch file

Run these in bash, in one terminal. The password is read from the terminal with `read -rs`, so it is not echoed and never reaches shell history. It is written to the file by `printf`, a bash builtin, so it never appears in the process list either.

```bash
batch=raw-1970-01-01-01
umask 077
mkdir -p ~/.secrets/uc/fleet/batches
chmod 0700 ~/.secrets ~/.secrets/uc ~/.secrets/uc/fleet ~/.secrets/uc/fleet/batches

IFS= read -rs -p 'Batch password: ' pw; echo
IFS= read -rs -p 'Batch password again: ' again; echo
if [ "$pw" != "$again" ] || [ -z "$pw" ]; then
    echo 'The two entries differ, or are empty. Nothing was written.'
else
    # YAML single quotes: a quote inside the value is written twice.
    quote() { local s=${1//\'/\'\'}; printf "'%s'" "$s"; }
    printf 'initial_password: %s\n' "$(quote "$pw")" > ~/.secrets/uc/fleet/batches/"$batch".yml
    chmod 0600 ~/.secrets/uc/fleet/batches/"$batch".yml
fi
unset pw again
```

Keep a copy of the password where you keep other secrets that must survive the loss of this machine, such as a password manager. The file is the working copy, not the backup.

## Checking a batch file

These commands show the modes, and the length of the password as `uc_secret` reads it, without showing the password. The outputs below are examples: the sizes, dates and length on your machine will differ.

### Check the directories

```bash
ls -ld ~/.secrets ~/.secrets/uc ~/.secrets/uc/fleet ~/.secrets/uc/fleet/batches
```

Output example:

```text
drwx------ 3 operator operator 4096 Nov 26 13:30 /home/operator/.secrets
drwx------ 3 operator operator 4096 Nov 26 13:30 /home/operator/.secrets/uc
drwx------ 3 operator operator 4096 Nov 26 13:30 /home/operator/.secrets/uc/fleet
drwx------ 2 operator operator 4096 Nov 26 13:32 /home/operator/.secrets/uc/fleet/batches
```

Every line must start with `drwx------` and name you as owner.

### Check the file

```bash
ls -l ~/.secrets/uc/fleet/batches/raw-1970-01-01-01.yml
```

Output example:

```text
-rw------- 1 operator operator 64 Nov 26 13:32 /home/operator/.secrets/uc/fleet/batches/raw-1970-01-01-01.yml
```

The line must start with `-rw-------` and name you as owner.

### Check the password through uc_secret

Run this from the uc-controller checkout, so its `ansible.cfg` finds the lookup:

```bash
ansible localhost -m ansible.builtin.debug \
  -a "msg={{ lookup('uc_secret', 'batches/raw-1970-01-01-01', key='initial_password') | length }}"
```

Output example:

```text
[WARNING]: No inventory was parsed, only implicit localhost is available
localhost | SUCCESS =>
    msg: 43
```

The number is the password's length. RN-ACC-08 asks for at least 15. The warning is expected, since the command uses no inventory. If `uc_secret` refuses the file, its message names the file and what to change.

Do not paste the output of these commands from a real batch into a document or a session. The file size and the length together tell a reader how long the password is.

## Retiring a batch

A batch is retired when its password must no longer open anything: when the nodes built with it have been onboarded and no longer use it, or when the password may have been seen by someone else.

1. Find every host that still carries the batch, in every client inventory:

   ```bash
   grep -rl 'raw_node_batch: raw-1970-01-01-01' ~/uc-inventories/*/
   ```

2. For each one, either onboard it, so it no longer depends on the batch password, or rebuild it with a new batch and admit it again.
3. Remove the batch from uc-node's node definitions, so no new node is built with it.
4. Delete both files, and the copy you keep elsewhere:

   ```bash
   rm -f ~/.secrets/uc/fleet/batches/raw-1970-01-01-01.yml ~/.secrets/uc/build/batches/raw-1970-01-01-01.yml
   ```

A password that may have been seen is not reused under another batch name. Make a new one.

## What never to do

- Never commit a batch file, or a batch's password or hash, to any repository, client inventories included. `scripts/check_inventory.py` refuses a client inventory that holds a crypt hash or a lookup.
- Never pass the password or the hash on a command line, where the process list and shell history keep it.
- Never put the password in uc-node's file, or a hash in uc-controller's.
- Never set `ansible_become_password` anywhere else. The admitted group's default in uc-controller is the one place it is set.

## Changelog

| Version | Date | Change |
| :-- | :-- | :-- |
| 0.1.4 | 2026-11-26 | The example outputs show the owner `operator` and the home `/home/operator`, the names the documents use for the operator's account |
| 0.1.3 | 2026-11-26 | The example batch name is `raw-1970-01-01-01`, the Unix epoch, a date no real batch can have, in place of `raw-EXAMPLE-01`, which did not follow the `raw-YYYY-MM-DD-NN` pattern |
| 0.1.2 | 2026-11-26 | Abstract given one subsection per controller, as written by Christopher, with its wording completed: one password per batch file. Checking a batch file split into three subsections, with `~/.secrets` and `~/.secrets/uc` added to the directory check, outputs marked as examples in `text` blocks, the sizes and length replaced with made-up values, what each check must show, and a warning not to paste real output |
| 0.1.1 | 2026-11-26 | Split each batch into two files, one per controller: `~/.secrets/uc/fleet/batches/<batch>.yml`, uc-controller's, with `initial_password` only, and `~/.secrets/uc/build/batches/<batch>.yml`, uc-node's, for the hashes later. `uc_secret`'s root is `~/.secrets/uc/fleet`. The recipe writes uc-controller's file only |
| 0.1.0 | 2026-11-25 | First version, replacing the ansible-vault guides `vault-guide.md`, `plain-vault-batch-passwords.md` and `vault-check.md` |
