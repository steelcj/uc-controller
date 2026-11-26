# Multi-Source Raw Inventory: Structure Impact and Option A Review Notes

These notes cover two things: how the inventory structure changes when raw nodes come from more than one source, and the review changes proposed for the Option A document as a result.

## Inventory structure impact

The structure barely changes. The `onboard` and `normalized` layers don't care where a node came from. Once a node is onboarded it is SSH-reachable, it has a hostname, and it is in an environment. Source-specific logic is a `raw`-phase concern only.

What changes is `raw/` getting wider, and the naming convention needing a scope note.

### What changes in raw/

`raw/group_vars/` currently has one source file (`incus.yml`). Multi-source means one per access method:

```text
raw/
├── group_vars/
│   ├── all.yml          # shared: ansible_python_interpreter, etc.
│   ├── incus.yml        # ansible_connection: community.general.incus
│   ├── libvirt.yml      # ansible_connection: libvirt or virsh via proxy
│   ├── proxmox.yml      # proxmox connection or API-driven
│   ├── aws.yml          # ansible_aws_profile, etc.
│   └── discovered.yml   # plain SSH after nmap/DHCP/ARP found it
├── hosts.yml            # static entries, groups by source
├── host_vars/
├── incus.yml            # dynamic inventory or plugin config (stays)
├── aws.yml              # dynamic inventory (new)
└── discovered.yml       # script or static, populated by nmap (new)
```

`raw/hosts.yml` gains groups:

```yaml
all:
  children:
    incus:
      hosts:
        deb13:
        deb12:
        ubu2404:
    libvirt:
      hosts:
        rocky9-vm:
    proxmox:
      hosts:
        fed42-ct:
    aws:
      hosts:
        # populated by aws.yml dynamic inventory, not here
    discovered:
      hosts:
        # populated by discovered.yml or a playbook
```

`raw/` stays flat (no `dev`/`stage` subdirectories). You don't assign an environment until onboarding decides it. A PXE-booted node, a cloud instance, a container you just launched: none have an environment until the onboarding playbook says so.

### What does not change

- `onboard/dev/` and `onboard/stage/` stay exactly as they are. By the time a node reaches onboard, it is SSH-reachable and its source is irrelevant.
- `normalized/` likewise.
- The `host_vars/` directories don't care about source.
- The env split (`dev`/`stage`) is an onboarding decision, not a raw-phase concern.

### The naming convention implication

This is where the taxonomy and the naming document meet. The convention says "name it by its OS." That works for nodes you create (Incus, libvirt, Proxmox, where you pick the name at launch). It doesn't work for nodes you discover:

- An AWS instance has a hostname or an instance ID assigned by AWS.
- A node found by nmap has whatever its existing hostname is.
- A CMDB entry has whatever name the CMDB gives it.

The naming convention governs what **you name**, not what you discover. Discovered nodes carry their source-assigned name through raw and into onboard. If you want to rename them to the OS convention later, that is an onboarding step, and it is the one case where renaming is acceptable because you are doing it once, deliberately, before the inventory entry is written.

So the scope note the document needs:

> This convention applies to instances the controller creates and names (Incus, libvirt, Proxmox, and similar hypervisor-managed guests). Nodes discovered from cloud APIs, network scans, bare-metal provisioning, or external systems carry the name their source assigns them. Renaming a discovered node to the OS convention, if desired, is an onboarding action, not a naming-convention requirement.

### Does raw need env subdirectories now?

No, and arguably even less so. With multiple sources, some nodes might not have a meaningful environment until several onboarding steps later (a cloud instance might be ephemeral, a discovered node might be someone else's). Keeping `raw` env-free is the right call for a broader source set, not just the narrower one.

### One structural question

Does `incus.yml` at the `raw/` root serve as a dynamic inventory plugin config (pointing at an Incus server), or as a static group definition?

If it is the former, the pattern scales cleanly: one config file per source that Ansible merges. If it is the latter, consider folding it into `hosts.yml` groups and reserving the root-level files exclusively for dynamic inventory configs, which keeps the "static groups here, dynamic sources here" distinction sharp as the number of sources grows.

## Option A review: functional changes

> Note: the source for this section was incomplete. The opening of the connection-check item is missing, and the summary table at the end lists three items (persistence model, discovery overwriting `hosts.yml`, playbook-snapshot number alignment) whose detailed write-ups were not in the source.

### Positive connection checks

Check for the connection types that need the step, by name:

```yaml
when: ansible_connection | default('ssh') in ['community.general.incus', 'community.libvirt.libvirt']
```

Or better, use a variable in `group_vars` per source:

```yaml
# raw/group_vars/incus.yml
needs_python_bootstrap: true

# raw/group_vars/raw.yml
needs_python_bootstrap: false
```

Then the playbook condition becomes `when: needs_python_bootstrap | default(false)`. New sources declare their own behavior in their group_vars without touching the playbook logic.

### The discover playbook's hostname derivation is lossy

The `derive unique hostnames from IPs` task replaces non-alphanumeric characters with hyphens. This produces names like `192-168-1-10`, which are valid but meaningless.

If the goal is to match the naming convention, the discovery step should ideally probe the OS (via `raw: cat /etc/os-release` or `raw: uname`) and assign an OS-based name. If that is too aggressive for a discovery step, at minimum the generated names should be marked as provisional, replaced during onboarding when the OS is confirmed.

### firewall_rules accumulation in converge

Both `20_normalize.yml` and `30_specialize.yml` reference `firewall_rules_onboard`. This variable must be defined somewhere the converge playbooks can see it.

The document mentions it lives in `group_vars` as data, but doesn't specify which file. Given the inventory structure, it would need to be in `onboard/<env>/group_vars/all.yml` or `normalized/<env>/group_vars/all.yml`. A one-line note or a comment in the playbook makes the dependency traceable.

## Summary of priority

| Priority | Change | Why |
| --- | --- | --- |
| High | Persistence model for `add_host` / `promote_node.py` | Without this, the workflow is ambiguous and a new operator will get confused |
| High | Discovery overwrites `hosts.yml` | Silent data loss on every discovery run if static entries exist |
| Medium | Positive connection checks | Prevents misclassification as sources grow |
| Medium | Playbook-snapshot number alignment stated | Makes the restore-and-resume workflow discoverable |
| Medium | Raw has no env split, explained | Prevents a future "fix" that breaks the model |
|          |                                                      |                                                              |
