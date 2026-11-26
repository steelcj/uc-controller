# Client Inventory

This repository is the inventory of one client of uc-controller: which nodes the client has, at which stage of their lifecycle, and the values that describe the client, such as its locale, its firewall rules and the controller key that reaches its nodes. It holds facts only, never secrets and never logic. Keep it private: it names the client's hosts and addresses.

How a node is reached and set up is logic, and lives in uc-controller's `inventory-defaults/`. Batch passwords are secrets, and live outside every repository, in `~/.secrets/uc/fleet/batches/<batch>.yml` on the controller. Nodes carry only the name of their batch, as `raw_node_batch`.

## Layout

| Path | Holds | Written by |
| :-- | :-- | :-- |
| `raw/admitted.yml` | Raw nodes admitted under the raw node contract | `05_admit.yml` |
| `raw/discovered.yml` | Raw nodes found by a subnet scan | `00_discover.yml` |
| `raw/incus.yml` | The Incus inventory plugin's settings; delete it when there is no Incus server | By hand |
| `raw/group_vars/` | Values for the raw stage | By hand |
| `onboard/<environment>/hosts.yml` | Onboarded nodes, one file per environment (`dev`, `stage`) | `promote_node.py` |
| `onboard/<environment>/group_vars/` | Values for that environment: the controller key, the initial user's public keys, locale, time zone, and SSH into the node for the firewall | By hand |
| `normalized/<environment>/hosts.yml` | Normalized nodes | `promote_node.py` |
| `normalized/<environment>/group_vars/` | Values for that environment: the firewall services, per group where needed | By hand |
| `ssh/known_hosts` | The host keys trusted for admitted nodes, at every stage | `05_admit.yml` |
| `.githooks/pre-commit` | The check run before every commit | uc-controller's template |

The generated files are committed, so the history records when each node was admitted, promoted and trusted. Do not edit them by hand.

## Using it

Run uc-controller's playbooks from the uc-controller checkout, with `scripts/inventory-args` giving the `-i` options for the stages the playbook needs. It lists uc-controller's defaults first and this repository's directories after them, so a value here overrides a default:

```bash
ansible-playbook $(scripts/inventory-args ~/uc-inventories/example.org raw onboard/dev) \
  ingress/playbooks/05_admit.yml -e admit_batch_id=raw-1970-01-01-01 -e @candidates.yml
```

## Where a value goes

A run that combines stages, such as admission with `raw` and `onboard/dev`, merges their `all` groups, and the last directory loaded wins for every host. So:

- A value in a `group_vars/all.yml` must mean the same at every stage, such as `uc_client_inventory: true`.
- A value that differs by stage goes on the stage's own group: `raw/group_vars/raw.yml`, `onboard/<environment>/group_vars/onboarded.yml` or `normalized/<environment>/group_vars/normalized.yml`. `uc_known_hosts_file` is one, since it is built from each stage's directory depth.

## The pre-commit hook

`.githooks/pre-commit` runs uc-controller's `scripts/check_inventory.py`, which refuses a commit that puts logic or secrets here: connection variables in `group_vars/` or `host_vars/`, an encrypted vault file, a password hash, a private key, a lookup, or an admitted host without a batch or without its host keys in `ssh/known_hosts`. Then it runs `yamllint`.

The hook needs `UC_CONTROLLER` set to a uc-controller checkout, and refuses every commit until it is. Without uc-controller, either remove `.githooks/pre-commit`, or commit with `git commit --no-verify`.
