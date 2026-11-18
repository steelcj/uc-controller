---
title: "Batch passwords with plain Ansible Vault"
date: 2026-11-18
author: "Christopher Steel"
status: "Draft, for testing"
description: "How to keep raw node batch passwords in one Ansible Vault file, with passphrases made with dice, and how to test the result against a node before the repository is changed to use it."
---

# Batch passwords with plain Ansible Vault

A raw node is built with a batch password: the password of the `initial` user, shared by every node of one build batch. The raw node contract makes the controller hold it, and gives the producer only its hash <a id="cite-steel-2026b"></a>[(Steel, 2026b)](#ref-steel-2026b).

This document keeps those passwords with standard Ansible Vault and nothing else:
- one encrypted variables file;
- one vault password in a file outside the repository;
- passphrases you make yourself with dice.

It replaces `vault-client.py`, `new_raw_batch.py` and `secrets/raw-batches/`, once it has been tested.

Every step here can be tested by hand before the repository changes. The last section lists what the code change will then do.

## Contents

- [The two secrets](#the-two-secrets)
- [Before you start](#before-you-start)
- [1. Make the passphrases with dice](#1-make-the-passphrases-with-dice)
- [2. Store the vault passphrase](#2-store-the-vault-passphrase)
- [3. Create the encrypted batch file](#3-create-the-encrypted-batch-file)
- [4. Check the file](#4-check-the-file)
- [5. Make the hash for uc-ventoy](#5-make-the-hash-for-uc-ventoy)
- [6. Set the batch passphrase on an existing node](#6-set-the-batch-passphrase-on-an-existing-node)
- [7. Test become from the controller](#7-test-become-from-the-controller)
- [Add, view and retire batches](#add-view-and-retire-batches)
- [Change the vault passphrase](#change-the-vault-passphrase)
- [Node secrets, later](#node-secrets-later)
- [What the code change will do](#what-the-code-change-will-do)
- [Rules](#rules)
- [References](#references)

## The two secrets

| Secret | Protects | Lives in | Used by |
| --- | --- | --- | --- |
| Vault passphrase, vault ID `batches` | The encrypted batch file | `~/.config/uc-controller/vault/batches` (mode `600`) and the password manager | Ansible, to decrypt the file |
| Batch passphrase, one per batch | The `initial` user on every node of that batch | Inside the encrypted batch file, and the password manager | Ansible, as the become password |

They are never the same, and they never go into each other's prompts. A vault ID is a label on an encrypted file that tells Ansible which vault password opens it <a id="cite-ansible-c"></a>[(Ansible project contributors, n.d.-c)](#ref-ansible-c). Its first line names it, as in `$ANSIBLE_VAULT;1.2;AES256;batches`. The name `batches` is chosen so it cannot be mistaken for a batch.

## Before you start

- Work from the root of the uc-controller repository, with the Ansible virtual environment active:

  ```bash
  cd ~/areas/development/uc-controller
  source ~/.venvs/ansible/current/bin/activate
  which ansible-vault openssl
  ```

- The examples use batch `raw-2026-11-18-01`. Any ID of the form `raw-YYYY-MM-DD-<suffix>` works.
- Everything in steps 1 to 7 works on `main`, with no script from the feature branches. The commands name the vault ID and the password file themselves, so `ansible.cfg` does not need to change for the test.
- Do not paste any passphrase into a chat or a Claude Code session, and do not run these commands with the `!` prefix in Claude Code: the output would enter the conversation.

## 1. Make the passphrases with dice

Make two passphrases: one for the vault, and one for the batch.

1. Use the EFF large wordlist. Roll five dice for each word and look the number up in the list. Six words give about 77 bits of entropy <a id="cite-bonneau-2016"></a>[(Bonneau, 2016)](#ref-bonneau-2016).
2. Separate the words with single spaces.
3. Add a number at the end, from one more roll. The privileged access policy asks for privileged passwords that are generated and contain letters and digits (PA-PWD-01) <a id="cite-steel-2026a"></a>[(Steel, 2026a)](#ref-steel-2026a). The contract asks for at least 15 characters (RN-ACC-08), which six words always exceed.
4. Avoid the characters `"` and `\`. The batch passphrase is written inside double quotes in YAML. EFF words contain only lower-case letters and hyphens.
5. Save each passphrase in the password manager straight away:

```bash
dev vault batches # passphrase for vault
dev batch raw-2026-11-18-01     # passphrase for batch
```

- `uc-controller batch raw-2026-11-18-01`

NIST recommends long passphrases over composition rules, and does not require periodic changes <a id="cite-nist-2025"></a>[(National Institute of Standards and Technology [NIST], 2025)](#ref-nist-2025).

Example of the form only. Do not use it:

```text
tannery unbiased pebble canopy mullets gutter 4
```

## 2. Store the vault passphrase

Write the vault passphrase to its file without showing it. It is read with a hidden prompt, inside a subshell, so it is not left in a shell variable or the history:

```bash
mkdir -p ~/.config/uc-controller/vault
chmod 700 ~/.config/uc-controller/vault
(umask 077; read -rsp 'Vault passphrase: ' p && printf '%s\n' "$p" > ~/.config/uc-controller/vault/batches; echo)
stat -c '%a %n' ~/.config/uc-controller/vault/batches
```

Output:

```text
Vault passphrase:
600 /home/initial/.config/uc-controller/vault/batches
```

Paste the passphrase from the password manager at the prompt. Ansible reads a vault password from a plain file like this one, as long as the file is not executable. An executable file is run as a script instead <a id="cite-ansible-c2"></a>[(Ansible project contributors, n.d.-c)](#ref-ansible-c).

## 3. Create the encrypted batch file

```bash
mkdir -p inventories/raw/group_vars/admitted
ansible-vault create \
  --vault-id batches@~/.config/uc-controller/vault/batches \
  --encrypt-vault-id batches \
  inventories/raw/group_vars/admitted/vault.yml
```

`ansible-vault create` opens your editor (`$EDITOR`, or `vi`) on an empty file <a id="cite-ansible-a"></a>[(Ansible project contributors, n.d.-a)](#ref-ansible-a). Type the following, pasting the batch passphrase from the password manager, then save and quit:

```yaml
vault_raw_batch_passwords:
  raw-2026-11-18-01: "tannery unbiased pebble canopy mullets gutter 4"
```

The file is encrypted as a whole when the editor closes. While it is open, `ansible-vault` keeps the plain text only in a temporary file, which it deletes afterwards. The variable name starts with `vault_` by convention, so it is clear where it comes from <a id="cite-ansible-b"></a>[(Ansible project contributors, n.d.-b)](#ref-ansible-b).

## 4. Check the file

```bash
head -1 inventories/raw/group_vars/admitted/vault.yml
```

Output:

```text
$ANSIBLE_VAULT;1.2;AES256;batches
```

To list the batch IDs without showing any passphrase:

```bash
ansible-vault view --vault-id batches@~/.config/uc-controller/vault/batches \
  inventories/raw/group_vars/admitted/vault.yml | sed -n 's/^  \([^:]*\):.*/\1/p'
```

Output:

```text
raw-2026-11-18-01
```

## 5. Make the hash for uc-ventoy

```bash
openssl passwd -6
```

It asks for the password without echoing it. Paste the batch passphrase. It prints a SHA-512 crypt hash <a id="cite-openssl-nd"></a>[(OpenSSL Project, n.d.)](#ref-openssl-nd):

```text
Password:
$6$<salt>$<hash>
```

Put it, with the batch ID, into uc-ventoy's `raw-node-input.yml`:

```yaml
initial_password_hash: "$6$<salt>$<hash>"
password_batch: "raw-2026-11-18-01"
```

Do not use `openssl passwd -6 -stdin` for this: it hashes every line it reads, so a password entered twice gives two hashes. Every run gives a new salt and a different hash. All of them are valid for the same passphrase.

## 6. Set the batch passphrase on an existing node

For a node that was built with another password, such as the uc-ventoy node at 192.168.1.109. Its SSH accepts keys only, so log in with the controller key:

```bash
ssh -i ~/.ssh/gradus-raw-initial-id_ed25519 -o IdentitiesOnly=yes initial@192.168.1.109
passwd
sudo -k && sudo -v
exit
```

- At `passwd`, give the node's current password, then paste the batch passphrase twice.
- At `sudo -v`, paste the batch passphrase again. It must be accepted.

Run `clear` afterwards, and clear the clipboard if your password manager does not.

## 7. Test become from the controller

This is the test that matters. Ansible decrypts the file, picks the batch's passphrase, connects as `initial`, and becomes root with it:

activate controller:

```bash
. ~/.venvs/ansible/current/bin/activate
```

then

```bash
ansible all -i 192.168.1.109, -u initial \
  --private-key ~/.ssh/gradus-raw-initial-id_ed25519 \
  --ssh-common-args='-o IdentitiesOnly=yes' \
  --vault-id batches@~/.config/uc-controller/vault/batches \
  -e @inventories/raw/group_vars/admitted/vault.yml \
  -e 'ansible_become_password={{ vault_raw_batch_passwords["raw-2026-11-18-01"] }}' \
  --become -m ansible.builtin.raw -a 'id -u'
```

Output:

I got this:

```bash
192.168.1.109 | CHANGED | rc=0 >>

0
Shared connection to 192.168.1.109 closed.
```

this was written:

```text
192.168.1.109 | CHANGED | rc=0 >>
0
```

`0` is root's user ID, so become worked. Some likely errors:

- **`Decryption failed`:** the vault passphrase file does not match the one the file was created with.
- **`Incorrect sudo password`:** the passphrase on the node is not the one in the file.
- **`Permission denied (publickey)`:** the key or the user is wrong.

On `main`, `ansible.cfg` still turns host key checking off. The admission work adds strict checking against `ssh/known_hosts`.

## Add, view and retire batches

**Add a batch.** Make its passphrase with dice, as in step 1, then add one line:

```bash
ansible-vault edit --vault-id batches@~/.config/uc-controller/vault/batches \
  inventories/raw/group_vars/admitted/vault.yml
```

```yaml
vault_raw_batch_passwords:
  raw-2026-11-18-01: "..."
  raw-2026-12-02-01: "..."
```

**View the file.** `ansible-vault view` prints every passphrase in plain text. Run `clear` afterwards.

```bash
ansible-vault view --vault-id batches@~/.config/uc-controller/vault/batches \
  inventories/raw/group_vars/admitted/vault.yml
```

**Retire a batch.** First check that no host still uses it, then delete its line with `ansible-vault edit`:

```bash
grep -rn 'raw_node_batch: *raw-2026-11-18-01' inventories/
```

No output means no host names it. Git history keeps the old encrypted file, so a retired passphrase is never used again.

## Change the vault passphrase

Do this on a schedule you choose, and at once if the vault passphrase was exposed.

1. Make a new passphrase with dice, and save it in the password manager as a new entry. Keep the old entry until step 4 passes.
2. Re-encrypt the file. The old passphrase comes from its file, and the new one from a prompt <a id="cite-ansible-a2"></a>[(Ansible project contributors, n.d.-a)](#ref-ansible-a):

   ```bash
   ansible-vault rekey \
     --vault-id batches@~/.config/uc-controller/vault/batches \
     --new-vault-id batches@prompt \
     inventories/raw/group_vars/admitted/vault.yml
   ```

3. Replace the passphrase file, as in step 2 of the setup.
4. Run step 4 (list the batch IDs) to prove the file opens.
5. Commit the file, then delete the old entry from the password manager.

## Node secrets, later

Secrets of one node, such as the password onboarding will give each node in place of the batch passphrase, follow the same pattern with their own vault ID, `node`, and their own passphrase file, `~/.config/uc-controller/vault/node`. Nothing needs them yet. The onboarding work will say where their file lives.

## What the code change will do

Once steps 1 to 7 work, the repository changes to match. None of this is done yet:

- **`ansible.cfg`:** names the passphrase file, so the commands no longer need `--vault-id`:

  ```ini
  vault_identity_list = batches@~/.config/uc-controller/vault/batches
  ```

  Every Ansible run then needs that file. An operator without it gets an error on every run, even on runs that decrypt nothing.
- **`inventories/raw/group_vars/admitted/main.yml`**, renamed from `admitted.yml`, sets:

  ```yaml
  ansible_become_password: "{{ vault_raw_batch_passwords[raw_node_batch] }}"
  ```
- **The admission playbook:**
  - takes the batch from `-e admit_batch_id=...`, since there is no index of current batches;
  - checks that the batch is in the file;
  - reports RN-ACC-08 when its passphrase is shorter than 15 characters, by measuring it rather than reading a recorded value.
- **Removed:**
  - `scripts/vault-client.py`, `scripts/new_raw_batch.py`, `scripts/sha512_crypt.py` and their tests;
  - `secrets/raw-batches/`;
  - the `secrets/` rules in `.gitignore`;
  - the old password files `~/.config/uc-controller/vault/raw_batch` and `node`, which the scripts made.
- **Documents:** the design document's Secrets section and `en/docs/guides/vault-guide.md` change to describe this file.

## Rules

- A passphrase is made with dice, never chosen, and never used for anything else.
- The vault passphrase lives only in the password manager and its mode `600` file. A batch passphrase lives only in the password manager and the encrypted file.
- Paste a passphrase only into the prompt that asks for that exact passphrase.
- Never show a passphrase where a Claude Code session or a log can see it. Run `clear` after viewing one.

## References

<a id="ref-ansible-a"></a>
Ansible project contributors. (n.d.-a). *ansible-vault*. Ansible Community Documentation. Retrieved November 18, 2026, from https://docs.ansible.com/projects/ansible/latest/cli/ansible-vault.html
[Return to first citation](#cite-ansible-a) · [Return to second citation](#cite-ansible-a2)

<a id="ref-ansible-b"></a>
Ansible project contributors. (n.d.-b). *Encrypting content with Ansible Vault*. Ansible Community Documentation. Retrieved November 18, 2026, from https://docs.ansible.com/projects/ansible/latest/vault_guide/vault_encrypting_content.html
[Return to citation](#cite-ansible-b)

<a id="ref-ansible-c"></a>
Ansible project contributors. (n.d.-c). *Managing vault passwords*. Ansible Community Documentation. Retrieved November 18, 2026, from https://docs.ansible.com/projects/ansible/latest/vault_guide/vault_managing_passwords.html
[Return to first citation](#cite-ansible-c) · [Return to second citation](#cite-ansible-c2)

<a id="ref-bonneau-2016"></a>
Bonneau, J. (2016, July 19). *Deep dive: EFF's new wordlists for random passphrases*. Electronic Frontier Foundation. https://www.eff.org/deeplinks/2016/07/new-wordlists-random-passphrases
[Return to citation](#cite-bonneau-2016)

<a id="ref-nist-2025"></a>
National Institute of Standards and Technology. (2025). *Digital identity guidelines: Authentication and authenticator management* (NIST Special Publication 800-63B-4). https://pages.nist.gov/800-63-4/sp800-63b/authenticators
[Return to citation](#cite-nist-2025)

<a id="ref-openssl-nd"></a>
OpenSSL Project. (n.d.). *openssl-passwd* (OpenSSL 3.0 manual). Retrieved November 18, 2026, from https://docs.openssl.org/3.0/man1/openssl-passwd/
[Return to citation](#cite-openssl-nd)

<a id="ref-steel-2026a"></a>
Steel, C. (2026a). *Privileged access policy* (Version 0.1.0) [Draft]. uc-contracts. https://github.com/steelcj/uc-contracts/blob/main/en/docs/node-policies/privileged-access/uc-privileged-access-policy.md
[Return to citation](#cite-steel-2026a)

<a id="ref-steel-2026b"></a>
Steel, C. (2026b). *Raw node contract* (Version 0.3.1) [Draft]. uc-contracts. https://github.com/steelcj/uc-contracts/blob/main/en/docs/node-onboarding-pipeline/1-raw-node-egress/uc-raw-node-contract.md
[Return to citation](#cite-steel-2026b)
