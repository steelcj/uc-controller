---
title: Admit and Onboard
description: What uc-controller does with a node after uc-node hands it over: admitting the candidates of one batch from the client inventory's candidates/, the fully qualified name an admitted node takes, admitting a node uc-node did not build, moving a node admitted under its hostname alone, and the Foomuuri fragments each later stage writes.
version: 0.1.0
status: provisional
date: 2026-11-27
language: en-CA
---

# Admit and Onboard

## Abstract

uc-node takes a node from raw to connected securely and hands it over with two records: the confirmation on the node, and a candidate in the client inventory's `candidates/`. uc-node's guide 4, Hand Over to the Fleet, ends there. This guide starts there. Admission, `ingress/playbooks/05_admit.yml`, reads the candidates of one batch, checks each node against the raw node contract and its candidate, and writes it into `raw/admitted.yml` and `ssh/known_hosts` under its fully qualified domain name. The guide then covers nodes uc-node did not build, moving a node admitted before 0.2.0 under its hostname alone, and what the firewall holds after onboarding, normalizing and specializing.

Admitted nodes are not onboarded yet: `10_onboard.yml` onboards nodes it reaches as root, through Incus or a subnet scan, and leaves the `admitted` group out. Onboarding admitted nodes is the next piece of work, and this guide gains a section for it then.

The examples use the client `example-org`, whose inventory is `~/.private/uc/example-org/uc-inventory`, the node `dev.example.org` on Incus at `10.0.0.21`, and a uc-controller checkout at `~/uc-controller`. Batch names in commands are `raw-YYYY-MM-DD-NN`: put the batch's real name there. The register's `raw-1970-01-01-01` is for documents and tests only.

## Contents

- [Before admission](#before-admission)
- [Admit the candidates of a batch](#admit-the-candidates-of-a-batch)
- [The admitted name](#the-admitted-name)
- [What admission refuses](#what-admission-refuses)
- [Commit the admission](#commit-the-admission)
- [Nodes uc-node did not build](#nodes-uc-node-did-not-build)
- [Move a node admitted under its hostname](#move-a-node-admitted-under-its-hostname)
- [Onboard, normalize and specialize](#onboard-normalize-and-specialize)
- [What the firewall holds after each stage](#what-the-firewall-holds-after-each-stage)
- [Changelog](#changelog)

## Before admission

From uc-node's guide 4, for each node of the batch:

- the candidate is committed in the client inventory, `candidates/<fqdn>.yml`;
- you compared its fingerprint with the one the node's console shows, and they agree.

On the controller:

- the batch password is in `~/.secrets/uc/fleet/batches/raw-YYYY-MM-DD-NN.yml`, as uc-node's guide 0, Set Up a Client, and uc-controller's [Batch Secrets](batch-secrets.md) describe;
- the client's key, `onboard_ssh_private_key_file` in `onboard/dev/group_vars/all.yml`, is in the agent if it has a passphrase. Admission offers that key alone, with `IdentitiesOnly=yes`:

  ```sh
  ssh-add -l | grep example-org-raw-initial-id_ed25519 || ssh-add -t 1h ~/.ssh/example-org-raw-initial-id_ed25519
  ```

## Admit the candidates of a batch

From the uc-controller checkout, with the client inventory's raw stage and the onboard stage of the environment the nodes are for:

```sh
batch=raw-YYYY-MM-DD-NN
cd ~/uc-controller
ansible-playbook $(scripts/inventory-args ~/.private/uc/example-org/uc-inventory raw onboard/dev) \
  ingress/playbooks/05_admit.yml -e admit_batch_id="$batch" -e admit_from_candidates=true
cd -
```

Admission reads every file in `candidates/` whose `raw_node_batch` is the batch, with PyYAML's `BaseLoader`, and checks it against the candidate's fields in the raw node handoff design before it uses it. For each candidate it:

1. refuses it, without contacting the node, when its `node_label` is `dev`, `stage` or `prod` and the run's onboard stage is another. A `raw` candidate goes with any onboard stage;
2. scans the node's host keys at the candidate's address and port;
3. reads the confirmation as the initial user with the client's key, trusting only the scanned keys, and checks it with `scripts/check_raw_confirmation.py`;
4. checks that the confirmation's hostname is the first label of the candidate's name, that the confirmation lists exactly the scanned keys, and that the candidate's fingerprint is one of them;
5. matches the name and the node's identity against every stage of the client inventory;
6. writes a new node into `raw/admitted.yml` and its host keys into `ssh/known_hosts`, both under its name, and confirms a connection as the initial user and a become with the batch password.

Admission never changes `candidates/`. It ends with one line per candidate:

```text
TASK [Report every candidate] **************************************************
ok: [localhost] =>
    msg:
    - '10.0.0.21: admitted dev.example.org - dev.example.org is new on every count'
```

It exits 0 when every candidate was admitted or is known, and 2, after the report, when any candidate was refused or stopped, or a candidate file is not valid. Run it again at any time: a node already admitted is reported as `known` and left as it is.

## The admitted name

A node is admitted under its fully qualified domain name, the candidate's top-level key, such as `dev.example.org`, never under its hostname alone. The node keeps that name from uc-node's `intake/` to `normalized/`: promotion and demotion carry it unchanged, and `scripts/check_inventory.py` refuses an admitted host, or an onboarded or normalized host that carries `raw_node_batch`, whose name is not fully qualified. Two domains in one client inventory, `dev.example.org` and `dev.example.net`, are then two nodes.

The confirmation on the node stays keyed by the hostname, `dev`, as the raw node contract has it, which is why admission checks that the hostname is the first label of the name.

Host keys are kept in `ssh/known_hosts` under the name, which the admitted group's SSH connection uses as `HostKeyAlias`. A node's keys therefore stay with it when its address changes, and an address reused by another test node does not inherit them.

## What admission refuses

| Report | Cause | What to do |
| :-- | :-- | :-- |
| `refused <name> - its candidate has node_label stage, and this run is onboard/dev` | The candidate was built for another environment | Admit it with the onboard stage of its label |
| `refused <name> - the confirmation names the host dev, which is not the first label of stage.example.org from its candidate` | The node at the candidate's address is not the node the candidate names | Find out which node answered. Rebuild, or correct the candidate by rebuilding |
| `refused <name> - the fingerprint in its candidate, SHA256:…, is not among the host keys` | The node presents other host keys than the build read | Do not admit it. Compare at the console, find out why, and rebuild |
| `refused <name> - RN-…` | The confirmation breaks a clause of the raw node contract | uc-node's to fix, as guide 4 says |
| `stopped <name> - <name> is new, but its identity is known as: dev (machine_id and mac, raw/admitted.yml)` | The node is admitted already, under another name | See [Move a node admitted under its hostname](#move-a-node-admitted-under-its-hostname) |
| `not valid, skipped: candidates/<file>: lacks fingerprint` | The candidate file does not hold the handoff design's fields | Rebuild the node, so uc-node writes it again. The pre-commit hook refuses such a file too |
| `No valid candidate in … names the batch raw-YYYY-MM-DD-NN` | No committed candidate names the batch | Check the batch name, and that uc-node wrote the candidates |

A run with `admit_candidates`, the list given with `-e @<file>` before 0.2.0, is refused with a message naming `admit_from_candidates`.

## Commit the admission

Check that the ED25519 key recorded for the node is the one you compared at the console, then commit:

```sh
cd ~/.private/uc/example-org/uc-inventory
ssh-keygen -lf ssh/known_hosts
git diff raw/admitted.yml
git add raw/admitted.yml ssh/known_hosts
UC_CONTROLLER=~/uc-controller git commit -m "Admit dev.example.org, batch raw-YYYY-MM-DD-NN"
cd -
```

`ssh-keygen -lf` prints each key's size, fingerprint, name and type, so the line ending `dev.example.org (ED25519)` holds the fingerprint to compare. `raw/admitted.yml` gains a host `dev.example.org` with its address, port, contract, baseline, machine ID, MAC addresses, batch and the time of admission.

## Nodes uc-node did not build

A node without a candidate, such as a uc-ventoy install, is admitted by address. Without a candidate, admission takes the name from the confirmation's hostname and `admit_client_domain`, which is required:

```sh
ansible-playbook $(scripts/inventory-args ~/.private/uc/example-org/uc-inventory raw onboard/dev) \
  ingress/playbooks/05_admit.yml -e admit_batch_id="$batch" \
  -e admit_addresses=203.0.113.10 -e admit_client_domain=example.org \
  -e admit_expected_fingerprint=SHA256:EXAMPLEexampleEXAMPLEexampleEXAMPLEexample0
```

A node whose confirmation says `deb13-vt-0001` is admitted as `deb13-vt-0001.example.org`. Give `admit_expected_fingerprint`, the ED25519 fingerprint read at the node's console, for a single address: without it, admission trusts the host key on first use and says so, as PA-HOST-01. `admit_from_discovered=true`, after `00_discover.yml`, takes every address the scan found, also with `admit_client_domain`. Neither is given with `admit_from_candidates`, whose candidates name their nodes.

## Move a node admitted under its hostname

Admission before 0.2.0 named a node by its hostname, so `dev.example.org` may be in `raw/admitted.yml` as `dev`. Admitting it again from its candidate is stopped, since its machine ID is known under the other name. Remove the old entry and its host keys, then admit it again.

Remove `dev` from `raw/admitted.yml`, keeping the file's header:

```sh
cd ~/.private/uc/example-org/uc-inventory
python3 - dev <<'EOF'
import sys, yaml
path, host = "raw/admitted.yml", sys.argv[1]
text = open(path, encoding="utf-8").read()
data = yaml.safe_load(text)
del data["admitted"]["hosts"][host]
with open(path, "w", encoding="utf-8") as handle:
    handle.write(text[:text.index("admitted:")])
    handle.write(yaml.safe_dump(data, sort_keys=False))
EOF
```

Remove its block from `ssh/known_hosts`, from its `BEGIN` line to its `END` line:

```sh
sed -i '/^# BEGIN dev, admitted by 05_admit.yml$/,/^# END dev, admitted by 05_admit.yml$/d' ssh/known_hosts
git diff
```

`git diff` should show only `dev`'s entry and its block removed. Commit both, then admit the node from its candidate, as above, and commit that admission:

```sh
git add raw/admitted.yml ssh/known_hosts
UC_CONTROLLER=~/uc-controller git commit -m "Remove dev, admitted under its hostname, to admit it as dev.example.org"
cd -
```

A node that was promoted past raw under its hostname is demoted first, with `scripts/demote_node.py --inventory ~/.private/uc/example-org/uc-inventory --from onboard/dev --to raw --host dev`, and its keys removed in the same way.

## Onboard, normalize and specialize

`10_onboard.yml` onboards the nodes it reaches as root, through Incus or a subnet scan: it bootstraps Python, converges the onboard baseline, creates the initial user with the client's key, writes the firewall's base fragment, switches the node to SSH as the initial user, and writes it into the onboard stage. It leaves admitted nodes out, and says so:

```text
Skipping admitted nodes (dev.example.org): onboarding contract nodes comes in a later kickoff.
```

For a node reached through Incus, with the client inventory's Incus plugin:

```sh
ansible-playbook $(scripts/inventory-args ~/.private/uc/example-org/uc-inventory raw onboard/dev) \
  ingress/playbooks/10_onboard.yml -l dev-example-org,localhost
ansible-playbook $(scripts/inventory-args ~/.private/uc/example-org/uc-inventory onboard/dev normalized/dev) \
  converge/playbooks/20_normalize.yml -l dev-example-org,localhost
ansible-playbook $(scripts/inventory-args ~/.private/uc/example-org/uc-inventory onboard/dev normalized/dev) \
  converge/playbooks/30_specialize.yml -l dev-example-org,localhost -e specialize_role=webserver
```

A limit with `-l` must name `localhost` too. Every playbook's first play runs on `localhost`, to find the client inventory, and the later plays need what it found.

`20_normalize.yml` takes `-e target_group=webservers` to put the node into the group whose services `30_specialize.yml` opens. Commit what each run writes, `onboard/dev/hosts.yml`, then `normalized/dev/hosts.yml` with the removal from `onboard/dev/hosts.yml`, in the client inventory.

## What the firewall holds after each stage

The firewall is Foomuuri, written by `steelcj.foomuuri`, with one nftables table, `inet foomuuri`. uc-node builds the node with a bootstrap base fragment, and from onboarding on uc-controller owns every fragment in `/etc/foomuuri/`:

| After | `/etc/foomuuri/` holds | From the client inventory |
| :-- | :-- | :-- |
| uc-node's build | `10-base.conf`, uc-node's bootstrap rule: SSH from the node definition's `ssh_sources` | `intake/<fqdn>.yml` |
| `10_onboard.yml` | `10-base.conf`, uc-controller's: DHCP, DHCPv6, ping, and SSH on 22 from `firewall_onboard_ssh`'s sources. Every other `.conf` file is removed, and so are ufw and firewalld | `onboard/<env>/group_vars/all.yml` |
| `20_normalize.yml` | `10-base.conf` and `20-normalize.conf`, the normalize services | `firewall_normalize_services` in `normalized/<env>/group_vars/all.yml` |
| `30_specialize.yml` | All three, `30-specialize.conf` holding the services of the node's groups | `firewall_specialize_services` in `normalized/<env>/group_vars/<group>.yml`, such as `webservers.yml` |

Each stage keeps the others' fragments, so rerunning normalize after specialize leaves `30-specialize.conf` in place. A stage whose service list is empty removes its own fragment. Every other incoming connection is dropped and logged by Foomuuri's final rule.

Onboarding refuses to run unless `firewall_onboard_ssh` gives SSH on the port the controller uses, and normalize and specialize refuse a node without `10-base.conf`, since their fragments accept no SSH: either would lock the controller out. To look at the firewall on an Incus node:

```sh
incus exec dev-example-org -- ls /etc/foomuuri
incus exec dev-example-org -- nft list tables
```

Output example, after specialize:

```text
10-base.conf  20-normalize.conf  30-specialize.conf
table inet foomuuri
```

## Changelog

| Version | Date | Change |
| :-- | :-- | :-- |
| 0.1.0 | 2026-11-27 | First version, for uc-controller 0.2.0: admitting from `candidates/`, the fully qualified name, admitting by address with `admit_client_domain`, moving a node admitted under its hostname, and the Foomuuri fragments of each stage. Admitted nodes are not onboarded yet |
