---
dc:title: "Incus: Instance Naming"
dcterms:version: "0.1.0"
dc:creator: "Christopher Steel"
dc:contributor: "Augure"
dc:subject:
  - "incus"
  - "naming"
  - "containers"
  - "virtual-machines"
  - "snapshots"
dc:description: "Convention for naming Incus containers and virtual machines: the instance name identifies the operating system, snapshots carry lifecycle state, and the name never changes across the node's life."
dc:publisher: "UniversalCake"
dcterms:created: "2026-11-12"
dcterms:modified: "2026-11-12"
dc:format: "text/markdown"
dc:language: "en"
sat:language_bcp47: "en"
dc:identifier: "incus--instance-naming"
dcterms:rightsHolder: "Christopher Steel"
dc:rights: >
  Copyright 2026 Christopher Steel / UniversalCake.
  SPDX-License-Identifier: AGPL-3.0-or-later
sat:uuid: ""
sat:version_at_creation: ""
sat:migration_status: pre-sat
sat:changelog:
  - version: "0.1.0"
    date: "2026-11-12"
    author: "Christopher Steel"
    notes: >
      Initial draft. Codifies the naming convention used for uc-controller
      test nodes: OS-based instance names, unnumbered raw snapshot as the
      origin, numbered lifecycle-stage snapshots, and tmp-prefixed scratch
      snapshots.
---

# Incus: Instance Naming

Version: 0.1.0
Status: Draft
Style Guide: style-guide--versioned-documents-in-unrendered-markdown

## Abstract

This document states how Incus containers and virtual machines are named, and how their snapshots are named, so that a node's inventory entry never changes across its lifecycle. The instance name identifies what the node is, its operating system. Snapshots identify what state it is in. The separation exists because renaming an instance changes its inventory name (`name.project.remote`), which breaks automated inventory writers such as `promote_node.py`.

## Sources and Acknowledgements

The naming constraints that govern this convention are set by Incus itself. An instance name is 1 to 63 characters long, uses only ASCII letters, digits, and hyphens, does not start with a digit or a hyphen, and does not end with a hyphen <a id="cite-incus-instance-properties"></a>([Linux Containers, n.d.-b](#ref-incus-instance-properties)). The length and character set are the host name rules of RFC 1123 <a id="cite-rfc1123"></a>([Braden, 1989](#ref-rfc1123)). Incus is stricter on one point: RFC 1123 allows a host name to begin with a digit, and Incus does not.

## The principle

State does not belong in an instance name. A node called `raw-deb13` stops being raw the moment onboarding finishes, and renaming it to reflect its new state breaks every downstream reference to its inventory name. The name answers "what is this node?" and never changes. Snapshots answer "what state is it in?" and are free to accumulate.

## Instance names

An instance is named after its operating system. The name is short, memorable, and stable for the life of the node.

| Part | Values | Example |
|------|--------|---------|
| OS | short code plus version | `deb13`, `ubu2404`, `rky9` |
| disambiguator | numeric suffix, only when a second instance of the same OS is needed | `deb13-2` |
| type suffix | `vm`, only when a VM and a container of the same OS coexist | `deb13-vm` |

Most of the time the name is simply the OS code: `deb13`, `ubu2404`, `rky9`. The disambiguator and type suffix appear only when there is a real collision.

## OS code table

The code is a short abbreviation plus the version number. Ubuntu keeps four digits because its releases are identified by year and month, and an LTS release and an interim release can share a year. Debian, Rocky, and Fedora carry only the major version.

| OS | Code | Note |
|----|------|------|
| Debian 12 | `deb12` | |
| Debian 13 | `deb13` | |
| Ubuntu 24.04 LTS | `ubu2404` | Four digits, so that 24.04 and 24.10 do not collide |
| Ubuntu 24.10 | `ubu2410` | |
| Rocky 9 | `rky9` | |
| Fedora 42 | `fed42` | |

## Filtering

The instance name covers the common queries without any additional metadata. `incus list` treats a bare keyword as a name prefix and also accepts a regular expression on the name <a id="cite-incus-list"></a>([Linux Containers, n.d.-a](#ref-incus-list)). Ansible takes a glob in `--limit`.

```sh
incus list deb                     # all Debian containers and VMs
incus list ubu                     # all Ubuntu instances
ansible-playbook ... -l 'deb13*'   # the same idea, as an Ansible limit
```

For cross-cutting filters that do not follow the name pattern, for example every node in the onboarding test batch regardless of OS, set a `user.*` configuration key on the instances and filter on it:

```sh
incus config set deb13 user.batch=onboard
incus config set rky9 user.batch=onboard
incus list user.batch=onboard
```

## Snapshot names

Snapshots carry lifecycle state. There are three categories, each with its own visual signature so the intent is obvious at a glance.

| Prefix | Meaning | Deletion policy |
|--------|---------|-----------------|
| (none) | the origin, the baseline you return to | never delete, never overwrite |
| `NN-` | a lifecycle stage, numbered by the playbook that produces it | keep; replace only by retaking the stage |
| `tmp-` | scratch, safe to discard | bulk-deletable |

### The raw snapshot

The bare word `raw` names the state as launched from the image, first boot finished, nothing applied. It carries no number because it is not a step in a sequence, it is the origin you return to. One word is used everywhere: the inventory group, the lifecycle stage, and the snapshot name.

```sh
incus snapshot create deb13 raw
```

Take `raw` once, immediately after first boot, and never overwrite it. If the image changes, launch a new instance.

### Numbered stages

The number matches the playbook that produces the state. Two digits, spaced by tens, leave room for insertion.

| Snapshot | Produced by |
|----------|-------------|
| `10-onboarded` | `10_onboard.yml` |
| `20-normalized` | `20_normalize.yml` |
| `30-webserver` | `30_specialize.yml`, with the role appended |

Restoring a numbered stage gives you a node ready for the next stage's work, without replaying the earlier playbooks. The node's entry must still be present in the matching inventory for that to hold.

### Scratch snapshots

Any temporary snapshot takes the `tmp-` prefix with a short note:

```sh
incus snapshot create deb13 tmp-broken-apt
incus snapshot create deb13 tmp-mid-playbook
```

The `tmp-` prefix makes cleanup mechanical:

```sh
incus snapshot list deb13 --format csv | cut -d, -f1 | grep '^tmp-' | \
  xargs -I{} incus snapshot delete deb13 {}
```

## Reset workflow

Returning a node to its baseline is two commands:

```sh
incus snapshot restore deb13 raw
python3 scripts/reset_inventories.py
```

The restore reverts the instance only. The second command clears the node's entries from the stage inventories on the controller, and empties the fact cache, because the restored node no longer has the SSH access and address those entries describe.

## Rules

- Never reuse a name for a different OS or type. Delete the instance and take the next disambiguated index.
- Never overwrite `raw`. If the image changes, the node is no longer the same thing, so launch a new one.
- Never number `raw`. It is the origin, not a stage.
- Never modify a numbered snapshot in place. If a stage needs to be retaken, delete the old snapshot and create a new one with the same name. The name means "the state produced by this playbook", not "the first attempt at this playbook".

## License

This document, *Incus: Instance Naming*, by **Christopher Steel**, with AI assistance from **Augure**, is licensed under the [GNU Affero General Public License v3.0 or later](https://www.gnu.org/licenses/agpl-3.0.html).

## Resources

### Platform documentation

- [Incus documentation](https://linuxcontainers.org/incus/docs/main/)

### Naming constraints

- [RFC 1123, Requirements for Internet Hosts](https://www.rfc-editor.org/rfc/rfc1123)

## References

<a id="ref-rfc1123"></a>
Braden, R. (Ed.). (1989). *Requirements for Internet hosts: Application and support* (RFC 1123). Internet Engineering Task Force. https://www.rfc-editor.org/rfc/rfc1123
[Return to citation](#cite-rfc1123)

<a id="ref-incus-list"></a>
Linux Containers. (n.d.-a). *incus list*. Incus documentation. Retrieved November 12, 2026, from https://linuxcontainers.org/incus/docs/main/reference/manpages/incus/list/
[Return to citation](#cite-incus-list)

<a id="ref-incus-instance-properties"></a>
Linux Containers. (n.d.-b). *Instance properties*. Incus documentation. Retrieved November 12, 2026, from https://linuxcontainers.org/incus/docs/main/reference/instance_properties/
[Return to citation](#cite-incus-instance-properties)

## Changelog

| Version | Status | Notes |
|---------|--------|-------|
| 0.1.0 | Draft | Initial draft; codifies OS-based instance names, unnumbered raw snapshot, numbered lifecycle stages, and tmp-prefixed scratch snapshots |
