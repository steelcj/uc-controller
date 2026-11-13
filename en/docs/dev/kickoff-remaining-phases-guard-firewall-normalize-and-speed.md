# Kickoff Update: Remaining Phases After the Review Checkpoint

This replaces the "Speed settings", "Documentation" and "Final report" sections of the original kickoff. Everything else in the original still applies, including the ground rules and the corrections to the source documents, except where this update says otherwise.

The order has changed. The firewall role and a runnable `20_normalize.yml` now come before the speed work, because timings should be taken against a workflow that has stopped changing, and because `strategy: free` cannot be tested on plays that do not run.

## Decisions from the review checkpoint

- Firewall: Option 2, a small project role. Details are in "Firewall rules role".
- Demotion to raw: it removes the host's entry from the onboard inventory and writes nothing to raw. The change that writes demoted hosts to `raw/discovered.yml` is undone. See "Scripts never add hosts to raw".
- Generated raw files: add `inventories/raw/discovered.yml` and `inventories/raw/cloud.yml` to `.gitignore`.
- Script path in `10_onboard.yml`: yes, resolve `promote_node.py` from the repository root with the same mechanism discovery now uses.
- `inventories/onboard/dev/hosts.yml`: leave the live `deb13` and `ubu2404` entries uncommitted. Do not commit live host entries on any branch in this run, and run the promotion scripts with `--no-commit`.

## Ground rule changes

- You may delete the `vaults/` directory and the vendored `roles/robertdebock.firewall` directory, as described below. All other vendored roles stay untouched.
- Snapshot operations: the first `10-onboarded` snapshot hung and a retry worked. Put a timeout on every `incus snapshot` and `incus restore` call, retry once, and stop and report if it happens again.
- Branches keep stacking. Each new branch starts from the previous one.

## Review additions

Branch: continue on `fix/option-a-review`.

### Scripts never add hosts to raw

Demotion is inventory bookkeeping only. It exists so the inventory can follow a node after a snapshot restore, and it has nothing to do with making onboarding repeatable.

- Raw is what the sources report: the Incus plugin, the hand-maintained `hosts.yml`, and the scan's `discovered.yml`. No script adds a host to any file under `inventories/raw/`.
- Demotion to raw removes the host's entry from the onboard inventory and writes nothing. The node reappears in raw through its source: the plugin lists a running Incus instance, a hand-entered host never left `hosts.yml`, and a scanned host is found by the next scan.
- Undo the change that writes demoted hosts to `raw/discovered.yml`, and update the script tests to match.
- Demotion from normalized to onboard is unchanged: the entry moves back.
- Promotion out of raw still removes a scanned host from `discovered.yml`. That is the one case where a script touches a raw file, and it exists so the host is not listed in two stages until the next scan.
- Add a header comment to each raw file naming what writes it, and record this rule in the design document, including the restore-and-resume procedure where it mentions demotion.

### Re-onboarding guard

- First report what currently prevents a promoted, still-running Incus instance from being listed in `raw` and targeted again by `10_onboard.yml`.
- Add a guard as the first task of the first play in `10_onboard.yml`: a `raw` command that tests whether the `initial` user exists. If it does, print a message naming the host and saying it is already onboarded, and end the play for that host only. Do not fail the run and do not require Python.
- Verify against the nodes as they are now, at `10-onboarded`: a second run of `10_onboard.yml` must skip both hosts and change nothing.
- Do not implement a plugin-side filter. Note in the design document that an Incus config key such as `user.uc_stage`, set at promotion and used in the plugin's `filters`, is a possible second layer, and say whether the plugin's `filters` option supports config keys.

### Remove the vault placeholders

- Confirm nothing in the working tree references `vaults/` apart from the layout tree in the design document.
- Delete the directory in a commit of its own. Remove its line from the layout in the v0.1.4 design document and add one sentence stating that secrets handling is deferred until the first secret exists.

### Housekeeping

- The `.gitignore` entries and the script path change from the decisions above.

## Firewall rules role

Branch: `feat/firewall-rules`.

### Design

- A project role, not a vendored one. Put it where both ingress and converge playbooks resolve it through `roles_path`, and say where you put it.
- It consumes the accumulated `firewall_rules` list that the plays already build. Keep the rule schema from the design document: `name`, `port`, `protocol`, and an optional `source`. A rule without `source` is open to all addresses.
- Backends: `community.general.ufw` on Debian and Ubuntu, `ansible.posix.firewalld` on the Red Hat family. Use the same backend per family that `robertdebock.firewall` was installing, so nothing else on the node changes.
- Default policy: deny incoming, allow outgoing.
- The role is additive. It does not remove rules that are missing from the list. Record that as a known limitation in the design document.

### SSH safety

- Before enabling the firewall or setting the default policy, the role asserts that the list contains a rule for the SSH port in use, and fails with a clear message if it does not.
- Allow rules are applied before the default deny takes effect.
- Define `firewall_rules_onboard` in `inventories/onboard/<env>/group_vars/all.yml` with the SSH rule, and remove `firewall_services`.

### Switch over

- Replace `robertdebock.firewall` in `10_onboard.yml`, `20_normalize.yml` and `30_specialize.yml`. Remove it from `requirements.yml` and delete its vendored directory.
- No migration of existing nodes. Restore both nodes to `raw` and onboard from scratch.
- Check that `scaffold.yml` still matches the variable names.

### Verify

- After onboarding, SSH as `initial` works from the controller, and the node's firewall shows default deny incoming with only the SSH rule.
- A temporary rule with a `source` restriction is reachable from an allowed address and refused from another. Remove the temporary rule afterwards.
- Take fresh `10-onboarded` snapshots, replacing the old ones.

## Runnable normalize stage

Branch: `fix/normalize-runnable`.

### Missing roles

`20_normalize.yml` lists five roles that are not in `requirements.yml`. Apply these defaults unless the repo gives a reason not to, and report what you did:

- `pam`, `limits`, `motd`: remove from the play. There is no stated requirement behind them, and no configuration should be invented.
- `timezone`: remove. The onboard stage already sets the timezone through the locale variables.
- `chrony`: remove the role reference and write a short time sync proposal in the design document covering containers (clock comes from the host), VMs and bare metal, and Debian 13 no longer shipping the `ntp` package. Do not implement the proposal.

### Container limits

- The remaining roles (`selinux`, `auditd`, `sysctl`, `hostname`, `rsyslog`) may fail inside containers. Gate a role on virtualization type in the play, following the existing `ntp` precedent in `10_onboard.yml`. Do not edit the vendored roles.
- If gating would leave the stage mostly untested, stop and propose adding one VM test node, named according to the naming document.

### Verify

- `20_normalize.yml` runs with `failed=0` on `deb13` and `ubu2404` from `10-onboarded`.
- The monitoring rule from `firewall_rules_normalize` is present on the node with its `10.0.0.0/24` source restriction.
- `--syntax-check` passes for every playbook, including `site.yml`. If `30_specialize.yml` cannot run because no `specialize_role` exists yet, say so and leave it.
- Take `20-normalized` snapshots.
- Restore one node from `20-normalized` to `10-onboarded`, demote its inventory entry from normalized to onboard, and confirm `20_normalize.yml` runs on it again. This exercises the one demotion path that moves an entry.

### Checkpoint

Summarise the demotion change, the guard, the firewall role and the normalize stage, list every role you removed or gated, and wait for my go-ahead before the speed work.

## Speed settings

Branch: `perf/ansible-cfg`.

### Baseline

- Enable `callbacks_enabled = ansible.posix.profile_tasks` and leave it on.
- Record three timings: `10_onboard.yml` from `raw`, `20_normalize.yml` from `10-onboarded`, and a throwaway play of about 30 trivial tasks over SSH as `initial`. Do not commit the throwaway play.

### Changes

One per commit, in this order. After each change, re-time only the throwaway play. Repeat the full onboard and normalize timings once at the end with everything applied.

- Pipelining. Confirm it is active with `ansible-config dump --only-changed`, since the valid config section depends on the Ansible version. Add `Defaults:initial !requiretty` only if a target fails without it, as its own file in `/etc/sudoers.d/` validated with `visudo -cf %s`.
- Fact cache location: a per-user directory such as `~/.ansible/fact_cache/uc-controller`.
- Fresh facts during onboarding: the onboard converge play gathers facts with an explicit `setup` task, so a rebuilt instance with a reused name never gets a cached address.
- `forks = 20`.
- `strategy: free` on the converge plays in `20_normalize.yml` and `30_specialize.yml` only. The config default stays `linear`.
- Confirm `roles_path` matches the Option A layout and includes the new firewall role's location.
- Leave `host_key_checking = False`, with a comment that it must be revisited before any non-test node is managed.

### Verify

Report a table of before and after timings. If a change shows no measurable gain on two nodes, keep it only if it is harmless and say so plainly.

## Documentation

On the branch each item belongs to:

- Design document v0.1.4: the rule that scripts never add hosts to raw and what demotion is for, the re-onboarding guard, the firewall role with its schema and known limitation, the normalize role list as it now stands, the time sync proposal, and the deferred secrets note. Remove the firewall mismatch section once the role replaces it, keeping one line of history in the changelog.
- Speed overview: the next version of the speed document, with the corrections from the original kickoff applied and measured timings replacing the generic estimates.
- Session record under `en/docs/`, following the existing pattern.

## Final report

- All branches in merge order, with commit counts.
- Each item in the summary table of the inventory notes, with its status.
- The pre-freeze list, each with its status: normalize runs end to end, firewall contract implemented, persistence documented and re-onboarding guarded, discovery writes only its own file, snapshot alignment and the raw environment rationale documented.
- The timing table.
- Open questions, and anything you chose not to do, with the reason.

## Prompt

Paste this into the running session. Adjust the path if the file is saved under another name.

```text
My answers to the review checkpoint, and the plan for the rest of the run, are in en/docs/dev/kickoff-remaining-phases-guard-firewall-normalize-and-speed.md. Read it in full and follow it. It replaces the "Speed settings", "Documentation" and "Final report" sections of the original kickoff, and everything else in the original still applies.

Summary of what it decides:
- Firewall: Option 2, a project role, built before the speed work.
- Demotion to raw removes the onboard entry and writes nothing to raw. Undo the write to raw/discovered.yml.
- Ignore the generated raw files in git, resolve promote_node.py from the repository root, and keep live host entries uncommitted.
- Add the re-onboarding guard and delete vaults/.
- Make 20_normalize.yml runnable, then stop at the checkpoint before the speed phase.

Order of work: review additions on fix/option-a-review, then feat/firewall-rules, then fix/normalize-runnable, then the checkpoint, then perf/ansible-cfg.

Before changing anything, tell me in a few lines whether anything in the repository contradicts the update. If nothing does, proceed without waiting.
```
