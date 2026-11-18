---
title: "Using the vault for batch passwords"
date: 2026-11-17
author: "Christopher Steel"
status: "Guide"
description: "How to set up the raw_batch vault password, create or import a raw node batch password, make it current, and give its hash to uc-ventoy."
---

# Using the vault for batch passwords

A raw node is built with a batch password: the password of the `initial` account, shared by every node of one build batch. The controller keeps it encrypted under `secrets/raw-batches/`, and uc-ventoy receives only its hash. This guide covers setting up the vault password once, then creating or importing a batch and making it current.

The design is described in the Secrets section of `en/docs/uc-controller-v0.1.7.md`.

## Before you start

Run every command from the root of the uc-controller repository, with the controller's Ansible virtual environment active. `new_raw_batch.py` calls `ansible-vault`, which lives in that environment.

```sh
source ~/.venvs/ansible/current/bin/activate
which ansible-vault
```

Output example:

```text
/home/initial/.venvs/ansible/current/bin/ansible-vault
```

If `which` prints nothing, create the environment first with `scripts/make_ansible_venv.py`.

## Set up the vault password

This is done once per operator and vault ID.

### The first operator

```sh
python3 scripts/vault-client.py --init --vault-id raw_batch
```

Output example:

```text
Wrote a new vault password for raw_batch to /home/initial/.config/uc-controller/vault/raw_batch
Copy it into the password manager; it is not shown here.
```

The password is not printed. Open the file it names and copy its contents into the password manager, then close the file. The file must keep mode `600`, or the client refuses to read it.

### Every other operator

```sh
python3 scripts/vault-client.py --set --vault-id raw_batch
```

It asks for the vault password. Paste it from the password manager. It never takes the password on the command line.

### Check the setup

```sh
python3 scripts/vault-client.py --status
```

## Create or import a batch

### Create a new batch

```sh
python3 scripts/new_raw_batch.py
```

It generates a password, stores it encrypted, makes the new batch current, and prints two lines to paste into uc-ventoy's `raw-node-input.yml`:

```text
password_batch: "raw-2026-11-17-01"
initial_password_hash: "$6$<salt>$<hash>"
```

The password itself is not printed. Use `--show-password` only if someone needs it at a console, and only once.

### Import an existing batch

A batch made by hand before `new_raw_batch.py` existed, such as `raw-2026-11-17-manual`, is imported. Add `--current` to make it current in the same step:

```sh
python3 scripts/new_raw_batch.py --import raw-2026-11-17-manual --current
```

It asks for the password twice. Paste it from the password manager. Only letters and digits are accepted. A password under 15 characters is still stored, with a warning, and recorded as `meets_min_length: false`: admission then reports RN-ACC-08 as failed for every node of that batch.

Output example:

```text
Batch password:
Again:
password_batch: "raw-2026-11-17-manual"
initial_password_hash: "$6$<salt>$<hash>"
```

Without `--current`, the batch is imported but not current, and the last line says so:

```text
note: imported raw-2026-11-17-manual, not current; current is None; commit secrets/raw-batches
```

Make it current afterwards with `--set-current`, below.

### About the hash

Every hash gets a new random salt, so the same password gives a different hash each time it is printed. All of them are valid. A node built with an earlier hash of the same password does not need rebuilding.

The hash is safe to put in `raw-node-input.yml`, which git ignores. Keep it out of chats, tickets and committed documents anyway: secret scanners flag `$6$` strings, and examples get copied.

## Check and change the current batch

### List the batches

```sh
python3 scripts/new_raw_batch.py --list
```

Output example:

```text
* raw-2026-11-17-manual  active    imported   2026-11-17T23:35:34-05:00
```

A `*` marks the current batch. `--list` also warns about any `.vault` file that is not actually encrypted.

### Make another batch current

```sh
python3 scripts/new_raw_batch.py --set-current raw-2026-11-17-manual
```

Output example:

```text
raw-2026-11-17-manual is now current
```

### Print a batch's hash again

```sh
python3 scripts/new_raw_batch.py --hash raw-2026-11-17-manual
```

### Retire a batch

```sh
python3 scripts/new_raw_batch.py --retire raw-2026-11-17-manual
```

Retiring deletes the batch's encrypted file. Only retire a batch once every node built with it has been onboarded and given its own password.

The script refuses to retire the current batch. It also refuses while any host in any stage inventory has `raw_node_batch` equal to the batch, and lists those hosts:

```text
error: these hosts have raw_node_batch: raw-2026-11-17-manual:
  deb13-vt-55b1 in inventories/raw/admitted.yml
They may still need its password. Use --force to retire it anyway.
```

`--force` retires the batch anyway, and prints a warning for each of those hosts. Those nodes can then no longer be reached with become until they have their own password. See `python3 scripts/new_raw_batch.py --help`.

## Commit

Each change to the batches is committed. The files are encrypted, apart from `index.yml`, which holds no secret.

```sh
git add secrets/raw-batches/
git commit -m "Import raw batch raw-2026-11-17-manual"
```

## Troubleshooting

| Message | Cause | Fix |
| --- | --- | --- |
| `ansible-vault not found` | The Ansible virtual environment is not active | `source ~/.venvs/ansible/current/bin/activate` |
| `can't open file 'scripts/new_raw_batch.py'` | The branch you are on does not have the script, or you are not at the repository root | Check with `git branch --show-current` and `pwd` |
| `argument --set-current: expected one argument` | `--set-current` was given without a batch ID, or combined with `--import` | Use `--import ID --current`, or `--set-current ID` on its own |
| `Decryption failed` from an Ansible run | No vault password is set up for that vault ID | Set it up as above |
