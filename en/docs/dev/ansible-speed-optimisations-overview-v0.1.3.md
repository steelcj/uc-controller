# Ansible Speed Optimizations - Overview

Version: 0.1.3

## Changelog

### v0.1.2 → v0.1.3

| Change | Description |
|--------|-------------|
| Measured, not estimated | The settings were applied to uc-controller one per commit and timed on two Incus containers (`deb13`, `ubu2404`); the measured results replace the generic speedup estimates for this fleet |
| forks | 20, not 50: the test nodes share the controller's machine |
| requiretty | The exemption names the management user, `Defaults:initial !requiretty`, and is added only if a target fails without it; none did |
| Callback | Keep `stdout_callback = default` with `callback_result_format = yaml`; `stdout_callback = yaml` is not used. `profile_tasks` is enabled by its full name, `ansible.posix.profile_tasks` |
| SSH multiplexing | `ssh_args` and `control_path` are left at Ansible's defaults, which already enable ControlMaster and ControlPersist, unless a socket path error is observed; none was |
| Fact cache | Moved out of `/tmp` to a per-user directory |
| Fresh facts during onboarding | New section: the onboard converge play gathers facts with an explicit `setup` task |
| Strategy | `linear` stays the config default; `strategy: free` is set per play, on the converge plays only |
| Removed | Mitogen (not installed) and the "Loops vs. include_tasks" advice (a looped include is slower than a looped module) |

## The Problem

Every Ansible task on every host costs connection and transfer overhead on top of the actual work. A playbook with 30 tasks across 100 hosts is 3,000 remote operations, and if each carries half a second of overhead, that is 25 minutes before any configuration happens. The settings below attack that overhead at the connection, execution, and fact layers.

On a small fleet the picture is different, and the measurements below show it: with two nodes, the long tasks are package installs, and most settings change little. They are still worth having, because they cost nothing and the fleet will grow.

## How It Was Measured

- `ansible.posix.profile_tasks` is enabled and left on, so every run ends with per-task timings.
- Throwaway play: 30 trivial tasks (`command`, `stat`, `file`), with become, over SSH as `initial` against both nodes. Each measurement is four runs, with a 65-second pause before each so the SSH control sockets have expired and every run starts cold, and reports the median of the middle two. Not committed.
- Full runs: `10_onboard.yml` from the `raw` snapshot, and `20_normalize.yml` from the `10-onboarded` snapshot with the nodes' cached facts flushed, once before the changes and once with all of them applied.
- The controller and both nodes run on one laptop, so timings vary by several percent between runs. The first pipelining round was noisy (7.9 s to 13.2 s); a paired rerun, alternating pipelining off and on four times each, gave the figure below.

## Results

| Change | Throwaway play (median) | Gain on this fleet | Kept |
|--------|------------------------|--------------------|------|
| Baseline | 8.93 s (paired rerun: 8.24 s) | | |
| `pipelining = True` | 6.98 s | About 15% | Yes |
| Fact cache moved to `~/.ansible/fact_cache/uc-controller` | 7.06 s | None; the play gathers no facts | Yes, harmless and out of `/tmp` |
| Fresh facts in the onboard converge play | 7.07 s | None; affects onboarding only, for correctness | Yes |
| `forks = 20` | 7.48 s | None; two nodes already fit in the default five | Yes, harmless |
| `strategy: free` on converge plays | 7.00 s | None; the throwaway play is not a converge play | Yes, harmless |

| Full run | Before | After |
|----------|--------|-------|
| `10_onboard.yml` from `raw`, two nodes | 192.8 s | 162.2 s (about 16% less) |
| `20_normalize.yml` from `10-onboarded`, two nodes | 279.1 s | 260.4 s (about 7% less, not attributable) |

Onboarding is the comparison to trust: it runs linear in both cases, and its slowest tasks (package installs) took about the same time before and after, so the saving comes from cheaper task overhead across its roughly 240 tasks, which pipelining provides. Normalize is not comparable in the same way. Its slowest task, the SELinux policy install on Debian, took 246 s in the baseline and 34 s in the final run with no setting that touches package downloads, so it is dominated by network and mirror speed. Under `strategy: free`, `profile_tasks` also stops being a per-task breakdown: it charges each task until the next task starts on any host, and credited 191 s to an rsyslog restart. Read normalize's per-task profile as indicative only once `free` is on.

## Connection Layer

### Pipelining

Without pipelining, Ansible copies each module to a temporary file on the target, runs it, and deletes it. With pipelining it sends the module through the open SSH session. Measured here: about 15% off the throwaway play.

```ini
# ansible.cfg
[connection]
pipelining = True
```

The valid section depends on the Ansible version. In ansible-core 2.21 the setting is accepted under `[defaults]`, `[connection]` and `[ssh_connection]`; confirm it is active with `ansible-config dump --only-changed`, which should list `ANSIBLE_PIPELINING ... = True`.

Pipelining with become needs sudo without `requiretty`. Debian and Ubuntu do not set it, and no target failed. If one does, exempt only the management user, in a file of its own validated before it is installed:

```text
# /etc/sudoers.d/initial-notty
Defaults:initial !requiretty
```

```bash
visudo -cf /etc/sudoers.d/initial-notty
```

### SSH Multiplexing

Ansible's defaults already use ControlMaster and ControlPersist, so a second play reuses the first play's connection. Leave `ssh_args` and `control_path` unset unless an error about the control socket path length appears; only then shorten `control_path`.

### SSH Key Type

Ed25519 keys are cheaper to compute than RSA. The `initial` user's key is already Ed25519 (`~/.ssh/gradus-raw-initial-id_ed25519`).

## Execution Layer

### forks

How many hosts Ansible manages in parallel. The default is 5. uc-controller uses 20: enough for the fleet to grow, and modest because the test nodes share the controller's machine. Raise it with the fleet, within the controller's CPU and memory.

```ini
[defaults]
forks = 20
```

### Strategy

`linear` runs each task on every host before any host moves on; `free` lets each host run ahead. The config default stays `linear`. `strategy: free` is set per play, only on the converge plays, where each node is independent:

| Playbook | Strategy | Reason |
|----------|----------|--------|
| `00_discover.yml` | linear | Runs on localhost only |
| `10_onboard.yml` | linear | The SSH switch must complete on every host before the verify play |
| `20_normalize.yml`, validation play | linear | Its `add_host` loop runs once for the play |
| `20_normalize.yml`, converge play | free | Each node converges independently |
| `30_specialize.yml` | free | Each node converges independently |

### async Tasks

`async` with `poll: 0` stops one slow host from blocking others on a long task. Not used yet.

## Facts Layer

### Fact Caching

```ini
[defaults]
gathering = smart
fact_caching = jsonfile
fact_caching_connection = ~/.ansible/fact_cache/uc-controller
fact_caching_timeout = 3600
```

`gathering = smart` gathers only when the cache has no current facts for the host. The cache lives in a per-user directory rather than `/tmp`, where it was shared and cleared on reboot. In ansible-core 2.21 each host's file is prefixed, for example `s1_deb13`. `scripts/reset_inventories.py` reads the location from `ansible.cfg`.

### Fresh Facts During Onboarding

Caching facts is unsafe where they may be stale. Incus instance names are reused across rebuilds, and `10_onboard.yml` takes the node's SSH address from gathered facts. Under `gathering = smart`, a cached fact from an earlier instance of the same name could point at a stale address. The onboard converge play therefore sets `gather_facts: no` and gathers with an explicit `setup` task as its first pre-task, so onboarding always uses fresh facts.

### gather_facts: no

A play that needs no facts should not gather them. The ingress validation plays already do this.

## Playbook Design Layer

### Role Order and Module Choice

Put cheap roles before expensive ones, so an early failure costs little. Prefer purpose-built modules over `shell` and `command`: they are idempotent and avoid needless changes. The measured runs show where time actually goes on this fleet:

| Slowest tasks, baseline | Time |
|-------------------------|------|
| `robertdebock.selinux : Install required packages` (normalize, Debian installs the SELinux policy) | 246.2 s |
| `robertdebock.update : Update all software (apt)` (onboard) | 27.1 s |
| `robertdebock.bootstrap : Install bootstrap packages (raw)` (onboard) | 25.1 s |
| `robertdebock.locale : Install requirements` (onboard) | 18.6 s |
| `robertdebock.openssh : Install openssh` (onboard) | 17.5 s |

Package installs dominate. No connection setting changes that; a local package cache or mirror would.

### serial for Rolling Changes

For anything that must not hit every host at once (restarts, canaries), use `serial` to limit the batch. It limits blast radius rather than saving time.

## What Not to Do

- Do not set forks far above the controller's CPU count.
- Do not use `strategy: free` in `10_onboard.yml`; the verify play would reach a host before its connection has switched.
- Do not set `stdout_callback = yaml`; use the default callback with `callback_result_format = yaml`.
- Do not replace a looped module with a looped `include_tasks` for speed; the include is slower.
- Do not install Mitogen.
- Do not disable fact caching, except where facts may be stale, as in onboarding.

## uc-controller ansible.cfg

```ini
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
