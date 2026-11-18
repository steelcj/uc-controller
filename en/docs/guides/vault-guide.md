---
title: "uc-controller Vault Guide"
date: 2026-11-18
author: "Christopher Steel"
status: "Guide"
description: "How to keep raw node batch passphrases in one Ansible Vault file, with passphrases made with dice: setting up, adding batches, building and admitting nodes, retiring batches and changing the vault passphrase."
---

# uc-controller Vault Guide

## Abstract

A raw node is built with a batch passphrase: the password of the `initial` user, shared by every node of one build batch. uc-controller keeps these passphrases with standard Ansible Vault and nothing else: one encrypted variables file, one vault passphrase in a file outside the repository, and passphrases the operator makes with dice. This guide covers setting up the vault passphrase, adding a batch, making the hash for uc-ventoy, admitting nodes, viewing, retiring and changing passphrases, and what to do when a secret is exposed. The design is described in the Secrets section of `en/docs/uc-controller-v0.1.7.md`.

## Sources and acknowledgements

The raw node contract makes the controller hold the batch passphrase and gives the producer only its hash <a name="apa-steel-raw-node-contract-citation"></a>([Steel, 2026b](#apa-steel-raw-node-contract-reference)). The privileged access policy sets the rules for generating it <a name="apa-steel-privileged-access-citation"></a>([Steel, 2026a](#apa-steel-privileged-access-reference)). The Ansible commands follow the Ansible Vault documentation, and the passphrase method follows the EFF wordlists and NIST SP 800-63B-4, each cited where it is used.

## Contents

- [The two secrets](#the-two-secrets)
- [Where things are](#where-things-are)
- [Before you start](#before-you-start)
- [Make passphrases with dice](#make-passphrases-with-dice)
- [Store the vault passphrase](#store-the-vault-passphrase)
- [Create the batch file](#create-the-batch-file)
- [Check the batch file](#check-the-batch-file)
- [Make the hash for uc-ventoy](#make-the-hash-for-uc-ventoy)
- [Admit the nodes](#admit-the-nodes)
- [Set a batch passphrase on an existing node](#set-a-batch-passphrase-on-an-existing-node)
- [Test become by hand](#test-become-by-hand)
- [Add, view and retire batches](#add-view-and-retire-batches)
- [Change the vault passphrase](#change-the-vault-passphrase)
- [Node secrets, later](#node-secrets-later)
- [Troubleshooting](#troubleshooting)
- [Rules](#rules)
- [If a secret is exposed](#if-a-secret-is-exposed)
- [Resources](#resources)
- [References](#references)
- [Changelog](#changelog)

## The two secrets

| Secret | Protects | Lives in | Used by |
| --- | --- | --- | --- |
| Vault passphrase, vault ID `batches` | The encrypted batch file | `~/.config/uc-controller/vault/batches` (mode `600`) and the password manager | Ansible, to decrypt the file |
| Batch passphrase, one per batch | The `initial` user on every node of that batch | Inside the encrypted batch file, and the password manager | Ansible, as the become password |

They are never the same, and they never go into each other's prompts. A vault ID is a label on an encrypted file that tells Ansible which vault password opens it <a name="apa-ansible-vault-passwords-citation"></a>([Ansible project contributors, n.d.-c](#apa-ansible-vault-passwords-reference)). The file's first line names it, as in `$ANSIBLE_VAULT;1.2;AES256;batches`.

## Where things are

| Item | Location | Notes |
| --- | --- | --- |
| Batch file | `inventories/raw/group_vars/admitted/vault.yml` | Encrypted as a whole, committed. Holds `vault_raw_batch_passwords`, one entry per batch ID |
| Vault passphrase file | `~/.config/uc-controller/vault/batches` | Mode `600`, never in the repository |
| Where Ansible finds it | `vault_identity_list = batches@~/.config/uc-controller/vault/batches` in `ansible.cfg` | Every Ansible run reads it, so every operator needs the file |
| Become password | `inventories/raw/group_vars/admitted/main.yml` | `ansible_become_password: "{{ vault_raw_batch_passwords[raw_node_batch] }}"` |
| Trusted host keys | `ssh/known_hosts` | Public keys, committed, keyed by hostname |

## Before you start

Work from the root of the uc-controller repository, with the Ansible virtual environment active:

```bash
cd ~/areas/development/uc-controller
source ~/.venvs/ansible/current/bin/activate
which ansible-vault openssl
```

Batch IDs have the form `raw-YYYY-MM-DD-NN`, such as `raw-2026-11-18-01`.

Do not paste any passphrase into a chat or a Claude Code session, and do not run these commands with the `!` prefix in Claude Code: the output would enter the conversation.

## Make passphrases with dice

Make one passphrase for the vault, once, and one for each batch.

1. Use the EFF large wordlist. Roll five dice for each word and look the number up in the list. Six words give about 77 bits of entropy <a name="apa-bonneau-2016-citation"></a>([Bonneau, 2016](#apa-bonneau-2016-reference)).
2. Separate the words with single spaces.
3. Add a number at the end, from one more roll. The privileged access policy asks for privileged passwords that are generated and contain letters and digits (PA-PWD-01) <a name="apa-steel-privileged-access-citation-2"></a>([Steel, 2026a](#apa-steel-privileged-access-reference)). The contract asks for at least 15 characters (RN-ACC-08), which six words always exceed.
4. Avoid the characters `"` and `\`. The batch passphrase is written inside double quotes in YAML. EFF words contain only lower-case letters and hyphens.
5. Save each passphrase in the password manager straight away, as `uc-controller vault batches` and `uc-controller batch raw-2026-11-18-01`.

NIST recommends long passphrases over composition rules, and does not require periodic changes <a name="apa-nist-800-63b-citation"></a>([National Institute of Standards and Technology [NIST], 2025](#apa-nist-800-63b-reference)).

An example of the form only. Do not use it:

```text
tannery unbiased pebble canopy mullets gutter 4
```

## Store the vault passphrase

Once per operator and workstation. The passphrase is read with a hidden prompt, inside a subshell, so it is not left in a shell variable or the history:

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

Paste the vault passphrase from the password manager at the prompt. Ansible reads a vault password from a plain file like this one, as long as the file is not executable. An executable file is run as a script instead <a name="apa-ansible-vault-passwords-citation-2"></a>([Ansible project contributors, n.d.-c](#apa-ansible-vault-passwords-reference)).

## Create the batch file

Only when the repository has no `inventories/raw/group_vars/admitted/vault.yml` yet. Otherwise add the batch to the existing file, as in [Add, view and retire batches](#add-view-and-retire-batches).

```bash
ansible-vault create --encrypt-vault-id batches inventories/raw/group_vars/admitted/vault.yml
```

`ansible-vault create` opens your editor (`$EDITOR`, or `vi`) on an empty file <a name="apa-ansible-vault-cli-citation"></a>([Ansible project contributors, n.d.-a](#apa-ansible-vault-cli-reference)). Type the following, pasting the batch passphrase from the password manager, then save and quit:

```yaml
vault_raw_batch_passwords:
  raw-2026-11-18-01: "tannery unbiased pebble canopy mullets gutter 4"
```

The file is encrypted as a whole when the editor closes. While it is open, `ansible-vault` keeps the plain text only in a temporary file, which it deletes afterwards. The variable name starts with `vault_` by convention, so it is clear where it comes from <a name="apa-ansible-vault-encrypting-citation"></a>([Ansible project contributors, n.d.-b](#apa-ansible-vault-encrypting-reference)).

Commit the file:

```bash
git add inventories/raw/group_vars/admitted/vault.yml
git commit -m "Add batch raw-2026-11-18-01"
```

## Check the batch file

```bash
head -1 inventories/raw/group_vars/admitted/vault.yml
```

Output:

```text
$ANSIBLE_VAULT;1.2;AES256;batches
```

To list the batch IDs without showing any passphrase:

```bash
ansible-vault view inventories/raw/group_vars/admitted/vault.yml | sed -n 's/^  \([^:]*\):.*/\1/p'
```

Output:

```text
raw-2026-11-18-01
```

## Make the hash for uc-ventoy

```bash
openssl passwd -6
```

It asks for the password without echoing it. Paste the batch passphrase. It prints a SHA-512 crypt hash <a name="apa-openssl-passwd-citation"></a>([OpenSSL Project, n.d.](#apa-openssl-passwd-reference)):

```text
Password:
$6$<salt>$<hash>
```

Put it, with the batch ID, into uc-ventoy's `raw-node-input.yml`, then build the nodes:

```yaml
initial_password_hash: "$6$<salt>$<hash>"
password_batch: "raw-2026-11-18-01"
```

uc-ventoy writes `password_batch` on each node as `RAW_NODE_PASSWORD_BATCH` in `/etc/raw-node/raw-node.conf`, so you can tell at the console which batch a node has.

Do not use `openssl passwd -6 -stdin` for this: it hashes every line it reads, so a password entered twice gives two hashes. Every run gives a new salt and a different hash. All of them are valid for the same passphrase.

## Admit the nodes

Admission is described in `en/docs/admitting-a-raw-node.md`. In short, the operator reads each node's address and host key fingerprint at its console, lists them in a candidates file, and names the batch the nodes were built with:

```bash
ansible-playbook -i inventories/raw -i inventories/onboard/dev \
  ingress/playbooks/05_admit.yml -e admit_batch_id=raw-2026-11-18-01 -e @candidates.yml
```

Admission refuses a batch that is not in the batch file, reports RN-ACC-08 as not met when the batch passphrase is under 15 characters, and records the batch on each node's inventory entry as `raw_node_batch`. From then on, Ansible uses that batch's passphrase as the node's become password.

## Set a batch passphrase on an existing node

For a node built with another password. Its SSH accepts keys only, so log in with the controller key:

```bash
ssh -i ~/.ssh/gradus-raw-initial-id_ed25519 -o IdentitiesOnly=yes initial@192.168.1.109
passwd
sudo -k && sudo -v
exit
```

At `passwd`, give the node's current password, then paste the batch passphrase twice. At `sudo -v`, paste the batch passphrase again. It must be accepted.

Run `clear` afterwards, and clear the clipboard if your password manager does not.

## Test become by hand

This checks a batch passphrase against a node without admitting it. Ansible decrypts the file, picks the batch's passphrase, connects as `initial`, and becomes root:

```bash
ansible all -i 192.168.1.109, -u initial \
  --private-key ~/.ssh/gradus-raw-initial-id_ed25519 \
  --ssh-common-args='-o IdentitiesOnly=yes' \
  -e @inventories/raw/group_vars/admitted/vault.yml \
  -e 'ansible_become_password={{ vault_raw_batch_passwords["raw-2026-11-18-01"] }}' \
  --become -m ansible.builtin.raw -a 'id -u'
```

Output:

```text
192.168.1.109 | CHANGED | rc=0 >>
0
```

`0` is root's user ID, so become worked.

## Add, view and retire batches

### Add a batch

Make its passphrase with dice, then add one line with `ansible-vault edit` and commit:

```bash
ansible-vault edit inventories/raw/group_vars/admitted/vault.yml
```

```yaml
vault_raw_batch_passwords:
  raw-2026-11-18-01: "..."
  raw-2026-12-02-01: "..."
```

### View the file

`ansible-vault view` prints every passphrase in plain text. Run `clear` afterwards.

```bash
ansible-vault view inventories/raw/group_vars/admitted/vault.yml
```

### Retire a batch

First check that no host still uses it, then delete its line with `ansible-vault edit` and commit:

```bash
grep -rn 'raw_node_batch: *raw-2026-11-18-01' inventories/
```

No output means no host names it. Nothing enforces this check, so run it every time. Git history keeps the old encrypted file, so a retired passphrase is never used again.

## Change the vault passphrase

Do this on a schedule you choose, and at once if the vault passphrase was exposed.

1. Make a new passphrase with dice, and save it in the password manager as a new entry. Keep the old entry until the file opens with the new one.
2. Re-encrypt the file. The old passphrase comes from its file, through `ansible.cfg`, and the new one from a prompt <a name="apa-ansible-vault-cli-citation-2"></a>([Ansible project contributors, n.d.-a](#apa-ansible-vault-cli-reference)):

   ```bash
   ansible-vault rekey --new-vault-id batches@prompt inventories/raw/group_vars/admitted/vault.yml
   ```

3. Replace the passphrase file: remove the old one with `rm ~/.config/uc-controller/vault/batches`, then [store the vault passphrase](#store-the-vault-passphrase) again.
4. List the batch IDs, as in [Check the batch file](#check-the-batch-file), to prove the file opens.
5. Commit the file, then delete the old entry from the password manager.

Older commits still hold the file encrypted with the old passphrase. That is acceptable only because the old passphrase is never used again.

## Node secrets, later

Secrets of one node, such as the password onboarding will give each node in place of the batch passphrase, will follow the same pattern with their own vault ID, `node`, and their own passphrase file, `~/.config/uc-controller/vault/node`. Nothing needs them yet. The onboarding work will say where their file lives, and will add `node` to `vault_identity_list`.

## Troubleshooting

| Message | Cause | Fix |
| --- | --- | --- |
| `The vault password file ... batches was not found`, on any Ansible run | No vault passphrase file on this workstation | [Store the vault passphrase](#store-the-vault-passphrase) |
| `Decryption failed` | The passphrase file does not match the one the batch file was encrypted with | Check it against the password manager entry `uc-controller vault batches` |
| `Batch ... is not in inventories/raw/group_vars/admitted/vault.yml` | The `admit_batch_id` given is not in the batch file | [Check the batch file](#check-the-batch-file), or add the batch |
| `Incorrect sudo password` | The passphrase on the node is not the batch's | [Set it on the node](#set-a-batch-passphrase-on-an-existing-node), or admit with the right batch |
| `Permission denied (publickey)` | Wrong key or user | Use `~/.ssh/gradus-raw-initial-id_ed25519` and `initial` |

## Rules

- A passphrase is made with dice, never chosen, and never used for anything else.
- The vault passphrase lives only in the password manager and its mode `600` file. A batch passphrase lives only in the password manager and the encrypted file.
- Paste a passphrase only into the prompt that asks for that exact passphrase.
- Never show a passphrase where a Claude Code session or a log can see it. Run `clear` after viewing one.

## If a secret is exposed

| What was exposed | Do this |
| --- | --- |
| A batch passphrase | Make a new batch, set its passphrase on every node of the old batch, change their `raw_node_batch`, then retire the old batch |
| The vault passphrase | [Change it](#change-the-vault-passphrase), then treat every batch passphrase as exposed |

## Resources

### Contracts and policy

- [Raw node contract](#apa-steel-raw-node-contract-reference)
- [Privileged access policy](#apa-steel-privileged-access-reference)

### Ansible Vault

- [ansible-vault command](#apa-ansible-vault-cli-reference)
- [Encrypting content with Ansible Vault](#apa-ansible-vault-encrypting-reference)
- [Managing vault passwords](#apa-ansible-vault-passwords-reference)

### Passphrases and hashes

- [EFF wordlists for random passphrases](#apa-bonneau-2016-reference)
- [NIST SP 800-63B-4](#apa-nist-800-63b-reference)
- [openssl-passwd](#apa-openssl-passwd-reference)

## References

<a name="apa-ansible-vault-cli-reference"></a>Ansible project contributors. (n.d.-a). *ansible-vault*. Ansible Community Documentation. Retrieved November 18, 2026, from https://docs.ansible.com/projects/ansible/latest/cli/ansible-vault.html
[Return to citation](#apa-ansible-vault-cli-citation)

<a name="apa-ansible-vault-encrypting-reference"></a>Ansible project contributors. (n.d.-b). *Encrypting content with Ansible Vault*. Ansible Community Documentation. Retrieved November 18, 2026, from https://docs.ansible.com/projects/ansible/latest/vault_guide/vault_encrypting_content.html
[Return to citation](#apa-ansible-vault-encrypting-citation)

<a name="apa-ansible-vault-passwords-reference"></a>Ansible project contributors. (n.d.-c). *Managing vault passwords*. Ansible Community Documentation. Retrieved November 18, 2026, from https://docs.ansible.com/projects/ansible/latest/vault_guide/vault_managing_passwords.html
[Return to citation](#apa-ansible-vault-passwords-citation)

<a name="apa-bonneau-2016-reference"></a>Bonneau, J. (2016, July 19). *Deep dive: EFF's new wordlists for random passphrases*. Electronic Frontier Foundation. https://www.eff.org/deeplinks/2016/07/new-wordlists-random-passphrases
[Return to citation](#apa-bonneau-2016-citation)

<a name="apa-nist-800-63b-reference"></a>National Institute of Standards and Technology. (2025). *Digital identity guidelines: Authentication and authenticator management* (NIST Special Publication 800-63B-4). https://pages.nist.gov/800-63-4/sp800-63b/authenticators
[Return to citation](#apa-nist-800-63b-citation)

<a name="apa-openssl-passwd-reference"></a>OpenSSL Project. (n.d.). *openssl-passwd* (OpenSSL 3.0 manual). Retrieved November 18, 2026, from https://docs.openssl.org/3.0/man1/openssl-passwd/
[Return to citation](#apa-openssl-passwd-citation)

<a name="apa-steel-privileged-access-reference"></a>Steel, C. (2026a). *Privileged access policy* (Version 0.1.0) [Draft]. uc-contracts. https://github.com/steelcj/uc-contracts/blob/main/en/docs/node-policies/privileged-access/uc-privileged-access-policy.md
[Return to citation](#apa-steel-privileged-access-citation)

<a name="apa-steel-raw-node-contract-reference"></a>Steel, C. (2026b). *Raw node contract* (Version 0.3.1) [Draft]. uc-contracts. https://github.com/steelcj/uc-contracts/blob/main/en/docs/node-onboarding-pipeline/1-raw-node-egress/uc-raw-node-contract.md
[Return to citation](#apa-steel-raw-node-contract-citation)

## Changelog

| Date | Notes |
| --- | --- |
| 2026-11-18 | Rewritten for plain Ansible Vault, replacing the guide to `vault-client.py` and `new_raw_batch.py`, which were removed. House style applied: no heading numbers, Citation Anchor Pairs, Abstract, Sources and acknowledgements, Resources and Changelog. Admission points to `admitting-a-raw-node.md` and the candidates file |
