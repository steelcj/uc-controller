~~~markdown
# UC-Controller Option A: Single Repo, Two Concerns

## Overview

Option A separates ingress (raw → onboarded) and converge (onboarded → normalized → specialized) into distinct top-level directories within a single repository. The inventories remain shared. The boundary is structural: ingress code handles connection plugins, Python bootstrapping, and SSH transitions; converge code never references source-specific logic.

This is the lightest touch that still walls off the complexity. No multi-repo overhead, no cross-repo path management, no separate checkout steps. The directory structure itself is the enforcement.

## Repository Layout

```text
uc-controller/
├── ansible.cfg
├── requirements.yml
│
├── inventories/
│ ├── raw/
│ │ ├── hosts.yml
│ │ ├── incus.yml
│ │ ├── group_vars/
│ │ │ ├── all.yml
│ │ │ ├── incus.yml
│ │ │ └── raw.yml
│ │ └── host_vars/
│ │
│ ├── onboard/
│ │ ├── dev/
│ │ │ ├── hosts.yml
│ │ │ ├── group_vars/
│ │ │ │ └── all.yml
│ │ │ └── host_vars/
│ │ ├── stage/
│ │ └── prod/
│ │
│ └── normalized/
│ ├── dev/
│ ├── stage/
│ └── prod/
│
├── ingress/
│ ├── playbooks/
│ │ ├── 00_discover.yml
│ │ └── 10_onboard.yml
│ └── roles/
│ └── (ingress-specific roles, if any)
│
├── converge/
│ ├── playbooks/
│ │ ├── 20_normalize.yml
│ │ └── 30_specialize.yml
│ └── roles/
│ └── (converge-specific roles, if any)
│
├── scripts/
│ ├── promote_node.py
│ └── demote_node.py
│
└── vaults/
 ├── raw_secrets.yml
 ├── onboard_secrets.yml
 └── normalized_secrets.yml
```

## Design Principles

### The Boundary Is Playbook-Level, Not Inventory-Level

Inventories stay unified. The firewall layering handoff (`firewall_rules_onboard` as data in `group_vars`) does not cross a repo boundary — it is a file the converge playbooks read. The only thing separated is the code that knows about connection plugins, Python bootstrapping, and SSH transitions from the code that does not.

### Ingress Owns Source Complexity

Everything that varies by node source lives in `ingress/`:

- Connection plugins (`community.general.incus`, `community.libvirt.libvirt`, etc.)
- Python bootstrapping via `raw` module
- SSH transition (switching from native connection to SSH as the `initial` user)
- Source-specific reachability checks (`incus exec`, `virsh dom-state`, `wait_for` on port 22)

### Converge Is Source-Agnostic

`20_normalize.yml` and `30_specialize.yml` never reference `ansible_connection`, never condition on source type, never bootstrap Python. They assume SSH as a known user with passwordless sudo. The bounded complexity insight guarantees this: once a node completes onboarding, its origin is irrelevant.

### Shared Inventory, Not Shared Code

The inventories directory is shared, but the playbooks that read it are not. Ingress playbooks target `raw` and `onboarded` groups. Converge playbooks target `onboarded` and `normalized` groups. The overlap is the `onboarded` group in the onboard inventory — that is the handoff point, and it is data, not code.

## Ansible Configuration

A single `ansible.cfg` at the repo root serves both concerns. The default inventory points to the raw directory so ingress can run without extra flags. Converge runs pass explicit `-i` flags for onboard and normalized.

```ini
# ansible.cfg
[defaults]
roles_path =./ingress/roles:./converge/roles:~/.ansible/roles:/usr/share/ansible/roles
inventory =./inventories/raw
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

The `roles_path` includes both `ingress/roles` and `converge/roles` so either concern can find its own roles, plus the shared Galaxy roles.

## Ingress

### 00_discover.yml

Find raw nodes and populate the raw inventory. Only needed for generated sources (nmap, custom API). Plugin-based sources (Incus, LXD, Docker, cloud) discover at runtime via their inventory plugin config and skip this playbook entirely.

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

Make it manageable. Five plays: validate and promote, bootstrap Python, converge baseline, transition to SSH, verify. SSH-ready sources skip plays 2 and 4 via `when` conditions. Non-SSH sources run all five.

```yaml
#!/usr/bin/env ansible-playbook
---
- name: validate and promote raw nodes
 hosts: raw
 gather_facts: no

 tasks:
 - name: wait for SSH (SSH-ready sources)
 wait_for:
 host: "{{ ansible_host | default(inventory_hostname) }}"
 port: 22
 timeout: 30
 delegate_to: localhost
 when: ansible_connection | default('ssh') in ['ssh', 'paramiko_ssh', 'smart']

 - name: confirm reachability (Incus sources)
 command: "incus exec {{ inventory_hostname }} -- true"
 delegate_to: localhost
 when: ansible_connection | default('ssh') == 'community.general.incus'
 changed_when: false

 - name: confirm reachability (libvirt sources)
 command: "virsh dom-state {{ inventory_hostname }} --running"
 delegate_to: localhost
 when: ansible_connection | default('ssh') == 'community.libvirt.libvirt'
 changed_when: false

 - name: promote to onboarded group
 add_host:
 name: "{{ item }}"
 ansible_host: "{{ hostvars[item].ansible_host | default(item) }}"
 groups:
 - onboarded
 - "{{ target_group | default('ungrouped') }}"
 loop: "{{ ansible_play_hosts }}"

- name: bootstrap Python on non-SSH sources
 hosts: onboarded
 gather_facts: no

 tasks:
 - name: install Python
 raw: "apt-get update && apt-get install -y python3"
 when: ansible_connection | default('ssh') not in ['ssh', 'paramiko_ssh', 'smart']

- name: converge onboard baseline
 hosts: onboarded
 become: "{{ ansible_become | default('yes') }}"
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

- name: transition to SSH connection
 hosts: onboarded
 gather_facts: no

 vars:
 source_connection: "{{ ansible_connection | default('ssh') }}"

 tasks:
 - name: switch connection to SSH as initial user
 set_fact:
 ansible_connection: ssh
 ansible_user: "{{ initial_user | default('initial') }}"
 ansible_ssh_private_key_file: "{{ initial_ssh_key_file }}"
 ansible_become: yes
 when: source_connection not in ['ssh', 'paramiko_ssh', 'smart']

 - name: reset connection to apply new settings
 meta: reset_connection
 when: source_connection not in ['ssh', 'paramiko_ssh', 'smart']

- name: verify SSH and sudo
 hosts: onboarded
 gather_facts: no

 tasks:
 - name: confirm SSH login
 ping:

 - name: confirm passwordless sudo
 command: sudo -n true
 changed_when: false
```

### Raw Inventory Structure

The raw inventory supports both plugin-based and generated discovery. Source-specific connection variables live in `group_vars` keyed to the source's group.

```text
inventories/raw/
├── hosts.yml # generated by 00_discover.yml (nmap, API)
├── incus.yml # community.general.incus plugin config
├── group_vars/
│ ├── all.yml # shared raw vars (ansible_python_interpreter, etc.)
│ ├── incus.yml # ansible_connection: community.general.incus
│ ├── libvirt.yml # ansible_connection: community.libvirt.libvirt
│ └── raw.yml # ansible_connection: ssh (default for generated)
└── host_vars/
```

```yaml
# inventories/raw/group_vars/incus.yml
ansible_connection: community.general.incus
ansible_user: root
ansible_become: no
```

```yaml
# inventories/raw/group_vars/raw.yml
ansible_connection: ssh
ansible_user: root
ansible_become: yes
```

## Converge

### 20_normalize.yml

Make it compliant. No source-specific logic. Assumes SSH as `initial` with passwordless sudo.

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

Make it useful. No source-specific logic.

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

## Usage

### Ingress (per source)

```bash
# Incus (plugin-based, auto-discovered)
ansible-playbook \
 -i inventories/raw/incus.yml \
 -i inventories/onboard/dev \
 ingress/playbooks/10_onboard.yml \
 -l 'ex2-test*' \
 -e target_group=webservers

# nmap (generated, run discovery first)
ansible-playbook \
 -i inventories/raw \
 ingress/playbooks/00_discover.yml \
 -e discover_source=subnet \
 -e discover_subnet=192.168.1.0/24

ansible-playbook \
 -i inventories/raw \
 -i inventories/onboard/dev \
 ingress/playbooks/10_onboard.yml \
 -e target_group=webservers
```

### Converge

```bash
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

### site.yml

A root-level `site.yml` can chain all stages, but ingress and converge may need different `-i` flags. Two options:

**Option 1: No site.yml.** Run stages explicitly with the right inventories. This is the simplest and most honest approach — the `-i` flags document which sources are involved.

**Option 2: site.yml with import_playbook.** Works if all inventories are passed on the command line. The playbook imports from both directories:

```yaml
#!/usr/bin/env ansible-playbook
---
- import_playbook: ingress/playbooks/00_discover.yml
- import_playbook: ingress/playbooks/10_onboard.yml
- import_playbook: converge/playbooks/20_normalize.yml
- import_playbook: converge/playbooks/30_specialize.yml
```

```bash
ansible-playbook \
 -i inventories/raw \
 -i inventories/onboard/dev \
 -i inventories/normalized/dev \
 site.yml \
 -e target_group=webservers \
 -e specialize_role=web-server
```

## Why Option A Over Alternatives

### vs. Shared playbooks/ and roles/ (v0.1.3)

v0.1.3 puts all playbooks in a single `playbooks/lifecycle/` directory and all roles in a single `roles/` directory. There is no structural boundary between ingress and converge. The risk is conditional logic leaking: a `when: ansible_connection ==...` in `20_normalize.yml` that someone added "just this once" and never removed.

Option A makes the boundary physical. A converge playbook that needs `community.general.incus` has to reach across the directory divide, which is a code review signal.

### vs. Two repos (Option B/C)

Two or three repos enforce the boundary at the git level but add real cost: cross-repo path management, separate `ansible.cfg` files, write operations that cross boundaries, and a multi-step checkout. For a single operator, the overhead exceeds the benefit.

Option A gives you 90% of the separation at 10% of the cost. The boundary is convention enforced by directory structure, not by git, but it is still a boundary that requires deliberate effort to cross.

## Tradeoffs

| Aspect | Assessment |
|--------|------------|
| Boundary enforcement | Directory-level, not git-level. A determined developer can cross it, but it is visible in review. |
| Familiarity | Unconventional. Dual `playbooks/` and `roles/` directories are not a standard Ansible layout. Self-documenting once you see it. |
| Inventory coupling | Shared. Both concerns read the same inventory tree. This is a feature: the handoff is data, not code. |
| Path complexity | Low. Single repo, single `ansible.cfg`, relative paths work as expected. |
| Reversibility | High. If ingress grows to the point of needing its own repo, the split is a `git mv` away. |
~~~

Ready to fold this into v0.1.4 of the controller document, or do you want to iterate on the structure first?