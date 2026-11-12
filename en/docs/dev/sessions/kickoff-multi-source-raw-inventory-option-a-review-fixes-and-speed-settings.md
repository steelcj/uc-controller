# Kickoff: Multi-Source Raw Inventory, Option A Review Fixes, and Speed Settings

You are working in the `uc-controller` repository, an Ansible controller configuration. This prompt asks you to implement two sets of notes: the multi-source raw inventory structure with the Option A review fixes, and the Ansible speed settings. Work through the phases in order and stop at each checkpoint.

## Source documents

Both should be in `en/docs/dev`. If either is missing, ask before starting.

- `multi-source-raw-inventory-structure-impact-and-review-notes.md`
- `ansible-speed-optimisations-overview-v0.1.2.md`

Where this prompt and a source document disagree, this prompt wins. The disagreements are deliberate and are listed in "Corrections to the source documents".

## Project context

- The project is in its dev phase. There are no production nodes. Test nodes are Incus containers and VMs on this machine and can be rebuilt freely.
- Lifecycle: `00_discover` then `10_onboard` (ingress), then `20_normalize` and `30_specialize` (converge). Inventories are staged: `inventories/raw/` (flat, no environments), `inventories/onboard/<env>/`, `inventories/normalized/<env>/`.
- A raw node is reached however its source provides (Incus connection as root, or SSH as root). Onboarding creates the `initial` user, and every later stage connects over SSH as `initial` with passwordless sudo.
- Onboarding is not idempotent, and that is accepted. Do not try to make `10_onboard.yml` safe to rerun against an already onboarded node.
- Incus instances are named by OS code only (`deb13`, `ubu2404`, `rky9`) and are never renamed. State lives in snapshots: `raw` is the origin, then `10-onboarded`, `20-normalized`, `30-<role>`, matching the playbook numbers. `tmp-` is scratch.
- `scripts/promote_node.py` and `scripts/demote_node.py` move host entries between stage inventories. Python in `scripts/` must run on Linux, macOS and Windows.

## Ground rules

- Determine the layout first. If `ingress/` and `converge/` exist at the repo root, you are on the Option A layout, use those paths. If the lifecycle playbooks are still under `playbooks/lifecycle/`, stop and ask whether to branch from `option-a` instead. Paths below use the Option A layout, map them if told to proceed on the old one.
- One branch per phase, created from the branch you were told to start on. Small commits with clear messages. Never push, never merge, never rebase shared branches. I review, merge and push by hand.
- Do not edit anything under `roles/` (vendored Galaxy roles) or `vaults/`. Do not print secrets or vault contents.
- Ask before the first `incus restore`, `incus delete` or `incus launch` of the session, and name the instances involved. Only restore instances that have a `raw` snapshot.
- Do not add files, groups or config for sources that have no node today. Scaffolding for libvirt, Proxmox and AWS is out of scope.
- If something in the repo contradicts this prompt, the repo is the truth. Report the contradiction rather than forcing the plan.
- Documents follow the house markdown style: commas rather than em dashes, no heading numbers, no horizontal rules, no hard line wraps in prose, subsections as the next lower heading level rather than bolded lead-ins.

## Observations to verify

These come from reading GitHub `main` at `6fd50af`, which may be behind the local repo. Confirm or correct each one during reconnaissance.

- `inventories/raw/incus.yml` is a dynamic inventory plugin config (`community.general.incus`) that puts running instances in the `raw` group. It does not create an `incus` group, so check whether `inventories/raw/group_vars/incus.yml` is being applied at all.
- `00_discover.yml` overwrites `inventories/raw/hosts.yml` on every run, for both the subnet and cloud sources. Its destination path is built from `playbook_dir` with a single `..`, which may not resolve to the repo's `inventories/` directory.
- `10_onboard.yml` runs `robertdebock.bootstrap` on every host unconditionally. That role also installs sudo, which the users role depends on.
- `firewall_rules_onboard` is not defined in any inventory. The plays build a `firewall_rules` variable, but `robertdebock.firewall` reads `firewall_services`, so the stage accumulation currently has no effect. `firewall_rules_normalize` in `inventories/normalized/dev/group_vars/all.yml` uses a `source` field the role cannot express.
- `20_normalize.yml` lists roles that are commented out of `requirements.yml` (`pam`, `limits`, `timezone`, `motd`, `chrony`), so it cannot run as written.
- `ansible.cfg` already has fact caching (in `/tmp/ansible_facts`), `gathering = smart`, and `stdout_callback = default` with `callback_result_format = yaml`. It has no pipelining, forks or profiling callback.

## Corrections to the source documents

- The bootstrap default is `true`, not `false`. Skipping bootstrap on an SSH-reached node would leave it without sudo. A source opts out only when its images are known to ship Python and sudo.
- There is no `raw/group_vars/raw.yml` in the target layout. Shared defaults go in `raw/group_vars/all.yml`.
- The management user is `initial`, so any sudoers line is `Defaults:initial !requiretty`, not `Defaults:ansible`.
- Do not set `stdout_callback = yaml`. Keep the existing default callback with `callback_result_format = yaml`.
- Do not apply the "Loops vs. include_tasks" advice. A looped include is slower than a looped module.
- Do not install Mitogen.
- Do not set `ssh_args` or `control_path` unless you observe a socket path error. Ansible's defaults already enable ControlMaster and ControlPersist.
- Use `forks = 20`, not 50. The test nodes share this machine with the controller.
- The fact cache moves out of `/tmp`.
- Keep `strategy = linear` as the config default. `strategy: free` is set per play, only on the converge plays in `20_normalize.yml` and `30_specialize.yml`.

## Reconnaissance

Make no changes in this phase.

- Report the layout, current branch, Ansible version in the active venv, and whether `ansible.posix` and `community.general` are available.
- Run `ansible-inventory -i inventories/raw --graph` and `--host` for one Incus node. Report which groups and connection variables the node actually gets.
- Confirm or correct every item in "Observations to verify".
- Report how `promote_node.py` handles a host that exists only through the Incus plugin and is absent from `hosts.yml`, and whether the persistence workflow (`add_host` is in memory for one run, `promote_node.py` persists) is already documented.
- Search the ingress playbooks for conditions on `ansible_connection`, especially negative ones such as `!= 'ssh'`. List them.
- List which Incus instances exist and which have a `raw` snapshot.

### Checkpoint

Post the report and a short list of anything that changes the plan. Wait for my go-ahead.

## Inventory structure

Branch: `feat/multi-source-raw-inventory`.

### Invariant

Every raw host is a member of `raw` and of exactly one source group. `10_onboard.yml` keeps targeting `hosts: raw`.

### Tasks

- Make the Incus plugin config place instances in an `incus` group as well as `raw`, so `raw/group_vars/incus.yml` applies. Keep the filename the plugin requires.
- Restructure `inventories/raw/hosts.yml` as a hand-maintained static file in which source groups are children of `raw`. Include only `incus` and `discovered`. No playbook may write to this file after this phase.
- Keep root-level files in `inventories/raw/` for dynamic plugin configs and generated inventories only, with a header comment in each stating which it is and what writes it.
- Add `needs_python_bootstrap: true` to `raw/group_vars/all.yml` with a comment explaining the opt-out rule. Add `raw/group_vars/discovered.yml` for plain SSH as root.
- Leave `onboard/` and `normalized/` untouched.

### Verify

`ansible-inventory --graph` shows each Incus node under both `raw` and `incus`, and `--host` shows the Incus connection variables. The static file parses with no warnings.

## Review fixes

Branch: `fix/option-a-review`.

### Discovery must not overwrite hand-maintained inventory

- The subnet source writes only `inventories/raw/discovered.yml`, under the `discovered` group. Point the placeholder cloud source at its own file so it cannot clobber anything, and do no further work on it.
- Fix the destination path so it resolves inside the repo regardless of where the playbook lives.
- Update `promote_node.py` and `demote_node.py` so a host can be found in any static inventory file in the source stage, not only `hosts.yml`. Do not change how plugin-only hosts are handled unless reconnaissance showed it is broken, in which case propose a fix first.

### Provisional names for discovered nodes

- Generated names become `disc-<ip with dots as hyphens>` and carry a host variable `name_provisional: true`.
- Do not implement renaming. Write a short proposal in the design document for renaming once at onboarding, before the onboard inventory entry is written.

### Bootstrap condition

- Gate the bootstrap play on `needs_python_bootstrap | default(true)`.
- Replace any negative `ansible_connection` conditions found in reconnaissance with a per-source variable declared in that source's `group_vars`. If there are none, say so and add nothing.

### Firewall variable traceability

- Do not redesign the firewall layering in this phase.
- Add a comment in each converge playbook naming the file where each `firewall_rules_<stage>` variable is expected to live.
- Write up the mismatch with `robertdebock.firewall` and two options: accumulate stage-namespaced `firewall_services_<stage>` lists that the role can consume, or change to a role that supports source restrictions. Give a recommendation and wait for my decision.

### Persistence and snapshot alignment

- If the persistence workflow is not documented, add a section to the design document: what `add_host` does, when to run `promote_node.py`, and what state is lost if it is skipped.
- Document the snapshot alignment: which snapshot to take after each playbook succeeds, and the restore-and-resume procedure. The procedure must include moving the inventory entry back with `demote_node.py` and flushing the fact cache, because restoring a snapshot changes neither.

### Verify

- Run discovery twice with a hand-added entry in `hosts.yml` and confirm the entry survives.
- Restore the test instances to `raw`, run `10_onboard.yml` end to end, and confirm SSH as `initial` works.
- `ansible-playbook --syntax-check` on every playbook. `20_normalize.yml` is expected to fail on missing roles. Report it, do not fix it.

### Checkpoint

Summarise what changed, show the firewall options, and wait.

## Speed settings

Branch: `perf/ansible-cfg`.

### Baseline

- Enable `callbacks_enabled = ansible.posix.profile_tasks` and leave it on.
- Record two timings: `10_onboard.yml` from restored `raw` snapshots, and a throwaway play of about 30 trivial tasks run over SSH as `initial` against the onboarded nodes. The second matters because most of these settings only help on the SSH path. Do not commit the throwaway play.

### Changes

Apply one per commit, in this order, and re-time after each.

- Pipelining. Confirm it is active with `ansible-config dump --only-changed`, since the valid config section depends on the Ansible version. Add the `requiretty` drop-in only if a target actually fails without it, as its own file in `/etc/sudoers.d/` validated with `visudo -cf %s`.
- Fact cache location: a per-user directory such as `~/.ansible/fact_cache/uc-controller`.
- Fresh facts during onboarding. Instance names are reused across rebuilds, and the SSH switch in `10_onboard.yml` takes the node's address from gathered facts, so cached facts from a previous instance of the same name can point at a stale address. Make the onboard converge play gather facts explicitly with a `setup` task rather than relying on `gathering = smart`.
- `forks = 20`.
- `strategy: free` on the converge plays in `20_normalize.yml` and `30_specialize.yml` only.
- Update `roles_path` for the Option A layout if it has not been done.
- Leave `host_key_checking = False`, with a comment that it must be revisited before any non-test node is managed.

### Verify

Report a table of before and after timings per change. If a change shows no measurable gain on this fleet, keep it only if it is harmless, and say so plainly instead of quoting the source document's speedup figures.

## Documentation

Do this on the branch of the phase each item belongs to.

- Design document (`en/docs/uc-controller-v0.1.3.md` or its current successor): add a new version following the file's existing changelog and versioning pattern, covering the raw layout, the source group invariant, why `raw` has no environment split, how to add a new source, and the sections named above.
- Naming scope note: add the scope paragraph from the inventory notes to the Incus instance naming document if it is in the repo. If it is not, put it in the design document and tell me.
- Speed overview: produce the next version of the speed document with the corrections from this prompt applied and the measured timings replacing the generic estimates where you have them.
- Session record: add a record of this session under `en/docs/`, following whatever pattern is already there.

## Final report

- Branches and commits created, in merge order.
- Each review item from the summary table in the inventory notes, with its status: fixed, already done, deferred, or needs my decision.
- The timing table.
- Open questions and anything you chose not to do, with the reason.
