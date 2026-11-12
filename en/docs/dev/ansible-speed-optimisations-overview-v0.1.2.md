# Ansible Speed Optimizations - Overview

## The Problem

Every Ansible task on every host requires an SSH connection, module transfer, execution, and result return. At scale, the overhead of connection and transfer dominates the actual work. A playbook with 30 tasks across 100 hosts is 3,000 SSH operations. If each handshake costs 0.5 seconds, that's 25 minutes of pure overhead before any actual configuration happens.

The optimizations below attack this problem at four layers:

* connection
* execution
* inventory
* playbook design.

## Connection Layer

### pipelining = True

The single most impactful setting. Without pipelining, Ansible opens an SSH connection, transfers the module as a temporary file, executes it, and cleans up. With pipelining, Ansible pipes the module directly through a single SSH session, eliminating the file transfer step.

```ini
# ansible.cfg
[defaults]
pipelining = True
```

**Requirement:** `requiretty` must be disabled in sudoers. On most modern systems this is already the case. If you see errors about sudo requiring a tty, add to your sudoers:

```
Defaults:ansible !requiretty
```

#### Implementation Details

To apply this fix securely without compromising the entire system, the line should be placed in a dedicated file within the `/etc/sudoers.d/` directory (e.g., `/etc/sudoers.d/ansible`).

```
Defaults:ansible !requiretty
```

#### Key Benefits

- **Compatibility**: Allows **SSH pipelining** to function correctly with Ansible, which significantly improves execution performance by reducing SSH round trips.
- **Security**: It restricts the TTY exemption **only to the `ansible` user**, leaving the `requiretty` protection active for all other users on the system.
- **Best Practice**: It is preferred over globally commenting out `Defaults requiretty`, which is considered a security risk on many hardened systems.

#### Verification

After adding the configuration, you can validate the syntax using:

```
sudo visudo -cf /etc/sudoers.d/ansible
```

**Impact:** Roughly 2-3x speedup on task-heavy playbooks. This is the production-safe descendant of what Michael DeHaan's "fireball mode" experiment was targeting in 2012 [1].

### SSH Multiplexing (ControlMaster)

Ansible uses SSH multiplexing by default, but you can tune it. ControlMaster reuses a single SSH connection for multiple sessions to the same host, eliminating repeated key exchanges.

```ini
# ansible.cfg
[ssh_connection]
control_path = %(directory)s/%%h-%%p-%%r
ssh_args = -o ControlMaster=auto -o ControlPersist=60s
```

The `control_path` template must be short enough to avoid socket path length limits (max 104 characters on Linux). The default Ansible template sometimes exceeds this on systems with long usernames or hostnames.

**Impact:** Marginal on its own, but compounds with pipelining. `ControlPersist=60s` keeps connections alive between plays, so the second play in a playbook reuses the first play's connection.



### SSH Key Type

Ed25519 keys are faster to compute than RSA. If your infrastructure allows it, use ed25519 for the `initial` management user key.

```sh
ssh-keygen -t ed25519 -f ~/.ssh/gradus-raw-initial-id_ed25519
```

**Impact:** Small per-connection, but measurable at scale. RSA-4096 key exchange is noticeably slower than ed25519 on low-CPU hosts.

## Execution Layer

### forks

Controls how many hosts Ansible manages in parallel. Default is 5. For any fleet over 10 hosts, this is too low.

```ini
# ansible.cfg
[defaults]
forks = 50
```

**Tuning:** Set forks to roughly match your host count, capped by your controller's CPU and memory. Each fork is a process. On a 4-core controller, 50-100 forks is reasonable. Beyond that, context switching dominates.

**Impact:** Linear until you hit controller CPU limits. 100 hosts with `forks=5` runs 20 batches sequentially. With `forks=50`, it runs 2 batches. 10x wall-clock improvement.

### strategy = free

By default, Ansible uses the `linear` strategy: every host completes a task before any host moves to the next. If one host is slow on a task, all others wait.

The `free` strategy lets each host proceed independently. A fast host can finish the entire playbook while a slow host is still on task 3.

```ini
# ansible.cfg
[defaults]
strategy = free
```

Or per-playbook:

```yaml
- name: converge onboard baseline
 hosts: onboarded
 strategy: free
 become: yes
```

**When to use:** Mixed hardware (some hosts are faster), heterogeneous workloads (some hosts skip tasks via `when`), or when you don't care about synchronized task ordering.

**When not to use:** When task ordering across hosts matters (rolling updates, canary deployments, anything that needs host A to finish before host B starts). The UC-Gradus lifecycle stages are safe candidates for `free` because each stage is independent per host.

**Impact:** Highly variable. On homogeneous fleets, near zero. On mixed fleets, can cut wall-clock time by 30-50%.

### Mitogen for Ansible

A third-party extension that replaces Ansible's execution pipeline with persistent Python interpreters and efficient message-based  Remote Procedure Call (RPC). It keeps a Python process alive on each target and sends modules to it rather than bootstrapping Python fresh per task.

```sh
pip install mitogen
```

```ini
# ansible.cfg
[defaults]
strategy_plugins = ~/.local/lib/python3.11/site-packages/ansible_mitogen/plugins/strategy
strategy = mitogen_linear
```

**Impact:** 2-7x speedup depending on playbook shape. Most dramatic on task-heavy playbooks with many small modules (file, lineinfile, service).

**Caveats:** Not maintained by Ansible. Compatibility lags behind new Ansible releases. Test before adopting in production. Some modules with unusual execution patterns don't work with Mitogen.

### async Tasks

For long-running tasks (large package installs, database migrations, backups), use `async` to let the task run in the background while Ansible continues with other hosts or tasks.

```yaml
- name: install large package set
 apt:
 name: "{{ heavy_package_list }}"
 state: present
 async: 300
 poll: 0
```

**Impact:** Not a speed optimization per se, but prevents one slow host from blocking the entire run. Combined with `strategy: free`, it lets fast hosts finish while slow hosts catch up.

## Inventory and Facts Layer

### Fact Caching

By default, Ansible gathers facts on every run. For 100 hosts, that's 100 SSH connections just to collect system information before any real work starts. Fact caching stores facts between runs so they're only collected when stale.

```ini
# ansible.cfg
[defaults]
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /tmp/ansible_facts
fact_caching_timeout = 3600
```

`gathering = smart` means Ansible only gathers facts if they're not cached or the cache has expired. `fact_caching_timeout = 3600` keeps facts for one hour.

**Alternatives:** Redis or memcached for multi-controller setups. JSON file is fine for a single controller.

**Impact:** Eliminates the fact-gathering overhead on repeat runs. For a 100-host fleet, this can cut 30-60 seconds off every run after the first.

### gather_facts: no

If a play doesn't need facts, turn them off. The ingress playbooks already do this for validation plays.

```yaml
- name: validate and promote raw nodes
 hosts: raw
 gather_facts: no
```

**Impact:** Saves one SSH round-trip per host per play. Across a five-play onboarding with 20 hosts, that's 100 eliminated connections.

## Playbook Design Layer

### Role Order

Ansible runs roles in the order listed. If a role fails early, subsequent roles don't run. Put roles most likely to fail or most critical to succeed first.

For speed specifically, put lightweight roles before heavyweight ones. A `lineinfile` or `service` role is cheap. A `apt update && apt upgrade` role is expensive. If the cheap role fails, you've saved the expensive role's execution time on every host.

### Module Selection

Some modules are faster than others for the same job:

| Task | Slow | Fast |
|------|------|------|
| Line in file | `shell: echo >> /etc/hosts` | `lineinfile:` |
| Package install | `shell: apt-get install` | `apt:` (idempotent) |
| Service restart | `shell: systemctl restart` | `service:` or `systemd:` |
| File copy | `shell: cp` | `copy:` or `template:` |
| Multiple files | Multiple `copy:` tasks | `copy:` with `loop` or synchronize |

The `shell` and `command` modules are always slower than purpose-built modules because they can't be idempotent without manual `changed_when`/`creates` guards, and they often trigger unnecessary changes.

### Loops vs. include_tasks

Large loops (100+ iterations) are slow because Ansible processes them serially within a task. For large loops, `include_tasks` with `loop` is faster because each iteration is a separate task that can benefit from pipelining.

```yaml
# Slow: 200 iterations in one task
- name: create users
 user:
 name: "{{ item.name }}"
 state: present
 loop: "{{ user_list }}"

# Faster: 200 separate tasks via include
- name: create users
 include_tasks: create_user.yml
 loop: "{{ user_list }}"
```

**Tradeoff:** `include_tasks` produces noisier output. Use it only when loop size is large enough to matter (50+).

### Batch Size for Rolling Updates

For playbooks that must be sequential (rolling restarts, canary deploys), use `serial` to control batch size.

```yaml
- name: restart web servers
 hosts: webservers
 serial: 5
 tasks:
 - name: restart nginx
 service:
 name: nginx
 state: restarted
```

This isn't a speed optimization, but it prevents speed from causing problems. Running 100 hosts in parallel during a restart takes down all 100 at once. `serial: 5` limits blast radius.

## UC-Gradus Controller Recommendations

### ansible.cfg

```ini
[defaults]
roles_path =./ingress/roles:./converge/roles:~/.ansible/roles:/usr/share/ansible/roles
inventory =./inventories/raw
host_key_checking = False
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /tmp/ansible_facts
fact_caching_timeout = 3600
forks = 50
pipelining = True
strategy = linear
stdout_callback = yaml
callbacks_enabled = profile_tasks

[ssh_connection]
control_path = %(directory)s/%%h-%%p-%%r
ssh_args = -o ControlMaster=auto -o ControlPersist=60s

[privilege_escalation]
become = True
become_method = sudo
become_user = root
become_ask_pass = False
```

### Per-Playbook Strategy

| Playbook | Strategy | Rationale |
|----------|----------|-----------|
| 00_discover.yml | linear | Single host (localhost), no benefit from free |
| 10_onboard.yml | linear | SSH transition must complete per host before verify |
| 20_normalize.yml | free | Independent per-host, mixed hardware likely |
| 30_specialize.yml | free | Independent per-host, role assignment varies |

## What Not to Do

- **Don't set `forks = 500` on a 4-core controller.** You'll spend more time context-switching than executing. Match forks to CPU.
- **Don't use `strategy: free` in 10_onboard.yml.** The SSH transition play must complete before the verify play. With `free`, a fast host could reach verify while a slow host is still bootstrapping Python, and the verify play's `ping` would fail because the connection hasn't switched yet.
- **Don't enable Mitogen without testing.** It breaks some modules and lags Ansible releases. Profile first.
- **Don't disable fact caching to "save disk."** The performance cost of re-gathering facts every run far exceeds the disk space of cached facts.

## Measurements

Before optimizing, measure. Ansible's built-in timer callback shows per-task execution time:

```ini
# ansible.cfg
[defaults]
callbacks_enabled = profile_tasks
```

Or run with timing inline:

```bash
time ansible-playbook -i inventories/raw ingress/playbooks/10_onboard.yml -l 'ex2-test*'
```

Profile a full run, identify the slowest tasks, then apply the optimization that addresses that specific bottleneck. SSH overhead → pipelining. Serial execution → forks or free. Fact gathering → fact caching. Module choice → switch to purpose-built modules.

## Summary: Impact Hierarchy

| Optimization | Typical speedup | Risk | Effort |
|--------------|----------------|------|--------|
| forks = 50 | 5-10x at scale | None | One line |
| pipelining = True | 2-3x | Low (needs!requiretty) | One line |
| fact caching | 1.5-2x on repeat runs | None | Three lines |
| strategy = free | 1.3-2x on mixed fleets | Medium (ordering) | One line |
| SSH multiplexing tuning | 1.2-1.5x | None | Two lines |
| Mitogen | 2-7x | High (compatibility) | Install + config |
| gather_facts: no | 1.1-1.3x per play | Low (if facts unused) | Per-play |
| Module selection | Variable | None | Per-task |