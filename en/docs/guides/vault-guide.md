# uc-controller Vault Guide

Last updated: 2026-11-18

This guide is for operators of uc-controller. It follows the order you work in: set up the vault passwords, create a batch, build and admit nodes with it, then view, retire and rekey as needed.

## Three kinds of secret

uc-controller uses three kinds of secret. They must never be the same, and they never pass through the same prompt.

| Secret | What it protects | Where it lives | Who types it |
| --- | --- | --- | --- |
| `raw_batch` vault password | The batch store, `secrets/raw-batches/` | `~/.config/uc-controller/vault/raw_batch` and the operator's password manager | The operator, once, during setup |
| `node` vault password | Secrets of single nodes, encrypted with the `node` vault ID. None exist yet; see The node vault | `~/.config/uc-controller/vault/node` and the operator's password manager | The operator, once, during setup |
| Batch password | The `initial` user on raw nodes built from one batch | Encrypted inside the batch store | Nobody, normally. Ansible uses it as the become password |

The `raw_batch` vault password is the lock on the batch store. It is not a batch password, despite the name. Confusing the two is how batch `raw-2026-11-17-manual` came to hold a vault password.

## Where things are

| Item | Location | Notes |
| --- | --- | --- |
| Vault password client | `scripts/vault-client.py` | Ansible calls it to read vault passwords. It must stay executable: if it is not, Ansible uses the script's text as the vault password, and `new_raw_batch.py` refuses to run |
| Vault password files | `~/.config/uc-controller/vault/<vault-id>` | Must be mode `600`, or the client refuses to read them |
| Vault IDs Ansible loads | `vault_identity_list` in `ansible.cfg` | Only `raw_batch` today. `node` is added when the first node secret exists |
| Batch tool | `scripts/new_raw_batch.py` | Creates, imports, lists, rehashes and retires batches |
| Batch store | `secrets/raw-batches/` | `index.yml` plus one `<batch-id>.vault` per active batch, such as `raw-2026-11-18-01.vault` |
| Batch index | `secrets/raw-batches/index.yml` | Not encrypted. Lists batches, the current batch, and `meets_min_length` for each |
| Trusted host keys | `ssh/known_hosts` | Public keys, committed, keyed by hostname |

The batch store exists only on branches that include it. If `ls secrets/raw-batches/` finds nothing, you are on a branch without it.

## Set up the vault passwords

This is done once per operator, for each vault ID. Run it from the root of the repository with the Ansible venv active.

### The first operator

#### Create the raw_batch vault password

```bash
python3 scripts/vault-client.py --init --vault-id raw_batch
```

Output:

```text
Wrote a new vault password for raw_batch to /home/initial/.config/uc-controller/vault/raw_batch
Copy it into the password manager; it is not shown here.
```

If the file already exists, `--init` refuses and changes nothing:

```text
error: /home/initial/.config/uc-controller/vault/raw_batch already exists; remove it first to replace it
```

Removing it is only right when nothing is encrypted with it yet. Otherwise follow Change a vault password.

#### Create the node vault password

```bash
python3 scripts/vault-client.py --init --vault-id node
```

Output:

```text
Wrote a new vault password for node to /home/initial/.config/uc-controller/vault/node
Copy it into the password manager; it is not shown here.
```

Each command writes a new random 40-character password to `~/.config/uc-controller/vault/<vault-id>` and does not print it. Copy each one into the password manager as its own entry, named after its vault ID.

To copy without showing the password on screen:

```bash
xclip -selection clipboard < ~/.config/uc-controller/vault/raw_batch
```

If you use `cat` instead, start the command with a space so bash leaves it out of history. That works only when `echo $HISTCONTROL` shows `ignorespace` or `ignoreboth`.

```bash
echo $HISTCONTROL
```

With a space before the command:

```bash
 cat ~/.config/uc-controller/vault/raw_batch
```

Then run `history` to confirm the command is not there, and `clear` to empty the screen.

### Every other operator

```bash
python3 scripts/vault-client.py --set --vault-id raw_batch
python3 scripts/vault-client.py --set --vault-id node
```

Each asks for that vault ID's password twice. Paste it from the password manager. The client never takes a password on the command line, and refuses one shorter than 20 characters.

### Check the setup

`--status` checks one vault ID at a time. Without `--vault-id` it checks `raw_batch`.

```bash
python3 scripts/vault-client.py --status --vault-id raw_batch
python3 scripts/vault-client.py --status --vault-id node
```

Output example:

```text
raw_batch: set up (/home/initial/.config/uc-controller/vault/raw_batch)
node: set up (/home/initial/.config/uc-controller/vault/node)
```

It prints no secret, and exits 1 for a vault ID that is not set up.

## Create a batch

A batch password is made by `new_raw_batch.py`, never by hand and never copied from the password manager. The script generates a random password, encrypts it into the batch store with the `raw_batch` vault password, and gives you the hash to build nodes with.

```bash
python3 scripts/new_raw_batch.py
python3 scripts/new_raw_batch.py --list
```

With no action option, `new_raw_batch.py` creates a batch:
- It generates a password of 24 letters and digits.
- It stores the password as `secrets/raw-batches/raw-<today>-NN.vault`, with `NN` the first number not used before that day, and records the batch in `index.yml` with `meets_min_length: true`.
- It makes the new batch current.
- It prints two lines, ready for uc-ventoy's `raw-node-input.yml`, and nothing else on standard output:

```text
password_batch: "raw-2026-11-18-01"
initial_password_hash: "$6$<salt>$<hash>"
```

Optional:
- `--batch-id ID` names the batch.
- `--length N` makes a longer password (at least 24).
- `--show-password` also prints the password once, on standard error, for someone who needs it at a console.

`--list` should show the new batch with a `*`, as current. Commit `secrets/raw-batches/` afterwards.

### Build nodes with the batch

1. Copy the two printed lines into uc-ventoy's `raw-node-input.yml`. uc-ventoy uses `initial_password_hash` for the `initial` user, and writes `password_batch` on the node as `RAW_NODE_PASSWORD_BATCH` in `/etc/raw-node/raw-node.conf`, so you can tell at the console which batch a node has.
2. Build nodes from that stick.
3. Admit them with `ingress/playbooks/05_admit.yml`. Admission records the batch on each node's inventory entry as `raw_node_batch`: the current batch, or the one given with `-e admit_batch_id=...`. From then on Ansible reads that node's become password from that batch, even after another batch becomes current.

To build more nodes of an existing batch later, print a fresh hash of the same password with `python3 scripts/new_raw_batch.py --hash <batch-id>`. Every hash gets a new salt, and all of them are valid.

### Importing an existing password

Use `--import` only when a node was already built with a password that is not in the store.

```bash
python3 scripts/new_raw_batch.py --import <batch-id> --current
```

- A password under 15 characters is stored with a warning and recorded as `meets_min_length: false`. Admission then reports RN-ACC-08 as not met for every node of that batch.
- A password with characters other than letters and digits is refused.
- At the import prompt, paste the node's own password and nothing else. Never paste a vault password there.

## View a batch password

You rarely need to. The main reason is setting a password on a node by hand.

```bash
cat secrets/raw-batches/index.yml
ls secrets/raw-batches/
ansible-vault view secrets/raw-batches/<batch-id>.vault
```

Run it from the root of the repository: `ansible-vault` finds the vault client through `ansible.cfg` there. The batch password is printed in plain text. Run `clear` afterwards, and never paste it into a chat or a Claude Code session.

## Check a batch against the vault passwords

This shows whether a batch password is the same as a vault password, without printing either one:

```bash
batch=secrets/raw-batches/<batch-id>.vault
for id in raw_batch node; do
  if [ "$(ansible-vault decrypt --output - "$batch")" = "$(cat ~/.config/uc-controller/vault/$id)" ]; then
    echo "SAME as the $id vault password: retire this batch"
  else
    echo "different from the $id vault password"
  fi
done
```

## Set a batch password on a node

Do this only when a node's password does not match its batch.

1. Check the batch with the command above. If it matches either vault password, stop: retire the batch and create a new one.
2. Log into the node as `initial`.
3. Run `passwd`, enter the old password, then paste the batch password twice.
4. Check it with `sudo -k && sudo -v`.
5. Run `clear` on your own machine.

## Retire a batch

```bash
python3 scripts/new_raw_batch.py --retire <batch-id>
```

`--retire` refuses in two cases:
- The batch is current. Make another batch current first, with `--set-current`.
- Any host in a stage inventory still has `raw_node_batch` set to the batch. It names those hosts. Move those nodes to a newer batch first, or pass `--force` when the batch is compromised and must go regardless.

Retiring deletes the batch's encrypted file and marks it retired in `index.yml`. The ID is never used again. Git history still holds the encrypted file.

## The node vault

The `node` vault ID is for secrets of single nodes, such as the password onboarding will give each node's `initial` user in place of the batch password (OE-ACC-03). The vault password can be set up now, as above, but nothing uses it yet:

- No script creates node secrets. The onboarding kickoff decides their layout and adds the tool. The place reserved for them is `secrets/nodes/<hostname>.vault`.
- `ansible.cfg` names only `raw_batch` in `vault_identity_list`, so playbooks cannot decrypt a `node` file yet.
- `.gitignore` allows only `secrets/raw-batches/index.yml` and `secrets/raw-batches/*.vault` under `secrets/`, so a file in `secrets/nodes/` would not be committed.

Wait for the onboarding kickoff rather than making node files by hand. If you need one before then, the first two changes are:

```ini
# ansible.cfg, [defaults]
vault_identity_list = raw_batch@scripts/vault-client.py, node@scripts/vault-client.py
```

```gitignore
# .gitignore, after the secrets/raw-batches lines
!/secrets/nodes/
/secrets/nodes/*
!/secrets/nodes/*.vault
```

Then make the file with a generated password, piped straight into `ansible-vault`. The password is never on screen, in the shell history or in a plain file:

```bash
mkdir -p secrets/nodes
python3 -c "import secrets, string; a = string.ascii_letters + string.digits; print(''.join(secrets.choice(a) for _ in range(24)))" \
  | ansible-vault encrypt --vault-id node@scripts/vault-client.py --encrypt-vault-id node \
      --output secrets/nodes/<hostname>.vault -
head -1 secrets/nodes/<hostname>.vault
```

Output:

```text
$ANSIBLE_VAULT;1.2;AES256;node
```

The first line must name `node`. If it names `raw_batch`, the file is locked with the wrong vault password. A playbook reads the file with `lookup('ansible.builtin.unvault', 'secrets/nodes/<hostname>.vault') | trim`.

## Change a vault password

Change a vault password on a schedule you choose, and at once if it was ever exposed, typed in the wrong place or stored anywhere but your password manager and its vault file.

1. Generate a new password for that vault ID and save it in your password manager as a new entry. Keep the old entry until step 5 passes. For example, without showing it: `python3 -c "import secrets, string; a = string.ascii_letters + string.digits; print(''.join(secrets.choice(a) for _ in range(40)))" | xclip -selection clipboard`, then paste it into the password manager.
2. List everything encrypted on the branch, both whole files and inline `!vault` values, and keep the files whose first line names that vault ID:
   ```bash
   grep -rl '^\$ANSIBLE_VAULT;1.2;AES256;<vault-id>' --exclude-dir=.git .
   grep -rn '!vault' --include='*.yml' --exclude-dir=.git .
   ```
3. Rekey them. The old password comes from the vault client, and the new one from a prompt, where you paste it from the password manager:
   ```bash
   ansible-vault rekey --vault-id <vault-id>@scripts/vault-client.py \
     --new-vault-id <vault-id>@prompt <file> ...
   ```
   Inline `!vault` values are not handled by `rekey`: decrypt and re-encrypt each with `ansible-vault encrypt_string`.
4. Replace the vault password file. `--set` refuses while the old file exists, so remove it first:
   ```bash
   rm ~/.config/uc-controller/vault/<vault-id>
   python3 scripts/vault-client.py --set --vault-id <vault-id>
   ```
5. View one rekeyed file to prove it opens with the new password, and for `raw_batch` run `python3 scripts/new_raw_batch.py --list`. `python3 tests/run_tests.py` does not test this: the tests use a temporary vault of their own.
6. Commit, then delete the old entry from your password manager.

Older commits still hold files encrypted with the old password. That is acceptable only because the old password is retired and never reused.

## Rules

- Vault passwords live in the password manager and their mode `600` vault files only, never in the repo, a shell history, a note or a chat.
- A batch password is never a vault password, and never a password used anywhere else.
- Only paste a password into the prompt that asks for that exact password.
- Never print a password where a Claude Code session or a log can see it. Ask sessions for commands, not values.
- Run `clear` after viewing any secret.

## If a secret is exposed

| What was exposed | Do this |
| --- | --- |
| A batch password | Retire the batch with `--force`, create a new batch, and set the new password on every node in the old batch |
| The `raw_batch` vault password | Change it as above, then treat every batch as exposed: retire and replace them all |
| The `node` vault password | Change it as above, and replace every secret it encrypted |
| A batch holds a vault password | Change that vault password first, then replace the batch |

## Open items

- Decide whether to rename the `raw_batch` vault ID to something that cannot be mistaken for a batch. Vault IDs may use lower-case letters, digits and underscores, so `batch_store` works but `batch-store` does not. Each encrypted file names its vault ID in its first line, so a rename means rekeying every batch file to the new ID, and changing `ansible.cfg`, `vault-client.py` and `new_raw_batch.py`.
- Record the outcome of the investigation into how batch `raw-2026-11-17-manual` came to hold the vault password.
- The layout and tool for node secrets, from the onboarding kickoff (see The node vault).
