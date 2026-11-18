---
title: "Admitting a raw node"
date: 2026-11-18
author: "Christopher Steel"
status: "Guide"
description: "How an operator admits raw nodes that meet the raw node contract into uc-controller's raw inventory: reading each node's address and host key fingerprint at its console, listing them in a candidates file, running the admission playbook, and reading its report. Scanning a subnet is described second, with its limits."
---

# Admitting a raw node

## Abstract

A raw node built to the raw node contract, by uc-ventoy for example, refuses root over SSH, asks for a password for sudo, and reports itself in `/var/lib/raw-node/confirmation.yml`. Admission takes such a node into uc-controller's raw inventory, as the `admitted` source, after checking its confirmation against the contract, its host keys and its identity. The operator supplies each node's address and the fingerprint of its host key, both read at the node's console, so that the controller trusts a key it has confirmed out of band. This guide covers that path, reading the admission report, what to do when a node is refused or stopped, and, second, finding candidates by scanning a subnet. Admission changes nothing on a node. Onboarding admitted nodes comes in a later kickoff.

## Sources and acknowledgements

Admission implements the ingress side of the raw node contract <a name="apa-steel-raw-node-contract-citation"></a>([Steel, 2026b](#apa-steel-raw-node-contract-reference)), and applies the privileged access policy's host key clauses, PA-HOST-01 and PA-HOST-02, from the first connection <a name="apa-steel-privileged-access-citation"></a>([Steel, 2026a](#apa-steel-privileged-access-reference)). The design is described in the Admission section of `en/docs/uc-controller-v0.1.7.md`. Batch passphrases are described in `en/docs/guides/vault-guide.md`.

## Contents

- [What admission checks](#what-admission-checks)
- [Before you start](#before-you-start)
- [Read the address and fingerprint at the console](#read-the-address-and-fingerprint-at-the-console)
- [Write the candidates file](#write-the-candidates-file)
- [Admit](#admit)
- [Read the report](#read-the-report)
- [After admission](#after-admission)
- [When a node is refused or stopped](#when-a-node-is-refused-or-stopped)
- [Admitting a single node](#admitting-a-single-node)
- [Finding candidates by scanning](#finding-candidates-by-scanning)
- [Resources](#resources)
- [References](#references)
- [Changelog](#changelog)

## What admission checks

For each candidate address, `ingress/playbooks/05_admit.yml`, on the controller:

1. Fetches the node's SSH host keys with `ssh-keyscan`, into a temporary file.
2. Connects as `initial` with the controller's key, trusting only those keys, and reads the confirmation with `cat`.
3. Checks the confirmation against the contract with `scripts/check_raw_confirmation.py`.
4. Requires the host keys listed in the confirmation to equal the keys the node presented, and the fingerprint you read at the console to be one of them.
5. Matches the node's hostname, `machine_id` and MAC addresses against every stage inventory. A node already known must still present exactly the keys recorded in `ssh/known_hosts`.
6. Writes a new node into `inventories/raw/admitted.yml`, adds its keys to `ssh/known_hosts`, then confirms a connection as `initial` and a become with the batch passphrase, both with strict host key checking. If that confirmation fails, the admission is undone.

## Before you start

- Work from the root of the uc-controller repository, with the Ansible virtual environment active (`source ~/.venvs/ansible/current/bin/activate`).
- The vault passphrase file `~/.config/uc-controller/vault/batches` is in place, and the batch the nodes were built with is in `inventories/raw/group_vars/admitted/vault.yml`. See `en/docs/guides/vault-guide.md`.
- The controller's key for `initial` is the one the onboard inventory names, `onboard_ssh_private_key_file` in `inventories/onboard/dev/group_vars/all.yml`. Its public key is the one uc-ventoy put on the nodes.
- The nodes are built, booted, and on a network the controller can reach on their SSH port.

## Read the address and fingerprint at the console

At each node's console, log in as `initial` with the batch passphrase and run:

```bash
hostnamectl --static
ip -br -4 addr show scope global
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
grep RAW_NODE_PASSWORD_BATCH /etc/raw-node/raw-node.conf
```

Output example:

```text
deb13-vt-55b1
enp2s0           UP             192.168.1.109/24
256 SHA256:HqHMMtM3O24uFujNDULW4A+N8E5LZomUmycBhbnRnxE root@deb13-vt-55b1 (ED25519)
RAW_NODE_PASSWORD_BATCH="raw-2026-11-18-01"
```

Write down the address, the fingerprint (from `SHA256:` to the next space) and the batch. Reading the fingerprint here, rather than over the network, is what lets the controller trust the key on the strength of something other than the connection it is checking.

## Write the candidates file

List every node to admit, each with its own fingerprint. Keep the file outside the repository: it is a working note for one admission, not configuration.

```yaml
# ~/uc-candidates.yml
admit_candidates:
  - address: 192.168.1.109
    fingerprint: SHA256:HqHMMtM3O24uFujNDULW4A+N8E5LZomUmycBhbnRnxE
  - address: 192.168.1.112
    fingerprint: SHA256:...
```

Every entry needs both an address and a fingerprint, and no address may appear twice. A wrong entry stops the run before any node is contacted. The fingerprint may be of any of the node's host keys; ED25519 is the one shown above.

## Admit

Name the batch the nodes were built with. There is no default:

```bash
ansible-playbook -i inventories/raw -i inventories/onboard/dev \
  ingress/playbooks/05_admit.yml \
  -e admit_batch_id=raw-2026-11-18-01 \
  -e @$HOME/uc-candidates.yml
```

The onboard inventory is loaded only for `onboard_ssh_private_key_file`. The candidates must all have been built with the named batch. Admit nodes of different batches in separate runs.

## Read the report

The play ends with one line per candidate:

```text
192.168.1.109: admitted deb13-vt-55b1 - deb13-vt-55b1 is new on every count
```

| Outcome | Means | Written | Exit status |
| --- | --- | --- | --- |
| `admitted` | New, meets the contract, keys confirmed, connection and become confirmed | `admitted.yml` and `ssh/known_hosts` | 0 |
| `known` | Already in an inventory with this `machine_id`, and its keys match `ssh/known_hosts` | Nothing | 0 |
| `not-contract` | No SSH server answered, or the controller key or the confirmation was refused | Nothing | 0 |
| `refused` | The confirmation breaks the contract, the keys differ from the confirmation, from the console fingerprint or, for a known node, from `ssh/known_hosts` | Nothing | 2 |
| `stopped` | A reinstall, a name collision, or a node known under another name | Nothing | 2 |

The exit status is 2 after the report when any candidate was refused or stopped, or when an admission could not be confirmed. Each of those needs you. Other candidates in the same run are still admitted.

The report also carries warnings that do not stop admission:
- `PA-HOST-01 host key trusted on first use` appears when no console fingerprint was given for a node being admitted.
- `RN-ACC-08` appears when the batch passphrase is under 15 characters.
- `Firewall firewall_active` appears when the node reports its firewall manager as stopped.

## After admission

Check the new entry and the trusted keys, then commit the keys. `admitted.yml` is generated and not committed. `ssh/known_hosts` is committed, so that git history records when each node's keys were trusted.

```bash
sed -n '/^admitted:/,$p' inventories/raw/admitted.yml
git diff ssh/known_hosts
ssh-keygen -lf ssh/known_hosts
git add ssh/known_hosts
git commit -m "ssh/known_hosts: trust deb13-vt-55b1, admitted by 05_admit.yml"
```

Each admitted host carries `ansible_host`, `ansible_port`, `raw_node_contract`, `raw_node_baseline`, `raw_node_machine_id`, `raw_node_macs`, `raw_node_batch` and `raw_node_admitted`.

The node can now be reached as an inventory host, with strict host key checking against `ssh/known_hosts` only:

```bash
ansible -i inventories/raw -i inventories/onboard/dev deb13-vt-55b1 \
  -m ansible.builtin.raw -a 'id -un' -e ansible_become=false
```

Running admission again with the same candidates reports each node as `known` and changes nothing.

## When a node is refused or stopped

| Report says | Likely cause | What to do |
| --- | --- | --- |
| `Versioning contract ... is not supported` | The node was built to another contract version | Rebuild it with a producer baseline for contract 0.3.0 or 0.3.1 |
| A clause such as `RN-ACC-07 sudo_nopasswd` | The node does not meet that clause | Fix the producer and rebuild |
| `host keys differ: presented ...; confirmation lists ...` | The confirmation is stale, or another machine answered at that address | Check the address and the node at its console |
| `the console fingerprint ... is not among the host keys` | A typing error, or another machine answered at that address | Read the fingerprint again at the console |
| `host keys differ from ssh/known_hosts for ...` | A known node presents other keys than when it was admitted | Find out why at the console before anything else. If the change is expected, follow the re-admission steps below |
| `reinstall` | Same hostname and MAC address, new `machine_id` | Follow the re-admission steps below |
| `collision` | Another node already has this hostname | Rename one of them |
| `conflict` | The `machine_id` or a MAC address is known under another name | Resolve the other inventory entry first |
| `Batch ... is not in inventories/raw/group_vars/admitted/vault.yml` | The batch named is not in the batch file | Check the batch at the console, or add it, see the vault guide |

To admit again a node that was reinstalled, or whose keys changed on purpose:

1. Read the new fingerprint at the console.
2. Remove the node's entry: from `inventories/raw/admitted.yml` if it is still raw, or with `python3 scripts/demote_node.py --from inventories/onboard/dev --to inventories/raw --host <host>` if it was promoted. The `reinstall` message names the right command.
3. Remove its old keys with `ssh-keygen -R <host> -f ssh/known_hosts`, and commit `ssh/known_hosts`, so that history records the change (PA-HOST-02).
4. Admit it again with its new fingerprint.

## Admitting a single node

For one node, the address and fingerprint can be given on the command line instead of in a file:

```bash
ansible-playbook -i inventories/raw -i inventories/onboard/dev \
  ingress/playbooks/05_admit.yml -e admit_batch_id=raw-2026-11-18-01 \
  -e admit_addresses=192.168.1.109 \
  -e admit_expected_fingerprint=SHA256:HqHMMtM3O24uFujNDULW4A+N8E5LZomUmycBhbnRnxE
```

`admit_expected_fingerprint` applies to one address only. `admit_addresses` also takes several addresses, comma-separated, but without fingerprints every node is trusted on first use. Use a candidates file instead.

## Finding candidates by scanning

When you do not know the addresses, the controller can scan a subnet and offer every host it finds:

```bash
ansible-playbook ingress/playbooks/00_discover.yml -e discover_subnet=192.168.1.0/24
ansible-playbook -i inventories/raw -i inventories/onboard/dev \
  ingress/playbooks/05_admit.yml -e admit_batch_id=raw-2026-11-18-01 \
  -e admit_from_discovered=true
```

Limits:

- **No console fingerprint.** Every node found by a scan is trusted on first use, and the report says so. Compare its fingerprints with the console afterwards (`ssh-keygen -lf ssh/known_hosts`), before you rely on it.
- **The probe is SSH only.** The scan runs `nmap -sn -PS22`, a TCP probe on the SSH port, so a contract node, whose firewall drops everything else, is found. A node whose SSH listens on another port needs `-e discover_ssh_port=<port>`. A node whose firewall admits SSH only from addresses other than the controller's is not found.
- **Hosts with port 22 closed appear too.** A host that answers the probe with a reset is listed as up. Admission reports it as `not-contract`, and the run still exits 0.
- **It touches every host on the subnet.** It probes every address and tries SSH as `initial` on every host it finds. Scan only networks you are responsible for, and prefer a narrow range, down to a single address (`192.168.1.109/32`).
- **Without root, nmap's default probes miss contract nodes.** That is why the SSH probe is set explicitly: the default probes only ports 80 and 443, which a contract node drops.

A node that announces itself to the controller, a phone-home, is proposed for a later kickoff as the replacement for scanning.

## Resources

### Contracts and policy

- [Raw node contract](#apa-steel-raw-node-contract-reference)
- [Privileged access policy](#apa-steel-privileged-access-reference)

## References

<a name="apa-steel-privileged-access-reference"></a>Steel, C. (2026a). *Privileged access policy* (Version 0.1.0) [Draft]. uc-contracts. https://github.com/steelcj/uc-contracts/blob/main/en/docs/node-policies/privileged-access/uc-privileged-access-policy.md
[Return to citation](#apa-steel-privileged-access-citation)

<a name="apa-steel-raw-node-contract-reference"></a>Steel, C. (2026b). *Raw node contract* (Version 0.3.1) [Draft]. uc-contracts. https://github.com/steelcj/uc-contracts/blob/main/en/docs/node-onboarding-pipeline/1-raw-node-egress/uc-raw-node-contract.md
[Return to citation](#apa-steel-raw-node-contract-citation)

## Changelog

| Date | Notes |
| --- | --- |
| 2026-11-18 | First version, from the raw node admission kickoff |
