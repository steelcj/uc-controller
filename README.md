# uc-controller

An Ansible controller that moves nodes through a lifecycle of stages: raw nodes are discovered or admitted, onboarded so they can be managed, normalized to a common baseline, and specialized for what they are for. It holds the code and the defaults; every client's hosts, values and trusted host keys live in a private inventory repository of the client's own, and secrets live in neither.

## Stages

| Stage | Playbook | What it does |
| :-- | :-- | :-- |
| Raw | `ingress/playbooks/00_discover.yml`, `ingress/playbooks/05_admit.yml` | Finds nodes by a subnet scan, or admits nodes that meet the raw node contract after checking their confirmation, host keys and identity |
| Onboard | `ingress/playbooks/10_onboard.yml` | Creates the `initial` user, hardens SSH, sets up the firewall, and switches the node to SSH as `initial` |
| Normalize | `converge/playbooks/20_normalize.yml` | Converges the compliance baseline |
| Specialize | `converge/playbooks/30_specialize.yml` | Applies a role for the node's purpose, such as `webserver` |

`site.yml` chains them. Every playbook runs against a client inventory, given with `scripts/inventory-args`, and refuses to run without one:

```bash
ansible-playbook $(scripts/inventory-args ~/uc-inventories/example.org raw onboard/dev) \
  ingress/playbooks/05_admit.yml -e admit_batch_id=raw-1970-01-01-01 -e @candidates.yml
```

## Outside this repository

- **Client inventories**, one private repository per client, made with `scripts/new-inventory` from `inventory-template/`: the hosts at each stage, the client's values, and `ssh/known_hosts`. See [Client Inventories](en/docs/guides/client-inventories.md).
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
| `shared/` | Roles both use, the `uc_secret` lookup, and the client inventory check every playbook starts with |
| `roles/` | Vendored Galaxy roles, installed from `requirements.yml` |
| `inventory-defaults/` | The logic half of the inventories, one directory per stage, loaded before every client inventory |
| `inventory-template/` | The layout of a client inventory repository |
| `scripts/` | The release scripts, and the scripts for client inventories: `inventory-args`, `new-inventory`, `check_inventory.py`, `promote_node.py`, `demote_node.py` and others |
| `tests/` | The tests, run with `python3 tests/run_tests.py` |
| `en/docs/guides/` | Step-by-step guides |

## Guides

- [Client Inventories](en/docs/guides/client-inventories.md): making a client's inventory repository, and running playbooks against it
- [Batch Secrets](en/docs/guides/batch-secrets.md): where batch passwords are kept, and how to create and retire one
- [Admitting a raw node](en/docs/admitting-a-raw-node.md): admitting nodes that meet the raw node contract
- The design, in [uc-controller v0.1.8](en/docs/uc-controller-v0.1.8.md)

## Releases

Releases are cut and published with the scripts in `scripts/`, as described in [Cut and Publish a Release](en/docs/guides/releases/cut-and-publish-a-release.md).

## License

See [LICENSE](LICENSE).
