# Raw Node Kinds and Role Behaviour: Executive Summary

Status: research note, no decision taken. Written 2026-11-18 for later review.

## Purpose

This note records how the kind of a raw node (bare metal, virtual machine, or one of several kinds of container) affects the Ansible roles that uc-controller applies, and what that could mean for the uc-contracts node-onboarding-pipeline contracts and node policies. It is a starting point for a decision record, not the decision itself.

## Summary

The raw node source taxonomy (`en/docs/raw-node-source-taxonomy.md`) groups sources by how a node is reached. Role behaviour depends on something else: what the node's kernel and init system let it do. The two do not line up, so the taxonomy alone cannot tell a role whether to run.

The recommendation under consideration is to keep the source as a raw-stage concern (how to reach the node) and add a node kind that follows the node through every stage (what roles can do on it). Roles would then be gated on capabilities derived from the kind, not on source names or lists of virtualization types.

Three concrete issues exist in the current playbooks:

- `robertdebock.selinux` is gated only on OS family, so a Rocky 9 container would receive it and most likely fail.
- `robertdebock.sysctl` is not gated at all, so host-wide keys (`kernel.*`, `vm.*`, `fs.*`) added later for CIS or STIG compliance will fail in containers.
- The list of container virtualization types is written twice, inline in `10_onboard.yml` and as `normalize_container_types` in `20_normalize.yml`, and the two copies will drift.

## Why source is not enough

Source and kind cut across each other:

- Incus is listed under Container, but it also produces virtual machines (the Rocky 9 test node is an Incus VM) and, in recent versions, OCI application containers.
- Proxmox is listed under Hypervisor, but it produces both LXC containers and QEMU virtual machines.
- Docker is listed under Container, but a Docker container usually has no systemd, no sshd and no lasting identity. It is a workload rather than a node.
- Cloud and bare metal behave alike for most roles, and differ mainly on reboots, time sources and provider-side firewalls.

## Proposed node kinds

| Kind | Examples | What it lacks or changes |
| --- | --- | --- |
| metal | PXE, Ventoy, IPMI | Nothing at kernel level. Reboots are slow and may stop at an encrypted-disk passphrase. |
| vm | Incus VM, Proxmox QEMU, libvirt, cloud instances | Nothing at kernel level. Cloud adds cloud-init behaviour and provider firewalls. |
| system container, unprivileged | Incus and LXD default, Proxmox unprivileged CT | Host-wide kernel settings, kernel modules, audit, clock, SELinux or AppArmor control, console. |
| system container, privileged | LXC privileged, Proxmox privileged CT | About the same as unprivileged, but root inside maps to root on the host. |
| app container | Docker, Podman, Incus OCI | systemd as PID 1, sshd, cron, timers, reboot. Arguably not a node. |

## Effect on the current roles

Statements that a role "most likely fails" are reasoned from how the role works and have not been tested.

| Role | metal / vm | System container | App container |
| --- | --- | --- | --- |
| `bootstrap`, `umask`, `users`, `locale`, `epel` | Fine | Fine, subject to the UID mapping note below | Mostly fine |
| `update`, `auto_update` | Fine, reboot policy matters | Kernel updates do nothing, the host kernel is what counts | Anti-pattern, rebuild the image instead |
| `cron` | Fine | Fine | No init to run it |
| `ntp` | Needed, Debian 13 question still open | Already skipped | Skip |
| `openssh` | Fine | Fine, but cloned images may share host keys | No sshd |
| `fail2ban`, `uc_firewall` | Fine, cloud adds security groups on top | Works in the container's own network namespace only if the host has already loaded the netfilter modules | Docker manages iptables itself |
| `selinux` | Red Hat family only | Not gated, most likely fails on a Rocky container | Not applicable |
| `auditd` | Fine | Already skipped | Skip |
| `sysctl` | Fine | Partly fails: `net.*` keys are per namespace and work, `kernel.*`, `vm.*` and `fs.*` are host-wide and fail | Skip |
| `hostname` and its reboot | Metal reboots can hang at a disk passphrase, cloud-init may reset the hostname at boot | Reboot is a cheap container restart | Runtime sets the hostname, no reboot |
| `rsyslog` | Fine | Fine | Usually pointless |

### Smaller issues

UID mapping: in unprivileged containers, UIDs and GIDs outside the container's ID map cannot be created. LXD's default range is 65,536 IDs, Incus's is larger. This matters only if `robertdebock.users` ever assigns high fixed IDs.

Duplicate identities: Proxmox templates, copied Incus snapshots and cloned VMs can share `/etc/machine-id` and SSH host keys. This is a property of how a node was made, not of its kind, and is worth one clause in the raw node contract.

## Proposed approach: gate on capabilities

The existing playbook comment "An OS family condition is not a source condition" extends naturally: roles should not gate on lists of type names either, but on what the node can do.

### A shared node kind role

A small shared role, provisionally `uc_node_kind`, would run right after fact gathering in onboarding and:

- work out the kind from `ansible_virtualization_type` and `ansible_virtualization_role`, the Incus plugin's instance type where available, `/proc/self/uid_map` (a line of `0 0 4294967295` means not remapped, so privileged or not a container), and whether PID 1 is systemd
- set capability flags such as `uc_cap_kernel`, `uc_cap_clock`, `uc_cap_mac`, `uc_cap_audit`, `uc_cap_reboot` and `uc_cap_init`
- write the result as a local fact in `/etc/ansible/facts.d/uc_node.fact`, so normalize, specialize and audits read the same answer without recomputing it

### Declared and detected kind

Each source could declare an expected kind in its `group_vars`, for example `uc_node_kind_expected: system-container`, and the role would assert that detection agrees. This catches cases such as an Incus source that turns out to be a VM.

### Role gates

Role lines would read like `when: uc_cap_audit` instead of naming virtualization types, and adding a new source would only require answering what kind of node it produces.

### Related variable

`needs_python_bootstrap` is keyed on source but really depends on the image. It works for now and shows the same mismatch.

## Implications for uc-contracts

### Raw node contract

State which kinds are accepted. One option is to require systemd as PID 1 and reject app containers at ingress with a clear assertion, or to move Docker in the taxonomy to a separate workloads branch. Nodes should also declare nesting (Incus `security.nesting`), since it changes what a container may do. Add a clause requiring unique `machine-id` and SSH host keys, or stating that onboarding regenerates them.

### Onboarding egress contract

OE-BAS-07 already excuses containers from time synchronisation. Generalise this so every clause a kind skips is listed against that kind.

### Inherited controls

A container skipping auditd or host-wide sysctls is not a deviation, because the control is provided by the provider host. NIST SP 800-53 describes such controls as inherited from a common control provider <a id="cite-nist-800-53r5"></a>([Joint Task Force, 2020](#ref-nist-800-53r5)), and cloud providers describe the same idea as a shared-responsibility model. The privileged-access policy already applies this to the console (PA-CON clauses covered by PA-ACC-05).

The proposal is an inherited controls table, kept separate from the exceptions register so that the register remains a list of real deviations:

| Container skips | Provider host must provide |
| --- | --- |
| Clock | Time synchronisation |
| auditd | Host audit, which sees container system calls but under host-side IDs, making attribution to a user harder |
| `kernel.*`, `vm.*`, `fs.*` sysctls | The same settings on the host |
| SELinux or AppArmor | Host enforcement |
| Console | PA-ACC-05 |

This also strengthens the case for normalizing provider hosts first: a container's compliance claim is only as good as its host's.

## Open decisions

- Whether to adopt node kind as a second classification alongside source.
- The final list of kinds and capability flags.
- Whether app containers are rejected at ingress or handled by a separate track.
- Whether inherited controls get their own register in uc-contracts.
- Whether the decision record comes before or after a working `uc_node_kind` prototype against `deb13` and the Rocky 9 VM.

## References

<a id="ref-nist-800-53r5"></a>
Joint Task Force. (2020). *Security and privacy controls for information systems and organizations* (NIST Special Publication 800-53, Rev. 5). National Institute of Standards and Technology. https://doi.org/10.6028/NIST.SP.800-53r5
[Return to citation](#cite-nist-800-53r5)
