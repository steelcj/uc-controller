# Preparing incus containers and vm's for ansible runs

On the incus host list your containers and vms

```bash
incus list -c nt
┌──────────┬─────────────────┐
│   NAME   │      TYPE       │
├──────────┼─────────────────┤
│ ex2-test │ CONTAINER       │
├──────────┼─────────────────┤
│ mint223  │ CONTAINER       │
├──────────┼─────────────────┤
│ web      │ CONTAINER       │
├──────────┼─────────────────┤
│ windows  │ VIRTUAL-MACHINE │
└──────────┴─────────────────┘
```

You should be using snapshots for testing so you can roll back almost instantly so list your snapshots for the target containers

```bash
incus snapshot list ex2-test
```

output:

```bash
┌──────────────────────────┬──────────────────────┬────────────┬──────────┐
│           NAME           │       TAKEN AT       │ EXPIRES AT │ STATEFUL │
├──────────────────────────┼──────────────────────┼────────────┼──────────┤
│ fresh                    │ 2026/11/09 21:11 EST │            │ NO       │
├──────────────────────────┼──────────────────────┼────────────┼──────────┤
│ before-ansible2-20261110 │ 2026/11/10 19:59 EST │            │ NO       │
├──────────────────────────┼──────────────────────┼────────────┼──────────┤
│ ansible2-converged       │ 2026/11/10 21:48 EST │            │ NO       │
└──────────────────────────┴──────────────────────┴────────────┴──────────┘
```

so here we want to use the snapshot called fresh

* [incus snapshot restore](https://linuxcontainers.org/incus/docs/main/reference/manpages/incus/snapshot/restore/#incus-snapshot-restore-md)

```bash
incus snapshot restore ex2-test fresh
```

start any containers or vms you want by name

```sh
incus start ex2-test
# incus start --all          # or start every stopped instance
```

Then confirm they’re up and have addresses:

```sh
incus list status=running -c ns4t
```

Output example:

```bash
┌──────────┬─────────┬───────────────────────┬───────────┐
│   NAME   │  STATE  │         IPV4          │   TYPE    │
├──────────┼─────────┼───────────────────────┼───────────┤
│ ex2-test │ RUNNING │ 10.119.134.207 (eth0) │ CONTAINER │
└──────────┴─────────┴───────────────────────┴───────────┘
```

That shows name, state, IPv4 and type (container or virtual-machine).

Two things to keep in mind:

- **VMs take longer.** A VM shows `RUNNING` as soon as it powers on, but Ansible can’t reach it until the guest has booted and the Incus agent is up. `incus exec <vm> -- true` returning without error is the sign it’s ready.
- **Your inventory only shows running instances.** That’s the `status=running` filter in `incus.yml`, so once the others are started, re-running the `--graph` command will list them. Remove the filter if you’d rather see stopped ones too; just don’t target them.

If the instances live in another Incus project, add `--project <name>` to the start command (or `--all-projects` to `incus list` to find them).

That's working: both instances are found, under `incus` → `incus_local` → `incus_local_default` (remote `local`, project `default`). Three next steps.

## Confirm

```bash
ansible-inventory -i inventories/raw/incus.yml --graph
@all:
  |--@ungrouped:
  |--@incus:
  |  |--@incus_local:
  |  |  |--@incus_local_default:
  |  |  |  |--ex2-test.default.local
```

```bash
nano 
```



## Put them in the `raw` group



`10_onboard.yml` targets `hosts: raw`, and that group doesn't exist yet. The plugin lists `keyed_groups` among its options, which suggests it supports the standard constructed options, so this should do it:

```yaml
plugin: community.general.incus
filters:
  - status=running
groups:
  raw: true
```

Re-run the `--graph` command and you should see `@raw` with both hosts. If `groups` is rejected, tell me and we'll use a small static file that makes `incus` a child of `raw` instead.

Output:

```bash
@all:
  |--@ungrouped:
  |--@incus:
  |  |--@incus_local:
  |  |  |--@incus_local_default:
  |  |  |  |--ex2-test.default.local
  |--@raw:
  |  |--ex2-test.default.local
```

now we see the @raw group

## Check what connection variables it set

```sh
ansible-inventory -i inventories/raw/incus.yml --host ex2-test.default.local
```

Output example:

```bash
{
    "ansible_incus_architecture": "x86_64",
    "ansible_incus_config": {
        "image.architecture": "amd64",
        "image.description": "Debian trixie amd64 (20261109_05:24)",
        "image.os": "Debian",
        "image.release": "trixie",
        "image.serial": "20261109_05:24",
        "image.type": "squashfs",
        "image.variant": "default",
        "limits.cpu": "1",
        "limits.memory": "1GiB",
        "volatile.base_image": "aebce3851afe80aaf48f9ee7839103c8f9a6593d41b321f6a6ccbc19bb42a37c",
        "volatile.cloud-init.instance-id": "4be0b24c-c64f-4dbf-96af-2297e6d9ab5f",
        "volatile.eth0.host_name": "veth106fc78a",
        "volatile.eth0.hwaddr": "10:66:6a:48:e8:8c",
        "volatile.idmap.base": "0",
        "volatile.idmap.current": "[{\"Isuid\":true,\"Isgid\":false,\"Hostid\":1000000,\"Nsid\":0,\"Maprange\":1000000000},{\"Isuid\":false,\"Isgid\":true,\"Hostid\":1000000,\"Nsid\":0,\"Maprange\":1000000000}]",
        "volatile.idmap.next": "[{\"Isuid\":true,\"Isgid\":false,\"Hostid\":1000000,\"Nsid\":0,\"Maprange\":1000000000},{\"Isuid\":false,\"Isgid\":true,\"Hostid\":1000000,\"Nsid\":0,\"Maprange\":1000000000}]",
        "volatile.last_state.idmap": "[]",
        "volatile.last_state.power": "RUNNING",
        "volatile.uuid": "0e93015d-6403-46a5-a46b-b943f2500abc",
        "volatile.uuid.generation": "c3a1cbcc-a917-4274-a5aa-e03f122135e0"
    },
    "ansible_incus_description": "",
    "ansible_incus_devices": {},
    "ansible_incus_ephemeral": false,
    "ansible_incus_expanded_config": {
        "image.architecture": "amd64",
        "image.description": "Debian trixie amd64 (20261109_05:24)",
        "image.os": "Debian",
        "image.release": "trixie",
        "image.serial": "20261109_05:24",
        "image.type": "squashfs",
        "image.variant": "default",
        "limits.cpu": "1",
        "limits.memory": "1GiB",
        "volatile.base_image": "aebce3851afe80aaf48f9ee7839103c8f9a6593d41b321f6a6ccbc19bb42a37c",
        "volatile.cloud-init.instance-id": "4be0b24c-c64f-4dbf-96af-2297e6d9ab5f",
        "volatile.eth0.host_name": "veth106fc78a",
        "volatile.eth0.hwaddr": "10:66:6a:48:e8:8c",
        "volatile.idmap.base": "0",
        "volatile.idmap.current": "[{\"Isuid\":true,\"Isgid\":false,\"Hostid\":1000000,\"Nsid\":0,\"Maprange\":1000000000},{\"Isuid\":false,\"Isgid\":true,\"Hostid\":1000000,\"Nsid\":0,\"Maprange\":1000000000}]",
        "volatile.idmap.next": "[{\"Isuid\":true,\"Isgid\":false,\"Hostid\":1000000,\"Nsid\":0,\"Maprange\":1000000000},{\"Isuid\":false,\"Isgid\":true,\"Hostid\":1000000,\"Nsid\":0,\"Maprange\":1000000000}]",
        "volatile.last_state.idmap": "[]",
        "volatile.last_state.power": "RUNNING",
        "volatile.uuid": "0e93015d-6403-46a5-a46b-b943f2500abc",
        "volatile.uuid.generation": "c3a1cbcc-a917-4274-a5aa-e03f122135e0"
    },
    "ansible_incus_expanded_devices": {
        "eth0": {
            "name": "eth0",
            "network": "incusbr0",
            "type": "nic"
        },
        "root": {
            "path": "/",
            "pool": "default",
            "type": "disk"
        }
    },
    "ansible_incus_location": "none",
    "ansible_incus_profiles": [
        "default"
    ],
    "ansible_incus_project": "default",
    "ansible_incus_remote": "local",
    "ansible_incus_status": "Running",
    "ansible_incus_type": "container"
}
```

Look for `ansible_connection`. If it already says `community.general.incus`, the raw group vars I suggested earlier aren't needed for these hosts. If it's absent, add them.

R. `ansible_connection`is not present

## Test the connection without SSH

```sh
ansible -i inventories/raw/incus.yml raw -m ansible.builtin.raw -a "id"
```

The `raw` module needs no Python on the target, so it isolates the connection itself. You want `uid=0(root)` from both. After that, try `-m ansible.builtin.ping`, which tells you whether each instance has a usable Python; if one doesn't, the onboard play has to install it with a `raw` task first.

If `mint223` is a VM and the `id` test hangs or fails on it only, the Incus agent isn't running in that guest.

Paste the `--host` output and the `id` results and I'll draft the onboard changes to match.

## The fix

```bash

```

add 

```yaml
---
# inventories/raw/group_vars/incus.yml
#
ansible_connection: community.general.incus
ansible_user: root
```

Then re-run the host dump

```bash
ansible-inventory -i inventories/raw/incus.yml --host ex2-test.default.local
```

 and look specifically for the connection line:

```bash
ansible-inventory -i inventories/raw/incus.yml --host ex2-test.default.local | grep ansible_connection
```

Output:

```bash
    "ansible_connection": "community.general.incus",
```

You want `"ansible_connection": "community.general.incus"` in the output. Once that shows up, the `raw` test should go through:

```sh
ansible -i inventories/raw/incus.yml raw -m ansible.builtin.raw -a "id"
```

Output example:

```bash
ex2-test.default.local | CHANGED | rc=0 >>
uid=0(root) gid=0(root) groups=0(root)
```

