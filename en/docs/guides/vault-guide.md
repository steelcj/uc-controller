# uc-controller Vault Guide

Last updated: 2026-11-18

This guide is for operators of uc-controller. It covers the two kinds of secret the controller uses, where each one lives, and how to create, view, retire and change them.

## Two kinds of password

uc-controller uses two kinds of password. They must never be the same, and they never pass through the same prompt.

| Password | What it protects | Where it lives | Who types it |
| --- | --- | --- | --- |
| Vault password | Every encrypted file in the repo | The operator's password manager only | The operator, at the `Vault password:` prompt |
| Batch password | The `initial` user on raw nodes built from one batch | Encrypted in `secrets/raw-batches/`, inside the vault | Ansible, as the become password; the operator only when setting it on a node by hand |

The vault password unlocks the batch passwords, so if the vault password ever lands on a node, every batch is exposed with it.

## Where things are

| Item | Location | Notes |
| --- | --- | --- |
| Batch store | `secrets/raw-batches/` | Encrypted batch files plus `index.yml` |
| Batch index | `secrets/raw-batches/index.yml` | Not encrypted. Lists batches, the current batch, and `meets_min_length` for each |
| Batch tool | `scripts/new_raw_batch.py` | Creates, imports, lists and retires batches. Run with `--help` for options |
| Vault password client | `scripts/vault-client.py` | Run with `--help` to see how it fetches the vault password |
| Trusted host keys | `ssh/known_hosts` | Public keys, committed, keyed by hostname |

The batch store exists only on branches that include it. If `ls secrets/raw-batches/` finds nothing, you are on a branch without it, such as an older `main`. Use a worktree on a branch that has it.

## Viewing a batch password

Run these from the repo folder with the Ansible venv active.

```bash
cat secrets/raw-batches/index.yml
ls secrets/raw-batches/
ansible-vault view secrets/raw-batches/<file-for-the-batch>
```

Type the vault password from your password manager at the prompt. The batch password is printed in plain text, so run `clear` afterwards, and never paste it into a chat or a Claude Code session.

## Creating a batch

Create batches with `new_raw_batch.py` rather than by hand. A generated batch gives a random password and its hash from the same source, so the installer and the vault always agree.

1. Run `python3 scripts/new_raw_batch.py --help` and create a new batch.
2. Use the hash it produces in the uc-ventoy configuration for the `initial` user.
3. Build nodes from that stick. They join the batch through `raw_node_batch`.

### Importing an existing password

Use `--import` only when a node was already built with a password that is not in the store. Imports follow these rules:

- A password under 15 characters is stored with a warning and recorded as `meets_min_length: false`.
- A password with characters other than letters and digits is refused.
- At the import prompt, paste the node's password and nothing else. Never paste the vault password there. That is how the 2026-11-17 batch ended up holding the vault password.

## Setting a batch password on a node

Do this only when a node's password does not match its batch, for example after an import mistake.

1. Log into the node as `initial`.
2. Run `passwd`, enter the old password, then paste the batch password twice.
3. Check it with `sudo -k && sudo -v`.
4. Run `clear` on your own machine.

Before you paste, compare the batch password with your vault password. If they match, stop: the batch is wrong, so retire it and create a new one.

## Retiring a batch

```bash
python3 scripts/new_raw_batch.py --retire <batch-id>
```

`--retire` refuses while any host in a stage inventory still has `raw_node_batch` set to that batch, and names those hosts. Change those nodes' passwords to a newer batch first, or pass `--force` when the batch is compromised and must go regardless.

## Changing the vault password

Change the vault password on a schedule you choose, and at once if it was ever exposed, typed in the wrong place or stored anywhere but your password manager.

1. Generate a new vault password and save it in your password manager as a new entry. Keep the old entry until step 4 passes.
2. List everything encrypted on the branch, both whole files and inline `!vault` values:
   ```bash
   grep -rl '^\$ANSIBLE_VAULT' --exclude-dir=.git .
   grep -rn '!vault' --include='*.yml' --exclude-dir=.git .
   ```
3. Rekey the whole files with `ansible-vault rekey <file> ...`, giving the old password and then the new one. Inline `!vault` values are not handled by rekey: decrypt and re-encrypt each with `ansible-vault encrypt_string`.
4. Run `python3 tests/run_tests.py` and view one batch with `ansible-vault view` to prove everything opens with the new password.
5. Commit, then delete the old entry from your password manager.

Older commits still hold files encrypted with the old password. That is acceptable only because the old password is retired and never reused.

## Rules

- The vault password lives in the password manager only, never in a file in the repo, a shell history, a note or a chat.
- A batch password is never the vault password, and never a password used anywhere else.
- Only paste a password into the prompt that asks for that exact password.
- Never print a password where a Claude Code session or a log can see it. Ask sessions for commands, not values.
- Run `clear` after viewing any secret.

## If a secret is exposed

| What was exposed | Do this |
| --- | --- |
| A batch password | Retire the batch with `--force`, create a new batch, and set the new password on every node in the old batch |
| The vault password | Change the vault password as above, then treat every batch as exposed: retire and replace them all |
| A batch holds the vault password | Both of the above: change the vault password first, then replace the batch |

## Open items

- Confirm how `vault-client.py` fetches the vault password, and add the exact command here.
- Confirm the batch file naming in `secrets/raw-batches/` and the exact `new_raw_batch.py` command for creating a batch.
- Record the outcome of the investigation into how batch `raw-2026-11-17-manual` came to hold the vault password.
