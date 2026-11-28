# uc-controller

An Ansible controller that moves nodes through a lifecycle of stages: raw nodes are discovered or admitted, onboarded so they can be managed, normalized to a common baseline, and specialized for what they are for. It holds the code and the defaults; every client's hosts, values and trusted host keys live in a private inventory repository of the client's own, and secrets live in neither.

## Stages

| Stage | Playbook | What it does |
| :-- | :-- | :-- |
| Raw | `ingress/playbooks/00_discover.yml`, `ingress/playbooks/05_admit.yml` | Finds nodes by a subnet scan, or admits the nodes uc-node hands over as candidates, and others that meet the raw node contract, after checking their confirmation, host keys and identity, under their fully qualified domain names |
| Onboard | `ingress/playbooks/10_onboard.yml` | Creates the `initial` user, hardens SSH, writes the Foomuuri base fragment `10-base`, and switches the node to SSH as `initial`. Admitted nodes are not onboarded yet |
| Normalize | `converge/playbooks/20_normalize.yml` | Converges the compliance baseline, and writes the Foomuuri fragment `20-normalize` |
| Specialize | `converge/playbooks/30_specialize.yml` | Applies a role for the node's purpose, such as `webserver`, and writes the Foomuuri fragment `30-specialize` |

`site.yml` chains them. Every playbook runs against a client inventory, given with `scripts/inventory-args`, and refuses to run without one:

```bash
ansible-playbook $(scripts/inventory-args ~/.private/uc/example-org/uc-inventory raw onboard/dev) \
  ingress/playbooks/05_admit.yml -e admit_batch_id=raw-YYYY-MM-DD-NN -e admit_from_candidates=true
```

The firewall is Foomuuri, through `steelcj.foomuuri`: uc-node builds nodes with a bootstrap base fragment, and uc-controller owns every fragment from onboarding on.

## Outside this repository

- **Client inventories**, one private repository per client, made with `scripts/new-inventory` from `inventory-template/`: the hosts at each stage, the client's values, `ssh/known_hosts`, and uc-node's `intake/` and `candidates/`. See [Client Inventories](en/docs/guides/client-inventories.md).
- **uc-node**, which builds raw nodes to the raw node contract and hands each over as a candidate in the client inventory. Its guides start where a client is set up and end at the handover, where [Admit and Onboard](en/docs/guides/admit-and-onboard.md) starts.
- **Secrets**, in `~/.secrets/uc/fleet/` on the controller, read only through the `uc_secret` lookup. See [Batch Secrets](en/docs/guides/batch-secrets.md).

## Layout

| Path | What it holds |
| :-- | :-- |
| `VERSION` | The repository's version |
| `CHANGELOG.md` | What changed in each release |
| `ROADMAP.md` | Planned and possible work |
| `CONTRIBUTORS.md` | How changes, versions and releases are handled |
| `ingress/` | The playbooks and roles that take a node from raw to onboarded, whatever its source |
| `converge/` | The playbooks and roles that take an onboarded node to normalized and specialized |
| `shared/` | The `uc_secret` lookup, and the client inventory check every playbook starts with |
| `roles/` | Roles developed in uc-controller, and the robertdebock roles and `steelcj.umask`, committed from `requirements.yml` earlier. A role developed elsewhere, such as `steelcj.foomuuri`, is pinned in `requirements.yml` and installed with `ansible-galaxy role install -r requirements.yml -p ~/.ansible/roles`, not committed. Without `-p`, run from here, `ansible-galaxy` installs into `roles/`, the first entry on `roles_path`. `tests/run_tests.py` offers to install a missing role |
| `inventory-defaults/` | The logic half of the inventories, one directory per stage, loaded before every client inventory |
| `inventory-template/` | The layout of a client inventory repository |
| `scripts/` | The release scripts, and the scripts for client inventories: `inventory-args`, `new-inventory`, `check_inventory.py`, `read_candidates.py`, `promote_node.py`, `demote_node.py` and others |
| `tests/` | The tests, run with `python3 tests/run_tests.py`, which fails on a skipped test and offers to install a missing role |
| `en/docs/guides/` | Step-by-step guides |

## Guides

- [Client Inventories](en/docs/guides/client-inventories.md): making a client's inventory repository, and running playbooks against it
- [Batch Secrets](en/docs/guides/batch-secrets.md): where batch passwords are kept, and how to create and retire one
- [Admit and Onboard](en/docs/guides/admit-and-onboard.md): admitting the candidates uc-node hands over, and other contract nodes, under their fully qualified names, and the firewall each later stage writes
- [Admitting a raw node](en/docs/admitting-a-raw-node.md): admission as 0.1.x did it, kept as a record
- The design, in [uc-controller v0.1.8](en/docs/uc-controller-v0.1.8.md)

## Releases

Releases are cut and published with the scripts in `scripts/`, as described in [Cut and Publish a Release](en/docs/guides/releases/cut-and-publish-a-release.md).

## License

SPDX-License-Identifier: AGPL-3.0-or-later

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. See [LICENSE](LICENSE).
