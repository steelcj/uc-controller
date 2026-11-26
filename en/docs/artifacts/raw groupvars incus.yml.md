The structure barely changes. The `onboard` and `normalized` layers don't care where a node came from — once it's onboarded it's SSH-reachable, it has a hostname, it's in an environment. Source-specific logic is a `raw`-phase concern only.

What changes is `raw/` getting wider, and the naming convention needing a scope note.

## What changes in raw/

`raw/group_vars/` currently has one source file (`incus.yml`). Multi-source means one per access method:

text

Copy

```
raw/ ├── group_vars/ │ ├── all.yml # shared: ansible_python_interpreter, etc. │ ├── incus.yml # ansible_connection: community.general.incus │ ├── libvirt.yml # ansible_connection: libvirt or virsh via proxy │ ├── proxmox.yml # proxmox connection or API-driven │ ├── aws.yml # ansible_aws_profile, etc. │ └── discovered.yml # plain SSH after nmap/DHCP/ARP found it ├── hosts.yml # static entries, groups by source ├── host_vars/ ├── incus.yml # dynamic inventory or plugin config (stays) ├── aws.yml # dynamic inventory (new) └── discovered.yml # script or static, populated by nmap (new)
```

`raw/hosts.yml` gains groups:

yaml

Copy

```
all: children: incus: hosts: deb13: deb12: ubu2404: libvirt: hosts: rocky9-vm: proxmox: hosts: fed42-ct: aws: hosts: # populated by aws.yml dynamic inventory, not here discovered: hosts: # populated by discovered.yml or a playbook
```

`raw/` stays flat (no `dev`/`stage` subdirectories). You don't assign an environment until onboarding decides it. A PXE-booted node, a cloud instance, a container you just launched — none have an environment until the onboarding playbook says so.

## What does not change

- `onboard/dev/` and `onboard/stage/` stay exactly as they are. By the time a node reaches onboard, it's SSH-reachable and its source is irrelevant.
- `normalized/` likewise.
- The `host_vars/` directories don't care about source.
- The env split (`dev`/`stage`) is an onboarding decision, not a raw-phase concern.

## The naming convention implication

This is where the taxonomy and the naming doc meet. The convention says "name it by its OS." That works for nodes you create (Incus, libvirt, Proxmox — you pick the name at launch). It doesn't work for nodes you discover:

- An AWS instance has a hostname or an instance ID assigned by AWS.
- A node found by nmap has whatever its existing hostname is.
- A CMDB entry has whatever name the CMDB gives it.

The naming convention governs what **you name**, not what you discover. Discovered nodes carry their source-assigned name through raw and into onboard. If you want to rename them to the OS convention later, that's an onboarding step, and it's the one case where renaming is acceptable because you're doing it once, deliberately, before the inventory entry is written.

So the scope note the document needs:

> This convention applies to instances the controller creates and names (Incus, libvirt, Proxmox, and similar hypervisor-managed guests). Nodes discovered from cloud APIs, network scans, bare-metal provisioning, or external systems carry the name their source assigns them. Renaming a discovered node to the OS convention, if desired, is an onboarding action, not a naming-convention requirement.

## Does `raw` need env subdirectories now?

No, and arguably even less so. With multiple sources, some nodes might not have a meaningful environment until several onboarding steps later (a cloud instance might be ephemeral, a discovered node might be someone else's). Keeping `raw` env-free is the right call for a broader source set, not just the narrower one.

## One structural question

Does `incus.yml` at the `raw/` root serve as a dynamic inventory plugin config (pointing at an Incus server), or as a static group definition? If it's the former, the pattern scales cleanly: one config file per source that Ansible merges. If it's the latter, consider folding it into `hosts.yml` groups and reserving the root-level files exclusively for dynamic inventory configs, which keeps the "static groups here, dynamic sources here" distinction sharp as the number of sources grows.

yaml
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

The `derive unique hostnames from IPs` task replaces non-alphanumeric characters with hyphens. This produces names like `192-168-1-10`, which are valid but meaningless. If the goal is to match the naming convention, the discovery step should ideally probe the OS (via `raw: cat /etc/os-release` or `raw: uname`) and assign an OS-based name. If that's too aggressive for a discovery step, at minimum the generated names should be marked as provisional, replaced during onboarding when the OS is confirmed.

### `firewall_rules` accumulation in converge

Both `20_normalize.yml` and `30_specialize.yml` reference `firewall_rules_onboard`. This variable must be defined somewhere the converge playbooks can see it. The document mentions it lives in `group_vars` as data, but doesn't specify which file. Given the inventory structure, it would need to be in `onboard/<env>/group_vars/all.yml` or `normalized/<env>/group_vars/all.yml`. A one-line note or a comment in the playbook makes the dependency traceable.

## Style and format changes

### Convert to versioned-document format

The document needs frontmatter, a version block, an Abstract, a License section, and a Changelog to match the house standard. The `dc:identifier` would be something like `uc-controller--option-a-single-repo-two-concerns`.

### Remove em dashes

Several instances throughout. Replace with commas or colons per the house rule.

### Remove horizontal rules

The `---` inside the content (between the overview and the repository layout, for instance) violate the no-horizontal-rules rule. Use paragraph breaks.

### Add citations

References to Ansible, Incus, robertdebock roles, and RFC 1123 (if mentioned) need CAP-form citations. At minimum: Ansible documentation, the specific `community.general` collection docs, and the robertdebock role repository.

### Tighten the Tradeoffs table

The table is fine structurally. One addition worth making: a row on "Onboarding as a rename event." Under the naming convention, if a discovered node arrives as `192-168-1-10` and onboarding renames it to `deb13`, that's the one sanctioned rename. The table should acknowledge this is the boundary case where the "never rename" rule is intentionally crossed, so a future reader doesn't think it's an oversight.

## Summary of priority

| Priority | Change | Why |
|----------|--------|-----|
| High | Persistence model for `add_host` / `promote_node.py` | Without this, the workflow is ambiguous and a new operator will get confused |
| High | Discovery overwrites `hosts.yml` | Silent data loss on every discovery run if static entries exist |
| Medium | Positive connection checks | Prevents misclassification as sources grow |
| Medium | Playbook-snapshot number alignment stated | Makes the restore-and-resume workflow discoverable |
| Medium | Raw has no env split, explained | Prevents a future "fix" that breaks the model |
| Low | Style conversion (frontmatter, em dashes, HRs, citations) | House compliance, no functional impact |
