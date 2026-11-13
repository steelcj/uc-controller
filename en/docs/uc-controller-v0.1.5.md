# uc-controller

An Ansible controller configuration that moves nodes through a four stage lifecycle: discover, onboard, normalize, and specialize. Each stage owns its own inventory, its own variables, and its own contribution to the firewall.

## Changelog

### v0.1.4 → v0.1.5

| Change | Description |
|--------|-------------|
| Hostname reboot kept | `hostname_reboot` stays at the role default; `robertdebock.hostname` must stay after `robertdebock.selinux`, which flushes handlers partway through |
| SELinux on the Red Hat family only | `robertdebock.selinux` runs only when `os_family` is `RedHat`; on Debian and Ubuntu it installed a policy, set enforcing and triggered the shared `Reboot` handler |
| Firewall role location | `uc_firewall` moved to `converge/roles/`; `roles/` holds only vendored roles |
| Scaffold removed | `tools/scaffold.yml`, the experimental role-defaults scaffold, was deleted: it wrote a mapping where the firewall plays expect a list, and nothing depended on it |
| Vault guidance | The onboarding guide no longer tells readers to create vault files; the secrets pattern is not decided |

### v0.1.3 → v0.1.4

| Change | Description |
|--------|-------------|
| Option A layout | Playbooks live in `ingress/playbooks/` (discover, onboard) and `converge/playbooks/` (normalize, specialize), `site.yml` at the repository root, `scaffold.yml` in `tools/`; `roles_path` keeps the shared `./roles` first |
| Multi-source raw inventory | `inventories/raw/hosts.yml` is a hand-maintained static file in which each source group is a child of `raw`; hosts come from per-source root-level files; new Raw Inventory section |
| Source group invariant | Every raw host is in `raw` and in exactly one source group; connection settings live in `group_vars/<source>.yml` |
| Incus host names | `host_fqdn: false` in `inventories/raw/incus.yml`, so an instance named `deb13` is the inventory host `deb13`, not `deb13.default.local` |
| Bootstrap opt-out variable | `needs_python_bootstrap: true` in `raw/group_vars/all.yml`; a source opts out only when its images ship Python and sudo |
| Reset helper | `reset_inventories.py` never touches the static `raw/hosts.yml` |
| Discovery output | `00_discover.yml` writes only `inventories/raw/discovered.yml` (subnet) or `cloud.yml` (placeholder), never `hosts.yml`; its directory comes from `raw_inventory`, not `playbook_dir` |
| Provisional names | Discovered hosts are named `disc-<ip>` and carry `name_provisional: true`; a rename-at-onboarding proposal is recorded |
| Scripts find hosts in any static file | `promote_node.py` searches every static inventory file in the source stage; `raw/hosts.yml` is read-only to scripts (`uc_origin: static`) |
| Scripts never add hosts to raw | Demotion to raw removes the host's entry and writes nothing under `inventories/raw/`; the node reappears through its source. Promotion still removes a scanned host from `discovered.yml` |
| Re-onboarding guard | `10_onboard.yml` checks for the `initial` user first and ends the play for a host that is already onboarded; later plays target only the hosts promoted in the run |
| Generated raw files ignored | `inventories/raw/discovered.yml` and `cloud.yml` are in `.gitignore`; live host entries are not committed |
| Script path | `10_onboard.yml` resolves `promote_node.py` from the repository root, as discovery resolves `raw_inventory` |
| Vault placeholders removed | `vaults/` held three unencrypted placeholders; secrets handling is deferred until the first secret exists |
| Bootstrap gate | The bootstrap play runs only when `needs_python_bootstrap` is true |
| Firewall traceability | Converge playbooks name the file each `firewall_rules_<stage>` list lives in |
| Runnable normalize stage | `20_normalize.yml` drops `pam`, `limits`, `motd`, `timezone` and `chrony` (none exists), gates `auditd` off in containers, and runs its controller-side check without become; a time sync proposal is recorded |
| Speed settings | `profile_tasks` on, pipelining, per-user fact cache, fresh facts in the onboard converge play, `forks = 20`, `strategy: free` on the converge plays; measured in the speed overview |
| Firewall rules role | `robertdebock.firewall` read only `firewall_services` and could not restrict sources, so no `firewall_rules` list reached the firewall; it is replaced by the project role `roles/uc_firewall`, which applies `firewall_rules` with ufw or firewalld |
| Persistence and snapshots | New Persistence and Snapshot Alignment sections: what `add_host` does, when `promote_node.py` runs, the snapshot to take after each playbook, and restore-and-resume |
| Listings | Playbook and script listings refreshed from the repository |

### v0.1.2 → v0.1.3

| Fix | Description |
|-----|-------------|
| Indentation | All code blocks, the directory tree, and the lifecycle diagram restored to valid indentation |
| Promotion of every host | Both `add_host` promotion tasks now loop over `ansible_play_hosts`; without the loop only the first host was promoted |
| `raw` group | Discovery now writes hosts into a `raw` group instead of directly under `all`, so `hosts: raw` in `10_onboard.yml` matches them |
| Inventory refresh | Discovery ends with `meta: refresh_inventory` so a full `site.yml` run sees the hosts it has just written |
| Scripts | `promote_node.sh` and `demote_node.sh` replaced by working Python scripts that run on Linux, macOS, and Windows |

### v0.1.1 → v0.1.2

| Fix | Description |
|-----|-------------|
| Firewall rule loss | Usage commands now pass all relevant inventories with `-i` in load-order so stage-namespaced vars are always available |
| Self-referencing vars | Removed recursive `vars:` declarations from `00_discover.yml`; defaults are now inline in tasks |
| Name mismatches | `scaffold_stage` expects `normalized` (matching the tree); `firewall_raw` removed from flow diagram; unused `target_env` removed from usage |
| `wait_for` delegation | All `wait_for` tasks now run on the controller via `delegate_to: localhost` |
| Hostname collisions | Discovery now derives unique hostnames from full IPs instead of first octet |

## Repository Layout

```text
uc-controller/
├── ansible.cfg
├── requirements.yml
├── site.yml                      # chains ingress then converge in one run
│
├── ingress/                      # source-specific: raw node to onboarded node
│   ├── playbooks/
│   │   ├── 00_discover.yml
│   │   ├── 10_onboard.yml
│   │   └── artifacts/            # earlier onboard versions, not run
│   └── roles/
│
├── converge/                     # source-agnostic: reads the onboard contract
│   ├── playbooks/
│   │   ├── 20_normalize.yml
│   │   └── 30_specialize.yml
│   └── roles/
│       └── uc_firewall/          # project firewall role, also used by onboarding
│
├── inventories/
│   ├── raw/                      # flat: no environment split
│   │   ├── hosts.yml             # static, hand-maintained: source groups under raw
│   │   ├── incus.yml             # dynamic plugin config: Incus instances
│   │   ├── discovered.yml        # generated by 00_discover.yml (subnet scan)
│   │   ├── group_vars/
│   │   │   ├── all.yml           # shared raw defaults
│   │   │   ├── incus.yml         # Incus connection as root
│   │   │   └── discovered.yml    # plain SSH as root
│   │   └── host_vars/
│   │
│   ├── onboard/
│   │   ├── dev/
│   │   │   ├── hosts.yml         # written by promote_node.py
│   │   │   ├── group_vars/
│   │   │   │   └── all.yml
│   │   │   └── host_vars/
│   │   └── stage/
│   │       ├── hosts.yml
│   │       ├── group_vars/
│   │       │   └── all.yml
│   │       └── host_vars/
│   │
│   └── normalized/
│       ├── dev/
│       │   ├── hosts.yml
│       │   ├── group_vars/
│       │   │   ├── all.yml
│       │   │   └── webservers.yml
│       │   └── host_vars/
│       └── stage/
│           ├── hosts.yml
│           ├── group_vars/
│           │   └── all.yml
│           └── host_vars/
│
├── roles/                        # vendored Galaxy roles, shared by both concerns
│
├── scripts/
│   ├── promote_node.py
│   ├── demote_node.py
│   ├── reset_inventories.py
│   └── check_converge_boundary.py
```

A `prod` environment, when it exists, follows the same pattern as `dev` and `stage` under `onboard/` and `normalized/`. Secrets handling is deferred until the first secret exists; the earlier `vaults/` placeholders held none and were removed.

## Raw Inventory

The raw inventory describes nodes as their source provides them, before onboarding has given them an `initial` user and SSH. Source differences end here: once a node is onboarded it is reached over SSH as `initial`, and the onboard and normalized inventories do not care where it came from.

### Layout

| File | Kind | Written by |
|------|------|------------|
| `hosts.yml` | Static inventory | Hand. No playbook or script writes to it. |
| `incus.yml` | Dynamic inventory plugin config (`community.general.incus`) | Hand. The plugin generates the hosts at run time. |
| `discovered.yml` | Generated inventory, `discovered` group | `00_discover.yml` (subnet scan, overwritten each run). `promote_node.py` removes a host from it when promoting that host. Ignored by git. |
| `cloud.yml` | Generated inventory, `cloud` group, placeholder | The cloud branch of `00_discover.yml`. Not a child of `raw`, so not onboarded. Ignored by git. |
| `group_vars/all.yml` | Shared defaults for every source | Hand |
| `group_vars/<source>.yml` | How that source's nodes are reached | Hand |

Root-level files in `inventories/raw/` are reserved for host sources, either a dynamic plugin config or a generated inventory, and each starts with a header comment stating which it is and what writes it. Groups are declared only in `hosts.yml`.

### The Source Group Invariant

Every raw host is a member of `raw` and of exactly one source group. `hosts.yml` declares each source group as a child of `raw`:

```yaml
raw:
  children:
    incus: {}       # Incus instances, from incus.yml
    discovered: {}  # SSH-reachable nodes found by 00_discover.yml
```

A source puts its hosts into its own group and never into `raw` directly. `10_onboard.yml` targets `hosts: raw`, so it reaches every source through the child groups, and it gets each node's connection settings from `group_vars/<source>.yml`. The Incus plugin's default groups (`incus`, `incus_<remote>`, `incus_<remote>_<project>`) supply the `incus` membership, and the plugin config has no `groups: raw: true`.

### Raw Images Are the Lightest Variant

A raw node starts from the lightest image of whatever OS is targeted. For Incus that is the `default` variant from the `images:` remote: `images:debian/13` for `deb13` and `images:ubuntu/24.04` for `ubu2404`, the latter being `ubuntu-minimal` with no cloud-init, snapd, or desktop. The `cloud` and `desktop` variants and Canonical's server images carry more than raw needs. Anything beyond the minimal base is the lifecycle's job, and a desktop, if a node needs one, is added in the specialize stage. Snapshot the instance as `raw` before Ansible touches it.

### Why raw Has No Environment Split

`onboard/` and `normalized/` are split by environment, and `raw/` is not. A raw node has no environment until onboarding assigns one: the onboard inventory you pass with `onboard_inventory` decides it. A container just launched, a cloud instance, or a node found by a scan may never belong to any environment, and some will be someone else's. Splitting `raw/` by environment would force that decision before the node is even reachable as `initial`, and would duplicate every source config per environment. Do not add `raw/dev/` or `raw/stage/`.

### Adding a Source

Add a source only when there is a node to test it against.

- Add the group under `raw.children` in `hosts.yml`.
- Add `group_vars/<source>.yml` with the connection settings (`ansible_connection`, `ansible_user`, and anything else the source needs). Set `needs_python_bootstrap: false` there only if the source's images are known to ship both Python and sudo.
- Add the root-level file that supplies the hosts: a plugin config named as the plugin requires, or a generated inventory. Give it a header comment saying which it is and what writes it, and make it put hosts only in the source group.
- Confirm with `ansible-inventory -i inventories/raw --graph` that the new hosts appear under `raw` and the source group, and with `--host` that they get the source's connection settings.

Nothing in `onboard/`, `normalized/`, or the converge playbooks changes.

### Scripts Never Add Hosts to Raw

Raw is what the sources report: the Incus plugin, the hand-maintained `hosts.yml`, and the scan's `discovered.yml`. No script adds a host to any file under `inventories/raw/`.

- Promotion out of raw removes a scanned host from `discovered.yml`, so the host is not listed in two stages until the next scan. This is the only case where a script changes a raw file.
- A host entered by hand in `hosts.yml` is copied on promotion, not moved, and marked `uc_origin: static`. A plugin host is created from `--address` and marked `uc_origin: plugin`.
- Demotion to raw removes the host's entry from the onboard (or normalized) inventory and writes nothing. The node reappears in raw through its source: the plugin lists a running Incus instance, a hand-entered host never left `hosts.yml`, and a scanned host is found by the next scan.

Demotion is inventory bookkeeping. It exists so the inventory can follow a node after a snapshot restore, and it has nothing to do with making onboarding repeatable. Onboarding is one-shot; see Re-onboarding Guard.

## Variable Precedence

```text
inventories/normalized/<env>/host_vars/<host>.yml     ← highest
inventories/normalized/<env>/group_vars/<group>.yml
inventories/normalized/<env>/group_vars/all.yml
inventories/onboard/<env>/group_vars/all.yml
inventories/raw/group_vars/all.yml
roles/<role>/defaults/main.yml                        ← lowest
```

Within a single inventory this follows Ansible's documented order, in which role defaults are the most easily overridden, inventory `group_vars/all` sits above them, more specific `group_vars` files sit above that, and `host_vars` sit higher still <a id="cite-ansible-variables"></a>([Ansible project contributors, n.d.-f](#ref-ansible-variables)).

The ordering across the raw, onboard, and normalized inventories applies only when those inventories are loaded together in the same run. Ansible loads inventory sources in the order they are supplied, and when the same variable is defined more than once the last definition wins <a id="cite-ansible-inventory"></a>([Ansible project contributors, n.d.-e](#ref-ansible-inventory)). An inventory that is not passed to a run contributes no variables to it.

### Critical Constraint

Ansible variable precedence **replaces** lists, it does not merge them. If `firewall_rules` is defined in both onboard and normalized `group_vars/all.yml`, the higher-precedence definition wins and the lower one vanishes silently. The default `hash_behaviour` is `replace`, and even the optional `merge` setting applies only to dictionaries, never to lists; the documentation recommends avoiding reused variable names and building merged values explicitly instead <a id="cite-ansible-config"></a>([Ansible project contributors, n.d.-c](#ref-ansible-config)). This is why stage-namespaced variables are required (see Firewall Layering below).

## Firewall Layering

### The Problem

Ansible's variable precedence operates on a replace basis for lists. You cannot rely on `group_vars` inheritance to accumulate firewall rules across lifecycle stages. The higher-precedence file overwrites the lower one entirely.

### The Solution: Stage-Namespaced Variables

Each stage owns its own firewall rules under a **distinct variable name**. The playbook combines them at play time into the role's expected input (`firewall_rules`). This preserves idempotency: re-running normalize or specialize always produces the same complete rule set because the role sees the full picture, not a delta.

### Variable Placement

```yaml
# inventories/onboard/dev/group_vars/all.yml
firewall_rules_onboard:
  - name: allow-ssh
    port: 22
    protocol: tcp
```

```yaml
# inventories/normalized/dev/group_vars/all.yml
firewall_rules_normalize:
  - name: allow-monitoring
    port: 9100
    protocol: tcp
    source: 10.0.0.0/24
```

```yaml
# inventories/normalized/dev/group_vars/webservers.yml
firewall_rules_specialize:
  - name: allow-http
    port: 80
    protocol: tcp
    source: 0.0.0.0/0
  - name: allow-https
    port: 443
    protocol: tcp
    source: 0.0.0.0/0
```

### Combine Expression

```yaml
vars:
  firewall_rules: >-
    {{
      (firewall_rules_onboard | default([]))
      + (firewall_rules_normalize | default([]))
      + (firewall_rules_specialize | default([]))
    }}
```

`uc_firewall` runs against the merged list. Run it once or ten times, same result, idempotent.

**Important:** the `default([])` guards only prevent a template error when a variable is undefined. They do not recover rules from an inventory that was not loaded. All inventories contributing rules must be passed with `-i` in the correct order. See Usage below.

### Why This Works

- **Onboard** knows it needs SSH. That's all it knows.
- **Normalize** knows it needs monitoring. It doesn't care about SSH.
- **Specialize** knows it needs ports 80/443. It doesn't care about monitoring.
- **None of them know the full picture individually.** The combine at play time is the convergence.

The firewall settings live with the stage that owns them. The role only ever runs against the merged result. That's layering without overwrite.

### The Firewall Role

`uc_firewall` is a project role, not a vendored one. It lives in `converge/roles/`. `roles_path` is shared, so `10_onboard.yml` resolves it too. It replaced `robertdebock.firewall`, which read only `firewall_services` and could not restrict a rule's source address.

#### Rule Schema

| Key | Required | Meaning |
|-----|----------|---------|
| `name` | yes | Rule name, used as the rule comment |
| `port` | yes | Port number |
| `protocol` | no | `tcp` (default) or `udp` |
| `source` | no | Address or network allowed to connect. A rule without `source` is open to all addresses. |

#### Behaviour

- Backend per OS family, the same one `robertdebock.firewall` installed, so nothing else on the node changes: ufw on the Debian family (Debian, Ubuntu) through `community.general.ufw`, firewalld on the Red Hat family through `ansible.posix.firewalld`, with a rich rule for each rule that has a `source`. The firewalld path has not been tested, because there is no Red Hat family test node.
- SSH safety: before anything is enabled, the role asserts that `firewall_rules` contains a TCP rule for the SSH port in use (`uc_firewall_ssh_port`, default `ansible_port` or 22), and fails with a message naming the file to fix if it does not. `firewall_rules_onboard` in `inventories/onboard/<env>/group_vars/all.yml` holds that rule.
- Order: allow rules first, then the default policy (deny incoming, allow outgoing), then the firewall is enabled, so the default deny never takes effect before the allow rules exist.

#### Known Limitation

The role is additive. It adds and keeps the rules in the list, and it never removes a rule that is missing from the list. Deleting a rule from `firewall_rules_<stage>` leaves it on nodes that already have it; remove it by hand (`ufw delete allow ...`) or rebuild the node from its snapshot.

## Playbooks

### 00_discover.yml

Find raw nodes and write them to a generated inventory file. Supports subnet scanning (nmap) and a cloud API placeholder. Lives in `ingress/playbooks/`.

The subnet scan writes only `inventories/raw/discovered.yml`, under the `discovered` group, and overwrites it on every run. It never writes the hand-maintained `hosts.yml`. The cloud placeholder writes its own `cloud.yml`. The target directory comes from `raw_inventory` (default `inventories/raw`), resolved against the directory `ansible-playbook` is started from, so it does not depend on where the playbook lives. Hosts get provisional names (`disc-<ip>`) and `name_provisional: true`.

Parameters are passed via `-e` and consumed inline with `| default()` filters. No recursive `vars:` declarations.

Discovered hosts are written into the `discovered` group, which `hosts.yml` declares as a child of `raw`, so `hosts: raw` in the onboard play matches them. The play ends with `meta: refresh_inventory` because inventory is read once at startup; without the refresh, a full `site.yml` run would not see the hosts it has just written.

```yaml
#!/usr/bin/env ansible-playbook
---
# Find raw nodes and write them to a generated inventory file.
#
# Discovery never writes inventories/raw/hosts.yml, which is hand-maintained.
# Each source writes only its own root-level file in inventories/raw/:
#   subnet -> discovered.yml, hosts in the discovered group
#   cloud  -> cloud.yml (placeholder, not wired into raw; see below)
#
# The directory comes from raw_inventory (default inventories/raw), resolved
# against the directory ansible-playbook is started from, which is the
# repository root. It does not depend on where this playbook lives.
#
# Generated names are provisional: disc-<ip with dots as hyphens>, with
# name_provisional: true on the host. Renaming is not done here.

- name: discover raw nodes
  hosts: localhost
  gather_facts: no
  become: no

  vars:
    discover_raw_dir: "{{ raw_inventory | default('inventories/raw') | ansible.builtin.realpath }}"

  tasks:
    - name: scan subnet for SSH-capable hosts
      command: "nmap -sn -oG - {{ discover_subnet | default('192.168.1.0/24') }}"
      register: scan_results
      changed_when: false
      when: (discover_source | default('subnet')) == 'subnet'

    - name: parse discovered hosts
      set_fact:
        discovered_hosts: >-
          {{
            scan_results.stdout_lines
            | select('match', '^Host:')
            | map('regex_replace', '^Host: (\S+).*', '\1')
            | list
          }}
      when: (discover_source | default('subnet')) == 'subnet'

    - name: derive provisional hostnames from IPs
      set_fact:
        discovered_named: >-
          {{
            discovered_hosts
            | map('replace', '.', '-')
            | map('regex_replace', '^', 'disc-')
            | zip(discovered_hosts)
            | list
          }}
      when: (discover_source | default('subnet')) == 'subnet'

    # Overwritten on every subnet scan. ansible_connection and ansible_user
    # come from raw/group_vars/discovered.yml.
    - name: write the discovered inventory from the subnet scan
      copy:
        dest: "{{ discover_raw_dir }}/discovered.yml"
        content: |
          # inventories/raw/discovered.yml
          #
          # Generated inventory, written by ingress/playbooks/00_discover.yml and
          # overwritten on every subnet scan. promote_node.py removes a host from it
          # when promoting that host. Not committed. Do not edit by hand.
          # Names are provisional (disc-<ip>) until onboarding.
          discovered:
          {% if discovered_named | length == 0 %}
            hosts: {}
          {% else %}
            hosts:
          {% for pair in discovered_named %}
              {{ pair[0] }}:
                ansible_host: {{ pair[1] }}
                name_provisional: true
          {% endfor %}
          {% endif %}
      when: (discover_source | default('subnet')) == 'subnet'

    - name: query cloud API for instances
      uri:
        url: "{{ cloud_api_url }}/instances"
        method: GET
        return_content: yes
        headers:
          Authorization: "Bearer {{ cloud_api_token }}"
      register: cloud_instances
      when: (discover_source | default('subnet')) == 'cloud'

    # Placeholder, not developed further. It writes its own file so it cannot
    # clobber anything. The cloud group is not a child of raw in hosts.yml,
    # so these hosts are not onboarded until a cloud source is added.
    - name: write the cloud placeholder inventory
      copy:
        dest: "{{ discover_raw_dir }}/cloud.yml"
        content: |
          # inventories/raw/cloud.yml
          #
          # Generated inventory, written by the cloud placeholder in
          # ingress/playbooks/00_discover.yml. Not committed. Not wired into raw.
          cloud:
            hosts:
          {% for instance in cloud_instances.json %}
              {{ instance.name }}:
                ansible_host: {{ instance.private_ip }}
                ansible_user: root
          {% endfor %}
      when: (discover_source | default('subnet')) == 'cloud'

    - name: reload inventory so later plays see the discovered hosts
      meta: refresh_inventory
```

### 10_onboard.yml

Make it manageable. Lives in `ingress/playbooks/`. It requires `-e onboard_inventory=inventories/onboard/<env>` and fails at once without it.

- Play 1 first skips any node that is already onboarded (see Re-onboarding Guard), then probes each raw node with `raw: 'true'` over whatever connection its source provides, and promotes it into `onboarding` and `onboarded` in memory.
- Play 2 runs `robertdebock.bootstrap` (Python and sudo) when `needs_python_bootstrap` is true, still over the source connection as root.
- Play 3 converges the onboarding baseline, including the `initial` user.
- Play 4 re-targets the node over SSH as `initial` with the full connection contract.
- Play 5 confirms SSH and sudo as `initial`.
- Play 6 persists the promotion by calling `promote_node.py` (see Persistence).

Promotion uses `add_host`, which adds hosts and groups to the in-memory inventory so that later plays in the same playbook run can target them <a id="cite-ansible-add-host"></a>([Ansible project contributors, n.d.-a](#ref-ansible-add-host)). `add_host` runs once per play rather than once per host, so the task loops over `ansible_play_hosts` to promote every node. That list holds only the hosts still active in the play, so a node that failed a check is not promoted or persisted.

```yaml
#!/usr/bin/env ansible-playbook
---
# Make raw nodes manageable.
#
# A raw node is reached however discovery left it: an Incus instance over the
# incus connection as root, or a bare-metal/VPS node over SSH as root. Neither
# has the "initial" user or sshd-as-initial yet; creating them is this stage's
# job. So the onboard plays run over that root connection, and only at the end
# is the connection switched to SSH as "initial" for the stages that follow.
#
# The connection and user for each raw node come from its inventory
# (inventories/raw/group_vars/incus.yml sets ansible_connection and
# ansible_user for the Incus group). This playbook carries those through
# promotion rather than assuming SSH.

- name: Confirm raw nodes are reachable and promote them
  hosts: raw
  gather_facts: no
  become: no

  tasks:
    # Re-onboarding guard. Onboarding is one-shot, and an onboarded Incus
    # instance stays in raw for as long as it runs, because the plugin lists
    # it. If the initial user already exists, the node has been onboarded:
    # say so and end the play for that host only. raw needs no Python, and an
    # unreachable node is left to the readiness probe below.
    - name: check whether the node is already onboarded
      ansible.builtin.raw: id initial
      register: onboarded_probe
      failed_when: false
      changed_when: false
      ignore_unreachable: true

    - name: report a node that is already onboarded
      ansible.builtin.debug:
        msg: >-
          {{ inventory_hostname }} is already onboarded (the initial user
          exists); skipping it. Restore it to its raw snapshot and demote its
          inventory entry to onboard it again.
      when: onboarded_probe.rc | default(1) == 0

    - name: end the play for a node that is already onboarded
      ansible.builtin.meta: end_host
      when: onboarded_probe.rc | default(1) == 0

    # The last play writes each promoted host into the onboard inventory, so
    # the destination has to be named up front. It is passed in, not derived
    # from playbook_dir, so it does not depend on where this file lives.
    - name: require the onboard inventory and key file
      ansible.builtin.assert:
        that:
          - onboard_inventory is defined
          - onboard_inventory | length > 0
          - onboard_ssh_private_key_file is defined
        fail_msg: >-
          Set onboard_inventory to the onboard inventory for this environment,
          for example -e onboard_inventory=inventories/onboard/dev, and load
          that inventory with -i so onboard_ssh_private_key_file is defined.
        quiet: true

    # raw runs over whatever connection the node uses and needs no Python, so
    # it is a readiness probe that works for both Incus (already up) and an
    # SSH root node (retried until sshd answers). This replaces the old
    # wait_for port 22, which a raw Incus node without sshd can never pass.
    - name: wait for the node to accept a connection
      ansible.builtin.raw: 'true'
      register: probe
      retries: 10
      delay: 6
      until: probe is succeeded
      changed_when: false

    # Promoted nodes join two in-memory groups. onboarding holds only the
    # nodes promoted in this run, and the later plays here target it, so a
    # node already listed in the onboard inventory's onboarded group is not
    # touched again. onboarded is what 20_normalize.yml targets when it is
    # chained in the same run through site.yml.
    #
    # add_host runs once per play, so loop over ansible_play_hosts to promote
    # every node still active in the play. The connection vars are carried
    # across with default(omit) so an Incus node keeps its incus connection and
    # an SSH node keeps the ansible_host from its inventory.
    - name: promote reachable nodes to onboarded
      ansible.builtin.add_host:
        name: "{{ item }}"
        groups:
          - onboarding
          - onboarded
          - "{{ target_group | default('ungrouped') }}"
        ansible_connection: "{{ hostvars[item].ansible_connection | default(omit) }}"
        ansible_user: "{{ hostvars[item].ansible_user | default(omit) }}"
        ansible_host: "{{ hostvars[item].ansible_host | default(omit) }}"
      loop: "{{ ansible_play_hosts }}"

- name: Bootstrap Python onto onboarded nodes
  hosts: onboarding
  gather_facts: no          # Python is not present yet; bootstrap installs it.
  become: no                # Already root over the incus/ssh-root connection.

  vars:
    # sudo may not be installed on a minimal image, and it is not needed while
    # the connection is already root. The later ssh-as-initial stages turn
    # become back on.
    bootstrap_become: false

  roles:
    # needs_python_bootstrap defaults to true in raw/group_vars/all.yml. A
    # source opts out in its own group_vars only when its images ship both
    # Python and sudo; the users role later in this playbook needs sudo.
    - role: robertdebock.bootstrap
      when: needs_python_bootstrap | default(true) | bool

- name: Converge the onboard baseline
  hosts: onboarding
  gather_facts: no          # Gathered fresh by the setup pre_task below.
  become: no                # Still root over the root connection.

  # Always gather fresh facts here, never from the cache. Instance names are
  # reused across rebuilds, and the SSH switch below takes the node's address
  # from these facts; under gathering = smart a cached fact from an earlier
  # instance of the same name could point at a stale address. Python is
  # present now, installed by bootstrap above.
  pre_tasks:
    - name: gather fresh facts
      ansible.builtin.setup:

  vars:
    firewall_rules: >-
      {{
        (firewall_rules_onboard | default([]))
      }}

  # No sudo pre_task is needed: robertdebock.bootstrap already installs sudo
  # (its Debian package set is "python3 sudo gnupg python3-apt"), which is why
  # the users role can rely on visudo and write /etc/sudoers.d/initial.

  roles:
    # Set a tight system-wide umask before any user is created, so the initial
    # user's home directory is created with the intended permissions. The umask
    # values live in inventories/onboard/<env>/group_vars/all.yml.
    - role: steelcj.umask
    - role: robertdebock.epel
    - role: robertdebock.update
    - role: robertdebock.locale
    - role: robertdebock.auto_update
    - role: robertdebock.cron
    # Containers take their clock from the host and usually cannot set time,
    # so skip ntp there. This also sidesteps Debian trixie dropping the 'ntp'
    # package; real VMs and bare metal on trixie need a time-sync rethink
    # (chrony or systemd-timesyncd), tracked separately.
    - role: robertdebock.ntp
      when: ansible_facts['virtualization_type'] | default('') not in ['lxc', 'lxd', 'incus', 'docker', 'podman', 'systemd-nspawn', 'container', 'openvz']
    - role: robertdebock.openssh      # installs and hardens sshd
    - role: robertdebock.fail2ban
    - role: uc_firewall               # applies firewall_rules; refuses without the SSH rule
    - role: robertdebock.users        # creates the initial user + sudo + key

- name: Switch onboarded nodes to SSH as the initial user
  hosts: onboarding
  gather_facts: no
  become: no

  tasks:
    # After this play the node is reached over SSH as initial, which is what
    # 20_normalize.yml and later stages expect. The management address is the
    # fact gathered in the previous play; fall back to any inventory
    # ansible_host, then the inventory name.
    - name: re-target the node over SSH as initial
      ansible.builtin.add_host:
        name: "{{ item }}"
        groups:
          - onboarded
        ansible_connection: ssh
        ansible_user: initial
        ansible_ssh_private_key_file: "{{ onboard_ssh_private_key_file }}"
        # Offer only the key above. Otherwise agent keys are tried first, can
        # exhaust sshd's MaxAuthTries, and get the controller banned by fail2ban.
        ansible_ssh_common_args: "-o IdentitiesOnly=yes"
        ansible_host: >-
          {{
            hostvars[item].ansible_default_ipv4.address
            | default(hostvars[item].ansible_host)
            | default(item)
          }}
      loop: "{{ ansible_play_hosts }}"

- name: Confirm SSH as the initial user works
  hosts: onboarding
  gather_facts: no
  become: yes               # initial has passwordless sudo

  tasks:
    - name: wait for SSH to answer as initial
      ansible.builtin.wait_for_connection:
        timeout: 60

    - name: confirm sudo works for initial
      ansible.builtin.command: id
      changed_when: false
      register: initial_id

    - name: show who we are now
      ansible.builtin.debug:
        msg: "{{ inventory_hostname }}: {{ initial_id.stdout }}"

- name: Persist the promotion to the onboard inventory
  hosts: onboarding
  gather_facts: no
  become: no

  vars:
    # Paths are resolved on the controller against the directory
    # ansible-playbook was started from, which is the repository root, the
    # same way 00_discover.yml resolves raw_inventory. They do not depend on
    # where this playbook lives.
    promote_script: "{{ uc_scripts_dir | default('scripts') | ansible.builtin.realpath }}/promote_node.py"
    promote_from: "{{ raw_inventory | default('inventories/raw') | ansible.builtin.realpath }}"
    promote_to: "{{ onboard_inventory | ansible.builtin.realpath }}"

  tasks:
    # promote_node.py is the only code that writes hosts.yml entries. One
    # run_once task looping over the play's hosts serializes the writes, so
    # several nodes finishing together cannot race on the same file. become
    # is off because ansible.cfg enables it globally and this writes to the
    # operator's own working tree. The commit is left to the operator.
    # The key path comes from the inventory variable, not from
    # ansible_ssh_private_key_file, which Ansible expands to an absolute path
    # once connected; the unexpanded ~/ form stays valid on other controllers.
    # expand_argument_vars is off because the command module otherwise expands
    # ~ in arguments before the script sees them.
    - name: write each promoted host and its connection contract
      ansible.builtin.command:
        expand_argument_vars: false
        argv: >-
          {{
            [ansible_playbook_python, promote_script,
             '--from', promote_from,
             '--to', promote_to,
             '--host', item,
             '--address', hostvars[item].ansible_host,
             '--key-file', hostvars[item].onboard_ssh_private_key_file,
             '--no-commit']
            + (['--group', target_group] if target_group is defined else [])
          }}
      loop: "{{ ansible_play_hosts }}"
      run_once: true
      delegate_to: localhost
      become: no
```

### 20_normalize.yml

Make it compliant. Lives in `converge/playbooks/`. Validates onboarded nodes, promotes them into the `normalized` group in memory, and converges the compliance baseline. Promotion is not persisted yet; run `promote_node.py` by hand afterwards (see Persistence).

#### Role List

| Role | Status |
|------|--------|
| `robertdebock.selinux` | Red Hat family only. On Debian and Ubuntu, which use AppArmor, its defaults installed the SELinux policy, set enforcing and notified a reboot |
| `robertdebock.auditd` | Skipped in containers, where `auditd.service` is masked; runs on VMs and bare metal. Untested so far, because both test nodes are containers |
| `robertdebock.sysctl` | Runs. No settings are defined yet |
| `robertdebock.hostname` | Runs, after `selinux`. Reboots the node when the hostname changes (`hostname_reboot` at its default, true) |
| `robertdebock.rsyslog` | Runs |
| `uc_firewall` | Runs. Adds `firewall_rules_normalize` |
| `pam`, `limits`, `motd` | Removed. There is no role of that name and no stated requirement, and no configuration is invented |
| `timezone` | Removed. The onboard stage sets the timezone through `locale_timezone` and `ntp_timezone` |
| `chrony` | Removed. See Time Sync |

Run with `failed=0` on `deb13` and `ubu2404` from `10-onboarded`; the monitoring rule is present with its `10.0.0.0/24` source restriction.

#### Reboots and Role Order

`robertdebock.hostname` reboots the node through a handler when it changes the hostname. A reboot after a hostname change is wanted, so `hostname_reboot` stays at its default. Handlers normally run at the end of the play, but `robertdebock.selinux` calls `flush_handlers` partway through its own tasks. `hostname` must therefore stay after `selinux` in the role list, or its reboot would fire mid-play.

Handler names are shared by every role in a play. `robertdebock.selinux` notifies a handler called `Reboot` when it changes the SELinux state, and `robertdebock.hostname` defines one of the same name. Before SELinux was limited to the Red Hat family, this reboot ran on every Debian and Ubuntu normalize run, labelled `robertdebock.hostname : Reboot` even though the hostname had not changed: SELinux had triggered it.

#### Time Sync (Proposal)

Not implemented. Today `robertdebock.ntp` runs in `10_onboard.yml` and is skipped in containers.

- Containers take their clock from the host and usually cannot set it. Leave time sync off there, as now.
- VMs and bare metal need a client. Debian 13 no longer ships the `ntp` package, so `robertdebock.ntp` cannot be the answer on trixie. Use `systemd-timesyncd` (present on Debian and Ubuntu, a client only) or `chrony` (also the Red Hat default, and able to serve time). The likely choice is chrony everywhere outside containers, from a vendored role or a small project role, configured from one `time_servers` list.
- It belongs in normalize, not onboard: onboarding only needs a clock good enough for package signatures, which the image provides.
- Remove `robertdebock.ntp` from onboarding once the normalize role exists, and test on a VM node.

```yaml
#!/usr/bin/env ansible-playbook
---
- name: validate and promote onboarded nodes
  hosts: onboarded
  gather_facts: no
  # ansible.cfg turns become on globally; the reachability check runs on the
  # controller, where sudo would need a password.
  become: no

  tasks:
    - name: confirm reachability
      wait_for:
        host: "{{ ansible_host | default(inventory_hostname) }}"
        port: 22
        timeout: 10
      delegate_to: localhost

    - name: promote to normalized group
      add_host:
        name: "{{ item }}"
        ansible_host: "{{ hostvars[item].ansible_host | default(item) }}"
        groups:
          - normalized
          - "{{ target_group | default('ungrouped') }}"
      loop: "{{ ansible_play_hosts }}"

- name: converge normalized baseline
  hosts: normalized
  become: yes
  gather_facts: yes
  # Each node converges independently, so a slow node does not hold the
  # others at every task. The config default stays linear; the validation
  # play above keeps it for its add_host loop.
  strategy: free

  vars:
    # Where each stage's list is expected to live (loaded only when that
    # inventory is passed with -i):
    #   firewall_rules_onboard    inventories/onboard/<env>/group_vars/all.yml
    #   firewall_rules_normalize  inventories/normalized/<env>/group_vars/all.yml
    # converge/roles/uc_firewall applies the combined list (see Firewall Layering in
    # en/docs/uc-controller-v0.1.4.md).
    firewall_rules: >-
      {{
        (firewall_rules_onboard | default([]))
        + (firewall_rules_normalize | default([]))
      }}
    # Container virtualization types, as in the ntp gate in 10_onboard.yml.
    # Roles that need the kernel or host access a container does not have are
    # skipped there; VMs and bare metal run them.
    normalize_container_types: ['lxc', 'lxd', 'incus', 'docker', 'podman', 'systemd-nspawn', 'container', 'openvz']

  # Removed, none of them exists in requirements.yml: pam, limits and motd
  # (no stated requirement; no configuration is invented), timezone (the
  # onboard stage sets it through locale_timezone and ntp_timezone), and
  # chrony (time sync is a pending proposal; see Time Sync in
  # en/docs/uc-controller-v0.1.4.md).
  # Role order matters for the reboot. robertdebock.hostname reboots the node
  # through a handler when the hostname changes (hostname_reboot is left at
  # the role default, true). Handlers run at the end of the play, but
  # robertdebock.selinux flushes handlers partway through its own tasks, so
  # hostname must stay after selinux or its reboot would fire mid-play.
  # Handler names are shared across roles: selinux also notifies Reboot.
  roles:
    # SELinux only on the Red Hat family. On Debian and Ubuntu, which use
    # AppArmor, the role's defaults would install a policy, set enforcing and
    # reboot. An OS family condition is not a source condition.
    - role: robertdebock.selinux
      when: ansible_facts['os_family'] == 'RedHat'
    # auditd needs the kernel audit subsystem, which a container cannot use
    # (the service is masked there).
    - role: robertdebock.auditd
      when: ansible_facts['virtualization_type'] | default('') not in normalize_container_types
    - role: robertdebock.sysctl
    - role: robertdebock.hostname
    - role: robertdebock.rsyslog
    - role: uc_firewall
```

### 30_specialize.yml

Make it useful. Applies the role-specific composition and the complete firewall state.

```yaml
#!/usr/bin/env ansible-playbook
---
- name: specialize normalized nodes
  hosts: normalized
  become: yes
  gather_facts: yes
  # Each node converges independently; the config default stays linear.
  strategy: free

  vars:
    # Where each stage's list is expected to live (loaded only when that
    # inventory is passed with -i):
    #   firewall_rules_onboard    inventories/onboard/<env>/group_vars/all.yml
    #   firewall_rules_normalize  inventories/normalized/<env>/group_vars/all.yml
    #   firewall_rules_specialize inventories/normalized/<env>/group_vars/<group>.yml
    #                             (for example webservers.yml)
    # roles/uc_firewall applies the combined list (see Firewall Layering in
    # en/docs/uc-controller-v0.1.4.md).
    firewall_rules: >-
      {{
        (firewall_rules_onboard | default([]))
        + (firewall_rules_normalize | default([]))
        + (firewall_rules_specialize | default([]))
      }}

  roles:
    - role: "{{ specialize_role }}"
    - role: uc_firewall
```

### site.yml

Full converge, chains all lifecycle stages for a given environment. Each stage is pulled in with `import_playbook`, which can only be used at the top level of a playbook and not inside a play <a id="cite-ansible-import-playbook"></a>([Ansible project contributors, n.d.-b](#ref-ansible-import-playbook)).

```yaml
#!/usr/bin/env ansible-playbook
---
- import_playbook: ingress/playbooks/00_discover.yml
- import_playbook: ingress/playbooks/10_onboard.yml
- import_playbook: converge/playbooks/20_normalize.yml
- import_playbook: converge/playbooks/30_specialize.yml
```

## Persistence

### What add_host Does

The playbooks move a node between groups with `add_host`. That changes only the in-memory inventory of the current `ansible-playbook` run <a id="cite-ansible-add-host-2"></a>([Ansible project contributors, n.d.-a](#ref-ansible-add-host)). Later plays in the same run see the node in its new group, and nothing is written to disk. `site.yml` works because every stage runs in one invocation. Separate invocations do not see each other's promotions.

### When promote_node.py Runs

- After `10_onboard.yml`: automatically. The playbook's last play calls `promote_node.py` once for all hosts that passed the SSH check, with `--address`, `--key-file`, `--no-commit` and `--group` when `target_group` is set. It writes each host and its connection contract into the onboard inventory named by `onboard_inventory`. The change is left uncommitted for the operator to review.
- After `20_normalize.yml`: by hand, until normalize gains its own persist play. Run `promote_node.py --from inventories/onboard/<env> --to inventories/normalized/<env> --host <host>` for each node that converged.
- After a snapshot restore: run `demote_node.py` so the inventory matches the restored node (see Restore and Resume).

### What Is Lost If It Is Skipped

- The onboard inventory has no entry for the node, so a separate converge run does not find it in `onboarded`.
- The connection contract is not on disk. Loaded together with raw, an Incus node falls back to the Incus connection as root. A discovered node falls back to SSH as root, which onboarding has just disabled, so the converge run cannot reach it at all.
- The address gathered during onboarding is lost with the run.

## Re-onboarding Guard

Onboarding is one-shot and is not made safe to rerun. An onboarded Incus instance stays in `raw` for as long as it runs, because the plugin lists it, so `10_onboard.yml` would target it again. Loaded together with the onboard inventory, the host's contract would then reach it over SSH as `initial`, and the bootstrap and baseline plays would run as a non-root user and fail partway.

The first task of the first play guards against that. It runs `raw: id initial`, which needs no Python. If the `initial` user exists, the play prints that the host is already onboarded and ends for that host only with `meta: end_host`, without failing the run. The later plays target `onboarding`, an in-memory group holding only the hosts promoted in the current run, so a host already listed in the onboard inventory's `onboarded` group is not touched. A second run against onboarded nodes reports both as already onboarded and changes nothing.

To onboard a node again, restore its `raw` snapshot and demote its inventory entry.

### A Possible Second Layer

The Incus plugin's `filters` option is passed to `incus list`, which accepts instance config keys as filters (`incus list image.os=Ubuntu` lists only Ubuntu instances). Promotion could set a user config key such as `user.uc_stage=onboarded` on the instance, and the plugin config could filter on it, so onboarded instances drop out of `raw` altogether. This is not implemented. `incus list` filters match a value exactly or as a regular expression (`image.os=Ub.*` works), but have no negation (`image.os!=Ubuntu` silently matches nothing). The filter would therefore have to select instances that are still raw, for example `user.uc_stage=raw` set at launch, rather than exclude onboarded ones, and every launch would have to set the key.

## Snapshot Alignment

Incus snapshot names follow the playbook numbers (see *Incus: Instance Naming*). Take each snapshot after the playbook succeeds and its inventory change is in place.

| Snapshot | Taken | Inventory stage holding the node |
|----------|-------|----------------------------------|
| `raw` | At launch, before Ansible touches the instance | raw, through its source (plugin, `hosts.yml`, or `discovered.yml`); no entry in `onboard/` |
| `10-onboarded` | After `10_onboard.yml` succeeds | `onboard/<env>/hosts.yml` |
| `20-normalized` | After `20_normalize.yml` succeeds and `promote_node.py` has run | `normalized/<env>/hosts.yml` |
| `30-<role>` | After `30_specialize.yml` succeeds with that role | `normalized/<env>/hosts.yml` |

```bash
incus snapshot create deb13 10-onboarded
```

### Restore and Resume

Restoring a snapshot changes the instance only. The inventory entry and the fact cache still describe the later state, so move both back by hand.

- Restore the instance to the snapshot of the stage you want to resume from.
- Demote the inventory entry to the stage that snapshot belongs to. Demoting to raw removes the entry from the onboard inventory and writes nothing to raw; the node is listed in raw again by its source. Demoting from normalized to onboard moves the entry back.
- Flush the node's cached facts, so the next run does not reach the node at a stale address or skip a fact gathering it needs. The jsonfile cache keeps one file per host in the directory `fact_caching_connection` names; ansible-core 2.21 prefixes the file name, for example `s1_deb13`.
- Run the next playbook.

To resume onboarding from `raw`:

```bash
incus snapshot restore deb13 raw
python3 scripts/demote_node.py --from inventories/onboard/dev --to inventories/raw --host deb13 --no-commit
CACHE="$(ansible-config dump | awk -F' = ' '/^CACHE_PLUGIN_CONNECTION/{print $2}')"; CACHE="${CACHE/#\~/$HOME}"
find "$CACHE" -maxdepth 1 \( -name deb13 -o -name '*_deb13' \) -delete
```

To resume normalizing from `10-onboarded`:

```bash
incus snapshot restore deb13 10-onboarded
python3 scripts/demote_node.py --from inventories/normalized/dev --to inventories/onboard/dev --host deb13 --no-commit
CACHE="$(ansible-config dump | awk -F' = ' '/^CACHE_PLUGIN_CONNECTION/{print $2}')"; CACHE="${CACHE/#\~/$HOME}"
find "$CACHE" -maxdepth 1 \( -name deb13 -o -name '*_deb13' \) -delete
```

On a development machine where every node is reset together, `python3 scripts/reset_inventories.py` empties every stage inventory and the whole fact cache instead.

## Provisional Names and Renaming

Discovered hosts get provisional names, `disc-<ip with dots as hyphens>`, and the host variable `name_provisional: true`. The naming convention governs instances the controller creates, not nodes it discovers (see the Scope section of *Incus: Instance Naming*), so a discovered node may keep its provisional or source-assigned name. Renaming is not implemented.

### Proposal: Rename Once at Onboarding

If a discovered node is to be renamed, it should happen once, inside `10_onboard.yml`, after facts are gathered and before the persist play writes the onboard inventory entry. Afterwards the name never changes.

- The new name comes from an explicit map passed in (`-e onboard_names='{"disc-192-168-1-10": "deb13-web1"}'`), not derived automatically. An OS code alone does not make a scanned node's name unique.
- The persist play passes `--host <provisional> --rename <new>` to `promote_node.py`, which drops `name_provisional`, writes the entry under the new name, and refuses a name already present in any stage inventory.
- The node's own host name is set to match, with the hostname role, in the same play.
- The cached facts for the provisional name are deleted.
- A node with no entry in the map keeps its provisional name, and stays marked `name_provisional: true` so the gap is visible.

## Alternative Patterns Considered

### Playbook-Scoped Variables

```text
playbooks/
├── normalize/
│   ├── firewall.yml   ← vars live here
│   └── main.yml
```

#### Decision

Rejected. One playbook cannot serve multiple environments with different rules without extra indirection. Mixing "how" (playbook) with "what" (policy) violates the separation principle. The readability gain of co-location does not justify the loss of environment orthogonality.

### Materialized Defaults (Scaffold Pattern)

Generates a real inventory file from a role's `defaults/main.yml`. Admins edit the file directly.

#### Decision

Rejected. A prototype scaffold playbook existed until v0.1.4 and was removed in v0.1.5: it wrote a role's defaults, a mapping, where the firewall plays expect a list, and nothing depended on it.

## Usage

All stage-namespaced firewall variables must be loaded by passing every contributing inventory with `-i` in load-order. An inventory that is not passed contributes no variables, and `default([])` will silently produce an empty list rather than a warning.

```bash
# Full lifecycle (site.yml chains all stages; pass all inventories)
ansible-playbook \
  -i inventories/raw \
  -i inventories/onboard/dev \
  -i inventories/normalized/dev \
  site.yml \
  -e onboard_inventory=inventories/onboard/dev \
  -e target_group=webservers \
  -e specialize_role=web-server

# Individual stages

ansible-playbook \
  -i inventories/raw \
  ingress/playbooks/00_discover.yml \
  -e discover_source=subnet \
  -e discover_subnet=192.168.1.0/24

ansible-playbook \
  -i inventories/raw \
  -i inventories/onboard/dev \
  ingress/playbooks/10_onboard.yml \
  -l deb13 \
  -e onboard_inventory=inventories/onboard/dev \
  -e target_group=webservers

ansible-playbook \
  -i inventories/raw \
  -i inventories/onboard/dev \
  -i inventories/normalized/dev \
  converge/playbooks/20_normalize.yml \
  -e target_group=webservers

ansible-playbook \
  -i inventories/raw \
  -i inventories/onboard/dev \
  -i inventories/normalized/dev \
  converge/playbooks/30_specialize.yml \
  -e specialize_role=web-server
```

Discovered nodes are onboarded the same way. They are reached over SSH as root until onboarding disables root login, so the controller's key must already be in root's `authorized_keys`:

```bash
ansible-playbook \
  -i inventories/raw \
  ingress/playbooks/00_discover.yml \
  -e discover_subnet=192.168.1.0/24

ansible-playbook \
  -i inventories/raw \
  -i inventories/onboard/dev \
  ingress/playbooks/10_onboard.yml \
  -l 'disc-*' \
  -e onboard_inventory=inventories/onboard/dev
```

Environment selection is implicit: the inventory you point at determines the environment. There is no `target_env` variable. For the raw stage there is no environment at all; see Why raw Has No Environment Split.

## Stage Responsibilities

| Stage | Question it answers | Firewall contribution | Key roles |
|-------|---------------------|-----------------------|-----------|
| discover | What exists? | None | nmap / cloud API |
| onboard | Can I manage it? | SSH (port 22) | bootstrap, umask, epel, update, locale, auto_update, cron, ntp, openssh, fail2ban, uc_firewall, users |
| normalize | Does it meet the baseline? | Monitoring, internal services | selinux, auditd (not in containers), sysctl, hostname, rsyslog, uc_firewall |
| specialize | What is it for? | Application ports (80, 443, etc.) | role-specific + uc_firewall |

## Scripts

Both scripts are plain Python 3 and run unchanged on Linux, macOS, and Windows. They need PyYAML, which is already installed wherever Ansible is.

The playbooks promote hosts with `add_host`, which lasts only for the current run. These scripts make the same move permanent in the inventory files, so that a stage can later be run on its own: `20_normalize.yml` targets the `onboarded` group and `30_specialize.yml` targets `normalized`, and those groups must exist in the stage's `hosts.yml` when no earlier play has created them in memory.

### promote_node.py

Moves a host entry between inventory stages. Git-tracked, auditable, revertible.

The host is removed from the source `hosts.yml` and added to the destination `hosts.yml` under the group that stage's playbook targets (`raw`, `onboarded`, or `normalized`), keeping its connection variables. `--group` adds it to a second group such as `webservers`. Both files are then committed to git; pass `--no-commit` to skip that. The files are rewritten by PyYAML, so comments in `hosts.yml` are not preserved.

```python
#!/usr/bin/env python3
"""Move a host entry between inventory stages.

Removes the host from whichever static inventory file in the source
inventory directory holds it (hosts.yml, discovered.yml, and so on; dynamic
plugin configs are skipped), adds it to the destination stage's hosts.yml
under that stage's group, then commits the changed files to git.

Raw is what the sources report, and no script adds a host to any file under
inventories/raw/:
- Plugin-discovered hosts (Incus and similar) are in no static file. Promote
  one by passing --address; the destination entry is created and marked
  uc_origin: plugin.
- A host listed by hand in raw/hosts.yml is copied, not moved, and marked
  uc_origin: static. Scripts never write raw/hosts.yml.
- A scanned host is removed from raw/discovered.yml when promoted, so it is
  not listed in two stages until the next scan. This is the only case where
  a script changes a raw file.
- Demotion to raw removes the host's entry from the source stage and writes
  nothing. The node reappears in raw through its source: the plugin lists a
  running instance, a hand-entered host never left hosts.yml, and a scanned
  host is found by the next scan. Demotion is inventory bookkeeping that
  lets the inventory follow a node after a snapshot restore.

A host promoted into the onboard stage carries the connection contract at
host level, so it wins over the raw inventory's group variables whichever
order the inventories are loaded in. Runs on Linux, macOS, and Windows. Requires PyYAML,
which is already present wherever Ansible is installed.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

# Lifecycle order.
STAGES = ["raw", "onboard", "normalized"]

# The group a host entry is written under in each stage's hosts.yml. Raw is
# absent: no script adds a host to raw.
STAGE_GROUP = {"onboard": "onboarded", "normalized": "normalized"}

# Header comments rewritten whenever the script rewrites these files.
HEADERS = {
    ("raw", "discovered.yml"):
        "# inventories/raw/discovered.yml\n#\n"
        "# Generated inventory, written by ingress/playbooks/00_discover.yml and\n"
        "# overwritten on every subnet scan. promote_node.py removes a host from it\n"
        "# when promoting that host. Not committed. Do not edit by hand.\n"
        "# Names are provisional (disc-<ip>) until onboarding.\n",
}

# How an onboarded node is reached: SSH as the initial user, offering only
# the named key so agent keys cannot exhaust MaxAuthTries. ansible_host and
# ansible_ssh_private_key_file are filled in per host.
CONTRACT = {
    "ansible_connection": "ssh",
    "ansible_user": "initial",
    "ansible_ssh_common_args": "-o IdentitiesOnly=yes",
}
# Records where a promoted host came from, for the operator:
#   plugin: created from --address; a dynamic inventory plugin supplies it
#   static: listed by hand in raw/hosts.yml, which scripts never write
# A scanned host carries no marker; it came from raw/discovered.yml.
ORIGIN_KEY, ORIGIN_PLUGIN, ORIGIN_STATIC = "uc_origin", "plugin", "static"

# Hand-maintained files that scripts read but never write.
READ_ONLY = {("raw", "hosts.yml")}


def stage_of(inventory: Path) -> str:
    """Return the lifecycle stage an inventory directory belongs to."""
    parts = inventory.resolve().parts
    if "inventories" in parts:
        index = len(parts) - 1 - parts[::-1].index("inventories")
        if index + 1 < len(parts) and parts[index + 1] in STAGES:
            return parts[index + 1]
    raise SystemExit(
        f"error: {inventory} is not under inventories/<{'|'.join(STAGES)}>/"
    )


def load(hosts_file: Path) -> dict:
    if not hosts_file.exists():
        return {}
    with hosts_file.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def dump(hosts_file: Path, data: dict, header: str | None = None) -> None:
    hosts_file.parent.mkdir(parents=True, exist_ok=True)
    with hosts_file.open("w", encoding="utf-8", newline="\n") as handle:
        if header:
            handle.write(header)
        yaml.safe_dump(data, handle, default_flow_style=False, sort_keys=False)


def static_files(inventory: Path) -> list[Path]:
    """Static YAML inventory files at the top of an inventory directory.

    hosts.yml comes first. Files that are dynamic plugin configs (a top-level
    plugin: key) and files that are not YAML mappings are skipped.
    """
    files = sorted(
        (p for p in inventory.iterdir()
         if p.is_file() and p.suffix in (".yml", ".yaml")),
        key=lambda p: (p.name != "hosts.yml", p.name),
    ) if inventory.is_dir() else []
    static = []
    for path in files:
        try:
            data = load(path)
        except yaml.YAMLError:
            continue
        if isinstance(data, dict) and "plugin" not in data:
            static.append(path)
    return static


def find_host(inventory: Path, host: str):
    """Pop host from the first static file holding it.

    Return (file, its data with the host removed, host vars), or
    (None, None, None) when no static file holds it.
    """
    for path in static_files(inventory):
        data = load(path)
        found, host_vars = pop_host(data, host)
        if found:
            return path, data, host_vars
    return None, None, None


def pop_host(groups: dict, host: str):
    """Remove host from every group in the tree. Return (found, its vars)."""
    found, host_vars = False, None
    for group in groups.values():
        if not isinstance(group, dict):
            continue
        hosts = group.get("hosts")
        if isinstance(hosts, dict) and host in hosts:
            removed = hosts.pop(host)
            if not found:
                found, host_vars = True, removed
        children = group.get("children")
        if isinstance(children, dict):
            child_found, child_vars = pop_host(children, host)
            if child_found and not found:
                found, host_vars = True, child_vars
    return found, host_vars


def add_host(data: dict, group: str, host: str, host_vars) -> None:
    section = data.get(group)
    if not isinstance(section, dict):
        section = data[group] = {}
    hosts = section.get("hosts")
    if not isinstance(hosts, dict):
        hosts = section["hosts"] = {}
    hosts[host] = host_vars


def with_contract(host_vars, address: str | None, key_file: str | None,
                  host: str) -> dict:
    """Return host_vars with the onboard connection contract applied."""
    host_vars = dict(host_vars or {})
    address = address or host_vars.get("ansible_host")
    key_file = key_file or host_vars.get("ansible_ssh_private_key_file")
    if not address:
        raise SystemExit(f"error: no address for {host}; pass --address")
    if not key_file:
        raise SystemExit(f"error: no key file for {host}; pass --key-file")
    host_vars.update(CONTRACT)
    host_vars["ansible_host"] = address
    host_vars["ansible_ssh_private_key_file"] = key_file
    return host_vars




def git_commit(files: list[Path], message: str) -> None:
    if shutil.which("git") is None:
        print("warning: git not found, changes left uncommitted", file=sys.stderr)
        return
    cwd = files[0].parent
    top = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=cwd, capture_output=True, text=True,
    )
    if top.returncode != 0:
        print("warning: not a git repository, changes left uncommitted", file=sys.stderr)
        return
    paths = [str(path.resolve()) for path in files]
    subprocess.run(["git", "add", "--", *paths], cwd=cwd, check=True)
    subprocess.run(["git", "commit", "-m", message, "--", *paths], cwd=cwd, check=True)


def main(direction: str = "promote") -> int:
    parser = argparse.ArgumentParser(
        description=f"{direction.capitalize()} a host between inventory stages."
    )
    parser.add_argument("--from", dest="source", required=True, type=Path,
                        metavar="INVENTORY", help="source inventory directory")
    parser.add_argument("--to", dest="dest", required=True, type=Path,
                        metavar="INVENTORY", help="destination inventory directory")
    parser.add_argument("--host", required=True, help="inventory hostname to move")
    parser.add_argument("--group", help="extra group to add the host to, e.g. webservers")
    parser.add_argument("--address", metavar="ADDRESS",
                        help="management address; creates the entry when no static "
                             "file in the source holds the host (plugin-discovered hosts)")
    parser.add_argument("--key-file", metavar="PATH",
                        help="SSH private key path written as ansible_ssh_private_key_file "
                             "when the destination is the onboard stage")
    parser.add_argument("--no-commit", action="store_true", help="skip the git commit")
    args = parser.parse_args()

    from_stage, to_stage = stage_of(args.source), stage_of(args.dest)
    step = STAGES.index(to_stage) - STAGES.index(from_stage)
    if (direction == "promote" and step <= 0) or (direction == "demote" and step >= 0):
        raise SystemExit(f"error: cannot {direction} from {from_stage} to {to_stage}")

    source_file, source_data, host_vars = find_host(args.source, args.host)
    found = source_file is not None
    if not found and (to_stage == "raw" or not args.address):
        raise SystemExit(
            f"error: host {args.host} not found in any static inventory file in {args.source}"
        )

    read_only = found and (from_stage, source_file.name) in READ_ONLY
    if not found:
        host_vars = {ORIGIN_KEY: ORIGIN_PLUGIN}
    elif read_only:
        host_vars = dict(host_vars or {})
        host_vars[ORIGIN_KEY] = ORIGIN_STATIC
        print(f"note: {source_file} is hand-maintained; its entry for {args.host} is left in place")

    if to_stage == "raw":
        # Raw is what the sources report. Remove the entry and write nothing;
        # the node reappears in raw through its source.
        dump(source_file, source_data, HEADERS.get((from_stage, source_file.name)))
        print(f"{direction.capitalize()}d {args.host}: removed from {source_file}; "
              f"nothing written to {args.dest}")
        if not args.no_commit:
            git_commit([source_file], f"{direction} {args.host}: {from_stage} -> {to_stage}")
        return 0

    dest_file = args.dest / "hosts.yml"
    if to_stage == "onboard":
        host_vars = with_contract(host_vars, args.address, args.key_file, args.host)

    # pop_host clears every existing entry for the host, so a repeat
    # promotion replaces the entry instead of adding a second one.
    dest_data = load(dest_file)
    pop_host(dest_data, args.host)
    add_host(dest_data, STAGE_GROUP[to_stage], args.host, host_vars)
    if args.group:
        add_host(dest_data, args.group, args.host, None)

    written = [dest_file]
    if found and not read_only:
        dump(source_file, source_data, HEADERS.get((from_stage, source_file.name)))
        written.insert(0, source_file)
    elif not found:
        print(f"note: {args.host} was not in any static file in {args.source}; "
              "created from --address")
    dump(dest_file, dest_data)
    print(f"{direction.capitalize()}d {args.host}: {args.source} -> {args.dest}")

    if (args.source / "host_vars" / f"{args.host}.yml").exists():
        print(f"note: {args.source / 'host_vars'} still holds a file for {args.host}")

    if not args.no_commit:
        git_commit(
            written,
            f"{direction} {args.host}: {from_stage} -> {to_stage}",
        )
    return 0


if __name__ == "__main__":
    sys.exit(main("promote"))
```

#### Promote Usage

```bash
python scripts/promote_node.py \
  --from inventories/raw \
  --to inventories/onboard/dev \
  --host 192.168.1.10 \
  --group webservers
```

On Windows the same command works from PowerShell or `cmd` on one line, using `python` or `py`.

### demote_node.py

Rolls back a node to a previous state. Inverse of promote: same interface, opposite direction. It imports `promote_node.py`, so the two files must stay in the same directory.

```python
#!/usr/bin/env python3
"""Roll a host back to an earlier inventory stage.

Inverse of promote_node.py: same interface, opposite direction. Demotion is
inventory bookkeeping: it lets the inventory follow a node after a snapshot
restore, and has nothing to do with making onboarding repeatable.

- Demotion to raw removes the host's entry from the source stage and writes
  nothing under inventories/raw/. The node reappears in raw through its
  source: the Incus plugin lists a running instance, a hand-entered host
  never left raw/hosts.yml, and a scanned host is found by the next scan.
- Demotion from normalized to onboard moves the entry back.
"""
import sys

from promote_node import main

if __name__ == "__main__":
    sys.exit(main("demote"))
```

#### Demote Usage

```bash
python scripts/demote_node.py \
  --from inventories/normalized/dev \
  --to inventories/onboard/dev \
  --host 192.168.1.10
```

## Ansible Configuration

```ini
# ansible.cfg
[defaults]
roles_path = ./roles:./ingress/roles:./converge/roles:~/.ansible/roles:/usr/share/ansible/roles
inventory = ./inventories/raw
# Hosts handled in parallel. Test nodes share this machine with the controller.
forks = 20
# Test nodes are rebuilt often and their host keys change. Revisit this before
# any non-test node is managed: enable it and manage known_hosts instead.
host_key_checking = False
gathering = smart
fact_caching = jsonfile
# Per-user cache, kept out of /tmp. reset_inventories.py reads this path.
fact_caching_connection = ~/.ansible/fact_cache/uc-controller
fact_caching_timeout = 3600
stdout_callback = default
callback_result_format = yaml
# Per-task timings at the end of every run.
callbacks_enabled = ansible.posix.profile_tasks

[privilege_escalation]
become = True
become_method = sudo
become_user = root
become_ask_pass = False

[connection]
# Send modules through the open SSH session instead of copying a file first.
# Needs sudo without requiretty, which Debian and Ubuntu do not set.
pipelining = True
```


The settings are measured and explained in the speed overview (`en/docs/dev/`). In short: pipelining sends modules through the open SSH session and needs sudo without `requiretty`, which Debian and Ubuntu do not set; the fact cache is per user, outside `/tmp`; `forks = 20` stays modest because the test nodes share the controller's machine; the default strategy stays `linear`, and only the converge plays set `strategy: free`; `host_key_checking = False` is for rebuilt test nodes only and must be revisited before any other node is managed.
## Requirements

Roles are installed from Ansible Galaxy with `ansible-galaxy install -r requirements.yml`. The file must keep its `.yml` or `.yaml` extension, and roles land in the first writable directory on the configured `roles_path` <a id="cite-ansible-galaxy"></a>([Ansible project contributors, n.d.-d](#ref-ansible-galaxy)).

```yaml
# requirements.yml
---
collections: []

roles:
  - name: robertdebock.bootstrap

  # Our fork of robertdebock.umask, adding the umask_system option for a
  # system-wide umask (login.defs + profile.d). Sourced from git, not Galaxy,
  # because the option does not exist upstream. Must run before
  # robertdebock.users so new home directories get the intended permissions.
  - name: steelcj.umask
    src: git@github.com:steelcj/ansible-role-umask.git
    scm: git
    version: master
  - name: robertdebock.epel
  - name: robertdebock.update
  - name: robertdebock.locale
  - name: robertdebock.auto_update
  - name: robertdebock.cron
  - name: robertdebock.ntp
  - name: robertdebock.openssh
  - name: robertdebock.fail2ban
  - name: robertdebock.users
  - name: robertdebock.selinux
  - name: robertdebock.auditd
#  - name: robertdebock.pam      # robert does not have a role called pam
#  - name: robertdebock.limits   # robert does not have a role called limits
  - name: robertdebock.sysctl
  - name: robertdebock.hostname
#  - name: robertdebock.timezone # robert does not have a role called timezone (see local and ntp)
#  - name: robertdebock.motd     # robert does not have a role called mod
#  - name: robertdebock.chrony   # robert does not have a role with this name
  - name: robertdebock.rsyslog
```

## Node Lifecycle Flow

```text
┌───────────┐  10_onboard   ┌───────────┐  20_normalize  ┌────────────┐  30_specialize  ┌─────────────┐
│ raw       │ ────────────▶ │ onboarded │ ─────────────▶ │ normalized │ ──────────────▶ │ specialized │
│           │               │           │                │            │                 │             │
│ hosts.yml │               │ group_vars│                │ group_vars │                 │ group_vars  │
│ (auto)    │               │ /all.yml  │                │ /all.yml   │                 │ /webservers │
│           │               │           │                │            │                 │             │
│ (none)    │               │ firewall  │                │ firewall   │                 │ firewall    │
│           │               │ _onboard  │                │ _normalize │                 │ _specialize │
└───────────┘               └───────────┘                └────────────┘                 └─────────────┘

Combined firewall at each stage:
  onboard:    onboard
  normalize:  onboard + normalize
  specialize: onboard + normalize + specialize
```

## References

<a id="ref-ansible-add-host"></a>
[Return to citation](#cite-ansible-add-host)
Ansible project contributors. (n.d.-a). *ansible.builtin.add_host module: Add a host (and alternatively a group) to the ansible-playbook in-memory inventory*. Ansible Community Documentation. Retrieved November 11, 2026, from https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/add_host_module.html

<a id="ref-ansible-import-playbook"></a>
[Return to citation](#cite-ansible-import-playbook)
Ansible project contributors. (n.d.-b). *ansible.builtin.import_playbook module: Import a playbook*. Ansible Community Documentation. Retrieved November 11, 2026, from https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/import_playbook_module.html

<a id="ref-ansible-config"></a>
[Return to citation](#cite-ansible-config)
Ansible project contributors. (n.d.-c). *Ansible configuration settings*. Ansible Community Documentation. Retrieved November 11, 2026, from https://docs.ansible.com/projects/ansible/latest/reference_appendices/config.html

<a id="ref-ansible-galaxy"></a>
[Return to citation](#cite-ansible-galaxy)
Ansible project contributors. (n.d.-d). *Galaxy user guide*. Ansible Community Documentation. Retrieved November 11, 2026, from https://docs.ansible.com/projects/ansible/latest/galaxy/user_guide.html

<a id="ref-ansible-inventory"></a>
[Return to citation](#cite-ansible-inventory)
Ansible project contributors. (n.d.-e). *How to build your inventory*. Ansible Community Documentation. Retrieved November 11, 2026, from https://docs.ansible.com/projects/ansible/latest/inventory_guide/intro_inventory.html

<a id="ref-ansible-variables"></a>
[Return to citation](#cite-ansible-variables)
Ansible project contributors. (n.d.-f). *Using variables*. Ansible Community Documentation. Retrieved November 11, 2026, from https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_variables.html
