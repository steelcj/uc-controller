# uc-controller

An Ansible controller configuration that moves nodes through a four stage lifecycle: discover, onboard, normalize, and specialize. Each stage owns its own inventory, its own variables, and its own contribution to the firewall.

## Changelog

### v0.1.3 → v0.1.4

| Change | Description |
|--------|-------------|
| Option A layout | Playbooks live in `ingress/playbooks/` (discover, onboard) and `converge/playbooks/` (normalize, specialize), `site.yml` at the repository root, `scaffold.yml` in `tools/`; `roles_path` keeps the shared `./roles` first |
| Multi-source raw inventory | `inventories/raw/hosts.yml` is a hand-maintained static file in which each source group is a child of `raw`; hosts come from per-source root-level files; new Raw Inventory section |
| Source group invariant | Every raw host is in `raw` and in exactly one source group; connection settings live in `group_vars/<source>.yml` |
| Incus host names | `host_fqdn: false` in `inventories/raw/incus.yml`, so an instance named `deb13` is the inventory host `deb13`, not `deb13.default.local` |
| Bootstrap opt-out variable | `needs_python_bootstrap: true` in `raw/group_vars/all.yml`; a source opts out only when its images ship Python and sudo |
| Reset helper | `reset_inventories.py` never touches the static `raw/hosts.yml` |

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
│
├── tools/
│   └── scaffold.yml
│
├── inventories/
│   ├── raw/                      # flat: no environment split
│   │   ├── hosts.yml             # static, hand-maintained: source groups under raw
│   │   ├── incus.yml             # dynamic plugin config: Incus instances
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
│
└── vaults/
```

A `prod` environment, when it exists, follows the same pattern as `dev` and `stage` under `onboard/` and `normalized/`.

## Raw Inventory

The raw inventory describes nodes as their source provides them, before onboarding has given them an `initial` user and SSH. Source differences end here: once a node is onboarded it is reached over SSH as `initial`, and the onboard and normalized inventories do not care where it came from.

### Layout

| File | Kind | Written by |
|------|------|------------|
| `hosts.yml` | Static inventory | Hand. No playbook or script writes to it. |
| `incus.yml` | Dynamic inventory plugin config (`community.general.incus`) | Hand. The plugin generates the hosts at run time. |
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

### Why raw Has No Environment Split

`onboard/` and `normalized/` are split by environment, and `raw/` is not. A raw node has no environment until onboarding assigns one: the onboard inventory you pass with `onboard_inventory` decides it. A container just launched, a cloud instance, or a node found by a scan may never belong to any environment, and some will be someone else's. Splitting `raw/` by environment would force that decision before the node is even reachable as `initial`, and would duplicate every source config per environment. Do not add `raw/dev/` or `raw/stage/`.

### Adding a Source

Add a source only when there is a node to test it against.

- Add the group under `raw.children` in `hosts.yml`.
- Add `group_vars/<source>.yml` with the connection settings (`ansible_connection`, `ansible_user`, and anything else the source needs). Set `needs_python_bootstrap: false` there only if the source's images are known to ship both Python and sudo.
- Add the root-level file that supplies the hosts: a plugin config named as the plugin requires, or a generated inventory. Give it a header comment saying which it is and what writes it, and make it put hosts only in the source group.
- Confirm with `ansible-inventory -i inventories/raw --graph` that the new hosts appear under `raw` and the source group, and with `--host` that they get the source's connection settings.

Nothing in `onboard/`, `normalized/`, or the converge playbooks changes.

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
    source: 0.0.0.0/0
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

The role runs against the merged list. Run it once or ten times, same result, idempotent.

**Important:** the `default([])` guards only prevent a template error when a variable is undefined. They do not recover rules from an inventory that was not loaded. All inventories contributing rules must be passed with `-i` in the correct order. See Usage below.

### Why This Works

- **Onboard** knows it needs SSH. That's all it knows.
- **Normalize** knows it needs monitoring. It doesn't care about SSH.
- **Specialize** knows it needs ports 80/443. It doesn't care about monitoring.
- **None of them know the full picture individually.** The combine at play time is the convergence.

The firewall settings live with the stage that owns them. The role only ever runs against the merged result. That's layering without overwrite.

## Playbooks

### 00_discover.yml

Find raw nodes and populate the raw inventory. Supports subnet scanning (nmap) or cloud API queries.

Parameters are passed via `-e` and consumed inline with `| default()` filters. No recursive `vars:` declarations.

Discovered hosts are written into a group named `raw`. Group names come from the contents of an inventory, not from the name of its directory, so hosts listed directly under `all` would never match `hosts: raw` in the onboard play. The play ends with `meta: refresh_inventory` because inventory is read once at startup; without the refresh, a full `site.yml` run would not see the hosts it has just written.

```yaml
#!/usr/bin/env ansible-playbook
---
- name: discover raw nodes
  hosts: localhost
  gather_facts: no

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

    - name: derive unique hostnames from IPs
      set_fact:
        discovered_named: >-
          {{
            discovered_hosts
            | map('regex_replace', '[^a-zA-Z0-9._]', '-')
            | zip(discovered_hosts)
            | list
          }}
      when: (discover_source | default('subnet')) == 'subnet'

    - name: build raw inventory from subnet scan
      copy:
        dest: "{{ playbook_dir }}/../inventories/raw/hosts.yml"
        content: |
          raw:
            hosts:
          {% for pair in discovered_named %}
              {{ pair[0] }}:
                ansible_host: {{ pair[1] }}
                ansible_user: root
          {% endfor %}
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

    - name: build raw inventory from cloud results
      copy:
        dest: "{{ playbook_dir }}/../inventories/raw/hosts.yml"
        content: |
          raw:
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

Make it manageable. Validates SSH reachability, promotes raw nodes into the `onboarded` group, and converges the onboarding baseline.

`wait_for` is delegated to the controller because the target may not yet be reachable. Promotion uses `add_host`, which adds hosts and groups to the in-memory inventory so that later plays in the same playbook run can target them <a id="cite-ansible-add-host"></a>([Ansible project contributors, n.d.-a](#ref-ansible-add-host)). `add_host` runs once per play rather than once per host, so the task loops over `ansible_play_hosts` to promote every node. That list holds only the hosts still active in the play, so a node that failed the SSH check is not promoted.

```yaml
#!/usr/bin/env ansible-playbook
---
- name: validate and promote raw nodes
  hosts: raw
  gather_facts: no

  tasks:
    - name: wait for SSH
      wait_for:
        host: "{{ ansible_host | default(inventory_hostname) }}"
        port: 22
        timeout: 30
      delegate_to: localhost

    - name: promote to onboarded group
      add_host:
        name: "{{ item }}"
        ansible_host: "{{ hostvars[item].ansible_host | default(item) }}"
        groups:
          - onboarded
          - "{{ target_group | default('ungrouped') }}"
      loop: "{{ ansible_play_hosts }}"

- name: converge onboard baseline
  hosts: onboarded
  become: yes
  gather_facts: yes

  vars:
    firewall_rules: >-
      {{
        (firewall_rules_onboard | default([]))
      }}

  roles:
    - role: robertdebock.bootstrap
    - role: robertdebock.epel
    - role: robertdebock.update
    - role: robertdebock.locale
    - role: robertdebock.auto_update
    - role: robertdebock.cron
    - role: robertdebock.ntp
    - role: robertdebock.openssh
    - role: robertdebock.fail2ban
    - role: robertdebock.firewall
    - role: robertdebock.users
```

### 20_normalize.yml

Make it compliant. Validates onboarded nodes, promotes them into the `normalized` group, and converges the compliance baseline.

```yaml
#!/usr/bin/env ansible-playbook
---
- name: validate and promote onboarded nodes
  hosts: onboarded
  gather_facts: no

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

  vars:
    firewall_rules: >-
      {{
        (firewall_rules_onboard | default([]))
        + (firewall_rules_normalize | default([]))
      }}

  roles:
    - role: robertdebock.selinux
    - role: robertdebock.auditd
    - role: robertdebock.pam
    - role: robertdebock.limits
    - role: robertdebock.sysctl
    - role: robertdebock.hostname
    - role: robertdebock.timezone
    - role: robertdebock.motd
    - role: robertdebock.chrony
    - role: robertdebock.rsyslog
    - role: robertdebock.firewall
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

  vars:
    firewall_rules: >-
      {{
        (firewall_rules_onboard | default([]))
        + (firewall_rules_normalize | default([]))
        + (firewall_rules_specialize | default([]))
      }}

  roles:
    - role: "{{ specialize_role }}"
    - role: robertdebock.firewall
```

### site.yml

Full converge, chains all lifecycle stages for a given environment. Each stage is pulled in with `import_playbook`, which can only be used at the top level of a playbook and not inside a play <a id="cite-ansible-import-playbook"></a>([Ansible project contributors, n.d.-b](#ref-ansible-import-playbook)).

```yaml
#!/usr/bin/env ansible-playbook
---
- import_playbook: lifecycle/00_discover.yml
- import_playbook: lifecycle/10_onboard.yml
- import_playbook: lifecycle/20_normalize.yml
- import_playbook: lifecycle/30_specialize.yml
```

### scaffold.yml (Experimental)

Materializes a role's `defaults/main.yml` into a stage-namespaced inventory file for editing. Generates a starting-point file that admins can edit without guessing variable names.

This is a research pattern, not a production recommendation. See Known Limitations below.

```yaml
#!/usr/bin/env ansible-playbook
---
- name: scaffold role defaults into inventory
  hosts: localhost
  gather_facts: no

  vars:
    scaffold_role: "{{ scaffold_role | mandatory }}"
    scaffold_stage: "{{ scaffold_stage | mandatory }}"
    scaffold_env: "{{ scaffold_env | mandatory }}"
    scaffold_group: "{{ scaffold_group | default('all') }}"
    scaffold_force: "{{ scaffold_force | bool | default(false) }}"
    scaffold_namespace: "firewall_rules_{{ scaffold_stage }}"

  tasks:
    # Locate the role
    - name: find role defaults in local roles/
      stat:
        path: "{{ playbook_dir }}/../roles/{{ scaffold_role }}/defaults/main.yml"
      register: role_defaults_stat

    - name: find role in galaxy paths
      stat:
        path: "{{ item }}/defaults/main.yml"
      loop: "{{ lookup('ansible.builtin.env', 'ANSIBLE_ROLES_PATH').split(':') }}"
      register: role_defaults_galaxy
      when: not role_defaults_stat.stat.exists

    - name: resolve defaults path
      set_fact:
        scaffold_defaults_path: >-
          {{
            role_defaults_stat.stat.exists
            | ternary(
                role_defaults_stat.stat.path,
                (role_defaults_galaxy.results
                  | selectattr('stat.exists')
                  | map(attribute='stat.path')
                  | first | default(''))
              )
          }}

    - name: fail if role not found
      fail:
        msg: "Role '{{ scaffold_role }}' not found in roles/ or ANSIBLE_ROLES_PATH"
      when: scaffold_defaults_path | trim | length == 0

    # Load and transform
    - name: slurp role defaults
      slurp:
        src: "{{ scaffold_defaults_path | trim }}"
      register: defaults_raw

    - name: parse defaults into dict
      set_fact:
        scaffold_defaults_parsed: "{{ defaults_raw.content | b64decode | from_yaml }}"

    # Determine output location
    - name: set output directory
      set_fact:
        scaffold_output_dir: >-
          {{ playbook_dir }}/../inventories/{{ scaffold_stage }}/{{ scaffold_env }}/group_vars

    - name: set output file
      set_fact:
        scaffold_output_file: >-
          {{ scaffold_output_dir }}/{{ scaffold_role.split('.') | last }}.yml

    # Guard against overwrite
    - name: check if output already exists
      stat:
        path: "{{ scaffold_output_file }}"
      register: existing_file

    - name: abort if file exists and force is false
      fail:
        msg: |
          File already exists: {{ scaffold_output_file }}
          Re-run with -e scaffold_force=true to overwrite.
          Admin edits will be lost.
      when:
        - existing_file.stat.exists
        - not scaffold_force | bool

    # Write the scaffold
    - name: ensure output directory exists
      file:
        path: "{{ scaffold_output_dir }}"
        state: directory
        mode: '0755'

    - name: generate scaffold file
      copy:
        dest: "{{ scaffold_output_file }}"
        content: |
          # Scaffold generated from {{ scaffold_role }} defaults
          # Stage: {{ scaffold_stage }} | Env: {{ scaffold_env }} | Group: {{ scaffold_group }}
          #
          # Edit freely. To regenerate (losing edits):
          # ansible-playbook tools/scaffold.yml \
          #   -e scaffold_role={{ scaffold_role }} \
          #   -e scaffold_stage={{ scaffold_stage }} \
          #   -e scaffold_env={{ scaffold_env }} \
          #   -e scaffold_group={{ scaffold_group }} \
          #   -e scaffold_force=true
          #
          {{ scaffold_namespace }}:
          {{ scaffold_defaults_parsed
             | dict2items
             | rejectattr('key', 'match', 'firewall_')
             | list
             | to_nice_yaml(indent=2)
             | indent(2) }}
          #
          # Original role variables (renamed above):
          {% for item in scaffold_defaults_parsed | dict2items %}
          # {{ item.key }}: {{ item.value | to_json }}
          {% endfor %}
        mode: '0644'

    - name: report result
      debug:
        msg: |
          Scaffold written: {{ scaffold_output_file }}
          Namespace: {{ scaffold_namespace }}
          Source: {{ scaffold_defaults_path | trim }}
          Next: edit the file, then run {{ scaffold_stage }} playbook normally.
```

#### Scaffold Usage

```bash
# Generate a starting-point firewall file for the normalized stage
ansible-playbook tools/scaffold.yml \
  -e scaffold_role=robertdebock.firewall \
  -e scaffold_stage=normalized \
  -e scaffold_env=dev \
  -e scaffold_group=webservers

# Force overwrite an existing file
ansible-playbook tools/scaffold.yml \
  -e scaffold_role=robertdebock.firewall \
  -e scaffold_stage=normalized \
  -e scaffold_env=dev \
  -e scaffold_group=webservers \
  -e scaffold_force=true
```

#### Known Limitations

| Issue | Mitigation |
|-------|------------|
| Transformation assumes flat dict to list rename | Only works cleanly for single-list roles like firewall. Multi-key roles need a mapping table |
| No diff detection on role upgrade | Add a `scaffold_check=true` mode that diffs current file against regenerated output and reports drift |
| Host-level override still manual | Workflow: `cp group_vars/firewall.yml host_vars/myhost.yml` then edit |
| Galaxy-installed roles live outside the repo | Requires `ANSIBLE_ROLES_PATH` to be set correctly in `ansible.cfg` |

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

Retained as experimental. The ergonomics are compelling, admins get a complete, valid file they can edit without guessing variable names. But it introduces three hard problems: regeneration vs. drift, silent shadowing of role defaults, and combinatorial explosion when host overrides require copying and editing entire files. The scaffold playbook above is a working prototype, not a production recommendation.

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

Environment selection is implicit: the inventory you point at determines the environment. There is no `target_env` variable.

## Stage Responsibilities

| Stage | Question it answers | Firewall contribution | Key roles |
|-------|---------------------|-----------------------|-----------|
| discover | What exists? | None | nmap / cloud API |
| onboard | Can I manage it? | SSH (port 22) | bootstrap, epel, update, openssh, fail2ban, firewall, users |
| normalize | Does it meet the baseline? | Monitoring, internal services | selinux, auditd, pam, sysctl, rsyslog, firewall |
| specialize | What is it for? | Application ports (80, 443, etc.) | role-specific + firewall |

## Scripts

Both scripts are plain Python 3 and run unchanged on Linux, macOS, and Windows. They need PyYAML, which is already installed wherever Ansible is.

The playbooks promote hosts with `add_host`, which lasts only for the current run. These scripts make the same move permanent in the inventory files, so that a stage can later be run on its own: `20_normalize.yml` targets the `onboarded` group and `30_specialize.yml` targets `normalized`, and those groups must exist in the stage's `hosts.yml` when no earlier play has created them in memory.

### promote_node.py

Moves a host entry between inventory stages. Git-tracked, auditable, revertible.

The host is removed from the source `hosts.yml` and added to the destination `hosts.yml` under the group that stage's playbook targets (`raw`, `onboarded`, or `normalized`), keeping its connection variables. `--group` adds it to a second group such as `webservers`. Both files are then committed to git; pass `--no-commit` to skip that. The files are rewritten by PyYAML, so comments in `hosts.yml` are not preserved.

```python
#!/usr/bin/env python3
"""Move a host entry between inventory stages.

Removes the host from the source inventory's hosts.yml, adds it to the
destination inventory's hosts.yml under that stage's group, then commits
both files to git. Runs on Linux, macOS, and Windows. Requires PyYAML,
which is already present wherever Ansible is installed.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

import yaml

# Lifecycle order, and the group each stage's playbook targets.
STAGES = ["raw", "onboard", "normalized"]
STAGE_GROUP = {"raw": "raw", "onboard": "onboarded", "normalized": "normalized"}


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


def dump(hosts_file: Path, data: dict) -> None:
    hosts_file.parent.mkdir(parents=True, exist_ok=True)
    with hosts_file.open("w", encoding="utf-8", newline="\n") as handle:
        yaml.safe_dump(data, handle, default_flow_style=False, sort_keys=False)


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
    parser.add_argument("--no-commit", action="store_true", help="skip the git commit")
    args = parser.parse_args()

    from_stage, to_stage = stage_of(args.source), stage_of(args.dest)
    step = STAGES.index(to_stage) - STAGES.index(from_stage)
    if (direction == "promote" and step <= 0) or (direction == "demote" and step >= 0):
        raise SystemExit(f"error: cannot {direction} from {from_stage} to {to_stage}")

    source_file = args.source / "hosts.yml"
    dest_file = args.dest / "hosts.yml"

    source_data = load(source_file)
    found, host_vars = pop_host(source_data, args.host)
    if not found:
        raise SystemExit(f"error: host {args.host} not found in {source_file}")

    dest_data = load(dest_file)
    pop_host(dest_data, args.host)
    add_host(dest_data, STAGE_GROUP[to_stage], args.host, host_vars)
    if args.group:
        add_host(dest_data, args.group, args.host, None)

    dump(source_file, source_data)
    dump(dest_file, dest_data)
    print(f"{direction.capitalize()}d {args.host}: {args.source} -> {args.dest}")

    if (args.source / "host_vars" / f"{args.host}.yml").exists():
        print(f"note: {args.source / 'host_vars'} still holds a file for {args.host}")

    if not args.no_commit:
        git_commit(
            [source_file, dest_file],
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

Inverse of promote_node.py: same interface, opposite direction.
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
roles_path = ./roles:~/.ansible/roles:/usr/share/ansible/roles
inventory = ./inventories/raw
host_key_checking = False
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /tmp/ansible_facts
fact_caching_timeout = 3600
stdout_callback = yaml
callbacks_enabled = profile_tasks

[privilege_escalation]
become = True
become_method = sudo
become_user = root
become_ask_pass = False
```

## Requirements

Roles are installed from Ansible Galaxy with `ansible-galaxy install -r requirements.yml`. The file must keep its `.yml` or `.yaml` extension, and roles land in the first writable directory on the configured `roles_path` <a id="cite-ansible-galaxy"></a>([Ansible project contributors, n.d.-d](#ref-ansible-galaxy)).

```yaml
# requirements.yml
---
collections: []

roles:
  - name: robertdebock.bootstrap
  - name: robertdebock.epel
  - name: robertdebock.update
  - name: robertdebock.locale
  - name: robertdebock.auto_update
  - name: robertdebock.cron
  - name: robertdebock.ntp
  - name: robertdebock.openssh
  - name: robertdebock.fail2ban
  - name: robertdebock.firewall
  - name: robertdebock.users
  - name: robertdebock.selinux
  - name: robertdebock.auditd
  - name: robertdebock.pam
  - name: robertdebock.limits
  - name: robertdebock.sysctl
  - name: robertdebock.hostname
  - name: robertdebock.timezone
  - name: robertdebock.motd
  - name: robertdebock.chrony
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
