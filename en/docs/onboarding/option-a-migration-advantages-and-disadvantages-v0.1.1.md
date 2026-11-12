# Migrating uc-controller to Option A: Advantages and Disadvantages

This document weighs the case for moving the uc-controller repository to the Option A design, a single repository with separate `ingress/` and `converge/` directories. It is based on three things: the Option A proposal, the bounded complexity note with its source taxonomy, and the repository as it stands on `main` at commit `6fd50af`. Where a claim could be tested, it was tested with ansible-core 2.22.0 against a scratch copy of the Option A layout, and the results are listed under Test Results.

## Changelog

### v0.1.0 → v0.1.1

| Change | Description |
|--------|-------------|
| Two gaps named | The connection contract and persisted promotion are now called out as Gap 1 and Gap 2, in the Summary and in their own section |
| Fixes described | Each gap has a problem statement, a fix, and implementation notes |
| Order of work | Conditions for Migrating is replaced by Order of Work, with the gap fixes placed ahead of the layout change |
| Cross references | The two matching entries under Disadvantages and Risks now hold the evidence only and point to the gap section for the fix |

## Summary

The layout change is cheap, reversible, and a good fit for where the controller is heading. It is worth doing, but not first.

Two gaps in the current repository have to be closed before the converge stage can run on its own. Both exist today, whether or not Option A is adopted, and both are prerequisites for the migration rather than consequences of it.

- Gap 1, the connection contract. Nothing in the onboard inventory says that an onboarded node is reached over SSH as `initial`. A converge run that loads the raw inventory still reaches an Incus node as root over `incus exec`.
- Gap 2, persisted promotion. Promotion happens in memory only. Run as two separate commands, converge does not see the nodes ingress just promoted, and `promote_node.py` cannot promote a plugin-discovered host.

Two further points qualify the proposal itself.

- The directories do not enforce the boundary. A converge playbook can use an ingress role, or condition on `ansible_connection`, without any path crossing a directory.
- The playbooks printed in the proposal are older than the ones in the repository. Migrate the layout, keep the repository's playbook bodies.

The recommendation is to close the two gaps, then migrate, in the sequence given under Order of Work.

## Two Gaps to Close First

Option A's central claim is that converge does not care where a node came from. Directories cannot make that true. The inventory has to carry the handoff, and at present it does not.

### Gap 1: The Onboard Inventory Does Not State the Connection Contract

#### The Problem

An onboarded node is reachable over SSH as `initial` with passwordless sudo, but nothing under `inventories/onboard/<env>/` says so. The raw inventory's Incus group variables (`ansible_connection: community.general.incus`, `ansible_user: root`) follow the host through every later inventory source that does not override them. A converge run that loads the raw inventory resolves the node to `incus exec` as root, not SSH as `initial`. The evidence is under Source-Agnostic Converge Depends on Inventory Data.

#### The Fix

The connection contract belongs at host level in the onboard inventory. In the tests, host-level variables were the only placement that won against the raw group variables in either `-i` order. Promotion, whether `add_host` in a chained run or `promote_node.py` for a persisted one, writes four variables onto each host entry:

```yaml
# inventories/onboard/dev/hosts.yml (after promotion)
onboarded:
  hosts:
    ex2-test.default.local:
      ansible_host: 10.119.134.42
      ansible_connection: ssh
      ansible_user: initial
      ansible_ssh_private_key_file: ~/.ssh/gradus-raw-initial-id_ed25519
```

This is the handoff contract. Ingress writes it, converge reads it. Neither side needs to know the other's code, and the ordering of raw and onboard on the command line stops mattering.

#### Implementation Notes

- The re-targeting `add_host` task in the repository's `10_onboard.yml` already sets `ansible_connection: ssh`, `ansible_user: initial`, and `ansible_host` from gathered facts. Only `ansible_ssh_private_key_file` is missing from the in-memory promotion, so this step is one added line.
- The key path is a controller-side path. Written into a tracked inventory file, it has to be valid on every machine that runs converge. Because the raw inventory does not set a key file, this one variable could instead live in the onboard inventory's group variables, or be left to the SSH agent, without weakening the contract. The other three must stay at host level.

#### A Consequence to Plan For

Plugin-discovered Incus instances stay in the `raw` group for as long as they are running. Once such a host also has a host-level SSH contract in the onboard inventory, the contract wins whenever both inventories are loaded, and the proposal's ingress commands load both. Running `10_onboard.yml` again on that host would then connect over SSH as `initial` instead of over `incus exec` as root. After a snapshot reset to the raw state, where sshd and the `initial` user no longer exist, that connection fails.

The rule that follows is that a node must be demoted before it is onboarded again. `demote_node.py` should remove the onboard entry and with it the contract, and the reset procedure in the onboarding guide should include the demotion.

### Gap 2: Promotion Is Not Persisted for Plugin-Discovered Hosts

#### The Problem

`add_host` changes the in-memory inventory for the current run only. Plugin-discovered hosts (Incus, LXD, Docker, cloud) never appear in `raw/hosts.yml`, because the plugin generates them at runtime. `promote_node.py` reads `raw/hosts.yml` and stops with "host not found" for any plugin-discovered node. The SSH address gathered during onboarding exists only in memory and is lost when the ingress run ends. The evidence is under The Handoff Between Ingress and Converge Is Not Persisted.

#### The Fix

There are two parts.

First, `10_onboard.yml` gains a final play that writes each promoted host, with its connection contract, to `inventories/onboard/<env>/hosts.yml` on the controller. The address comes from the facts gathered during the baseline play. This makes the promotion durable without a separate manual step.

Second, `promote_node.py` gains a path for hosts that are not in a static file. For generated hosts (nmap, manual) it reads `raw/hosts.yml` as it does now. For plugin-discovered hosts it accepts the address as an argument, for example `--address 10.119.134.42`, or a `--source` flag that tells it to query the plugin's inventory for the current address. Either way it writes the entry into the onboard inventory with the contract from Gap 1.

#### Implementation Notes

- One writer is safer than two. If the final play calls `promote_node.py --address ...` on the controller, the script remains the only code that knows the layout of `hosts.yml`, and the play and the manual path cannot drift apart. Appending YAML with `lineinfile` is fragile by comparison.
- The write must be serialized. Several hosts finishing at once would otherwise race on one file. A single `run_once` task that loops over `ansible_play_hosts`, delegated to the controller, avoids that.
- The delegated task needs `become: no`. `ansible.cfg` turns privilege escalation on globally, and the write is to the operator's own working tree.
- The target path should come from a variable naming the onboard inventory for the environment, not from `playbook_dir`, so it survives the move to `ingress/playbooks/`.
- The write should be idempotent, replacing an existing entry for the same host rather than adding a second one.

### What the Gaps Mean for Option A

The two fixes are needed whether the layout stays as it is or moves to Option A. Once every host in the onboard inventory carries the connection contract, converge does not depend on the node's origin, because the contract overrides whatever the raw inventory says. The directory boundary and the data boundary then support each other: the directories keep source handling out of the converge code, and the persisted contract keeps it out of the converge inventory.

## What Changes

| Item | Today | Option A |
|------|-------|----------|
| Discover and onboard playbooks | `playbooks/lifecycle/00_discover.yml`, `10_onboard.yml` | `ingress/playbooks/` |
| Normalize and specialize playbooks | `playbooks/lifecycle/20_normalize.yml`, `30_specialize.yml` | `converge/playbooks/` |
| Roles | 17 Galaxy roles vendored in `./roles` | `ingress/roles` and `converge/roles`, both empty at first |
| `roles_path` | `./roles:~/.ansible/roles:/usr/share/ansible/roles` | `./ingress/roles:./converge/roles:~/.ansible/roles:/usr/share/ansible/roles` |
| `site.yml` | `playbooks/site.yml` | repository root, or dropped |
| Inventories, scripts, vaults | unchanged | unchanged |
| `scaffold.yml` | `playbooks/lifecycle/scaffold.yml` | not placed by the proposal |

## Advantages

### The Layout Matches the Bounded Complexity Insight

The background note's central claim is that source diversity ends at the raw to onboard transition. Option A gives that claim a place in the tree. Someone opening the repository sees two concerns before reading a line of YAML, and the question "does this change care where the node came from?" has a default answer based on which directory the file is in.

### Ingress Is Where the Growth Will Land

The source taxonomy lists 18 sources in six families: container, hypervisor, cloud, network, bare metal, and external. The connection matrix shows that four of its ten rows (Incus, LXD, Docker, libvirt) need a connection transition, and that discovery, bootstrap needs, and host naming differ across nearly all of them. Only Incus and the nmap scan exist in the repository so far. Every source added later brings plugin configuration, reachability checks, and naming rules, and all of it belongs to ingress. Separating now means converge stays the same size while ingress grows.

### Changes to Ingress Are Visibly Contained

With the split, a commit that only touches `ingress/` cannot have changed how compliant nodes are normalized or specialized. That makes review faster and makes it safer to experiment with a new source. It also gives a natural unit for testing: ingress can be exercised against throwaway Incus instances without running the converge roles at all.

### The Migration Is Small

The move is four `git mv` operations, one edited line in `ansible.cfg`, and path fixes in two playbooks. The inventories, the vaults, and the scripts do not move. `promote_node.py` and `demote_node.py` locate stages by looking for `inventories/` in the path, so they are unaffected by the layout change.

### It Is Reversible and It Is a Step Toward a Split

If the layout does not earn its keep, moving the playbooks back is the same four operations. If ingress later grows enough to deserve its own repository, the directory is already the unit that would be extracted. Neither Option B nor Option C offers that kind of low-commitment trial.

### Shared Inventory Keeps the Firewall Layering Simple

The stage-namespaced variables (`firewall_rules_onboard` and the rest) stay in one inventory tree that both concerns read. No variable has to cross a repository boundary, and the `-i` ordering rules documented in v0.1.3 carry over unchanged.

## Disadvantages and Risks

### The Directories Do Not Enforce the Boundary

The proposal says a converge playbook that needs something from ingress "has to reach across the directory divide". In practice it does not. Ansible resolves a role name by searching a `roles/` directory beside the playbook, then every directory on the configured `roles_path` <a id="cite-ansible-roles"></a>([Ansible project contributors, n.d.-d](#ref-ansible-roles)). Option A puts both `ingress/roles` and `converge/roles` on that one path, so a converge playbook can name an ingress role with no path in sight. In the test, a playbook in `converge/playbooks/` ran a role stored in `ingress/roles/` by its bare name.

The leak the proposal worries about most, a `when: ansible_connection == ...` added to `20_normalize.yml`, needs no cross-directory reference at all. It is one line inside a converge file.

The boundary is therefore a convention that is easy to see in a diff, not a wall. It becomes a wall only with a check, for example a pre-commit or CI step that fails when anything under `converge/` mentions `ansible_connection`, the `raw` module, or a connection plugin name.

### Source-Agnostic Converge Depends on Inventory Data

This is the evidence for Gap 1. Three facts about the current repository work against the assumption that converge reaches nodes over SSH as `initial`:

- The Incus plugin configuration puts every running instance in the `raw` group, and it keeps doing so after the instance is onboarded.
- `inventories/raw/group_vars/incus.yml` sets `ansible_connection: community.general.incus` and `ansible_user: root`.
- `inventories/onboard/dev` sets neither `ansible_connection` nor `ansible_user`.

The proposal's converge commands pass `-i inventories/raw` first. Ansible flattens group variables onto the host, with child groups overriding the `all` group, and when several inventory sources are passed the later source wins a conflict <a id="cite-ansible-inventory"></a>([Ansible project contributors, n.d.-c](#ref-ansible-inventory)). Tested with a host in both `raw` and `onboarded`:

- Connection settings placed in the onboard inventory's `group_vars/all.yml` lost to the raw group's settings. The node resolved to the Incus connection as root.
- The same settings placed in `group_vars/onboarded.yml` won, but only while the onboard inventory was passed after the raw one. Reversing the `-i` order handed the node back to the Incus connection.
- Settings placed on the host itself in the onboard `hosts.yml` won in either order.

The third result is why the fix for Gap 1 puts the contract at host level.

### The Handoff Between Ingress and Converge Is Not Persisted

This is the evidence for Gap 2. `10_onboard.yml` promotes nodes with `add_host`, which changes only the in-memory inventory of the current run <a id="cite-ansible-add-host"></a>([Ansible project contributors, n.d.-a](#ref-ansible-add-host)). The proposal's preferred usage is no `site.yml`, with ingress and converge run as separate commands. Tested that way, a node promoted by the ingress run was not in `onboarded` when the converge run started. Chained through a root `site.yml`, it was.

`promote_node.py`, run against an Incus instance name, stopped with "host not found", because plugin-discovered hosts are never written to `inventories/raw/hosts.yml`.

Option A describes the handoff as "data, not code". For Incus nodes that data does not exist until Gap 2 is closed.

### The Proposal's Playbooks Are Behind the Repository

The playbook bodies in the proposal predate the working onboard flow committed on `main`. Copying them in would undo fixes that were made while testing on Incus:

| Area | Proposal | Repository today |
|------|----------|------------------|
| Reachability | `wait_for` port 22, or `incus exec`, chosen by `when` on the connection type | one `raw: 'true'` probe that works over any connection |
| Python bootstrap | `raw: apt-get install python3` for non-SSH sources | `robertdebock.bootstrap` over the source connection |
| umask | absent | `steelcj.umask` runs before users are created |
| Time sync | `robertdebock.ntp` always | skipped on containers |
| Switch to SSH | `set_fact` and `meta: reset_connection` | `add_host` re-targeting with the gathered address |
| Output callback | `stdout_callback = yaml` | `default` with `callback_result_format = yaml` |
| Normalize roles | includes `pam`, `limits`, `timezone`, `motd`, `chrony` | `requirements.yml` notes these roles do not exist |
| Firewall input | `firewall_rules` | the role reads `firewall_services` |

One consequence is worth noting on the advantages side as well. The repository's `10_onboard.yml` contains no conditions on connection type. Source differences already live in inventory variables, so the amount of source-specific code that Option A would wall off is, for now, close to zero. The benefit is anticipatory.

### Shared Roles Lose Their Path

The proposal's `roles_path` drops `./roles`, which is where all 17 installed roles are vendored and tracked in git. In the test, a role left in `./roles` was reported as not found. `./roles` has to stay on the path, or the roles have to be reinstalled elsewhere.

There is also a modelling gap. Every role in use is a shared Galaxy role, and `robertdebock.firewall` is used by both concerns. The two-directory scheme has no home for shared roles, and `ingress/roles` and `converge/roles` would both start empty. A third location, `./roles` as it is now, is the honest answer, which makes the layout three role directories rather than two.

### Relative Paths Need Correcting

`00_discover.yml` writes to `{{ playbook_dir }}/../inventories/raw/hosts.yml`. From `ingress/playbooks/` that resolves to `ingress/inventories/raw/hosts.yml`, which does not exist. The test confirmed the resolution from the sibling `converge/playbooks/` directory. The correct form after the move is `../../inventories`. The same expression in today's layout resolves to `playbooks/inventories`, so the path is already wrong and the migration is a chance to fix it. `scaffold.yml` uses the same pattern for both `roles` and `inventories`.

### The Layout Is Unconventional and Tied to the Repository Root

Ansible's sample layouts keep one `roles/` directory and note that moving playbooks into a subdirectory requires setting `roles_path` <a id="cite-ansible-sample-setup"></a>([Ansible project contributors, n.d.-e](#ref-ansible-sample-setup)). Two `playbooks/` and two `roles/` directories will surprise anyone who knows the usual shape, and tools that assume it, such as editor integrations and linters, may need configuration.

The layout also works only from the repository root. Ansible picks up `ansible.cfg` from the current directory and resolves relative settings such as `roles_path` against that file <a id="cite-ansible-config"></a>([Ansible project contributors, n.d.-b](#ref-ansible-config)). Run from inside `converge/playbooks/`, the test found no `ansible.cfg`, fell back to the default search path, and could not find the roles. This is true of the current layout too, but deeper nesting makes it easier to trip over.

### Loose Ends the Proposal Does Not Place

- `scaffold.yml` serves neither concern. It needs a home, perhaps a top-level `tools/` or `playbooks/` directory.
- A stray copy of `10_onboard.yml` sits at the repository root and differs from the one under `playbooks/lifecycle/`.
- `playbooks/lifecycle/artifacts/` holds earlier onboard versions.
- The guides under `en/docs` quote `playbooks/lifecycle/` paths in their commands and will need updating, as will the v0.1.4 controller document.

## Test Results

All tests used ansible-core 2.22.0 in a scratch directory laid out as Option A, with the proposal's `ansible.cfg`.

| Question | Result |
|----------|--------|
| Can a converge playbook use an ingress role by bare name? | Yes. No path crosses the directory boundary. |
| Is a role left in `./roles` still found? | No. Reported as not found; `./roles` is not on the proposed path. |
| Where does `{{ playbook_dir }}/../inventories` point from `converge/playbooks/`? | `converge/inventories`, which does not exist. |
| Raw and onboard loaded, connection set in onboard `group_vars/all.yml`? | Raw group settings win. Node reached over Incus as root. |
| Same, set in onboard `group_vars/onboarded.yml`? | Onboard wins only when passed after raw. |
| Same, set on the host in onboard `hosts.yml`? | Onboard wins in either order. |
| Does a root `site.yml` importing from both directories work? | Yes. Converge saw the node ingress promoted. |
| Does converge, run separately, see a node promoted by an earlier ingress run? | No. Promotion is in memory only. |
| Does a playbook run from inside its own directory find its roles? | No. `ansible.cfg` is not picked up. |
| Can `promote_node.py` promote an Incus plugin host? | No. The host is not in `raw/hosts.yml`. |

The Incus plugin itself was not run in the test environment. The statement that onboarded instances remain in `raw` follows from the plugin configuration in the repository (`groups: raw: true`, filtered on running status) and should be confirmed with `ansible-inventory --graph` on the workstation. The fixes described under Two Gaps to Close First have not been implemented or tested; the host-level placement they rely on was.

## Order of Work

### Close the Gaps

1. Add `ansible_ssh_private_key_file` to the re-targeting `add_host` task in `10_onboard.yml`, so the in-memory promotion carries the full contract for chained runs. The other three variables are already set there.
2. Add a final play to `10_onboard.yml` that writes promoted hosts, with the contract, to `inventories/onboard/<env>/hosts.yml` on the controller.
3. Update `promote_node.py` to accept `--address` for plugin-discovered hosts and to write the contract. Update `demote_node.py` to remove it.
4. Verify that the contract is at host level and that it survives the raw inventory being loaded:

```sh
ansible-inventory -i inventories/onboard/dev --graph --vars
ansible-inventory -i inventories/raw -i inventories/onboard/dev --host ex2-test.default.local
ansible-inventory -i inventories/onboard/dev -i inventories/raw --host ex2-test.default.local
```

All three should show `ansible_connection: ssh` and `ansible_user: initial` for the promoted host. Plain `--graph` lists hosts and groups without variables, so `--vars` or `--host` is needed. Then run `20_normalize.yml` as a separate command, without `site.yml`, and confirm it reaches the node.

### Then Migrate the Layout

5. Move the repository's current playbooks, not the proposal's versions, into `ingress/playbooks/` and `converge/playbooks/`.
6. Keep `./roles` on `roles_path`, ahead of or alongside the two new directories.
7. Correct the `playbook_dir` paths in `00_discover.yml` and `scaffold.yml`, and decide where `scaffold.yml` lives.
8. Add a check that fails when files under `converge/` reference connection types, the `raw` module, or connection plugins.
9. Remove the stray root `10_onboard.yml`, update the `en/docs` guides, and add the demotion step to the snapshot reset procedure.

Steps 1 through 4 close both gaps and stand on their own. Step 5 onward is the layout change, which is safe once the data handoff exists.

## References

<a id="ref-ansible-add-host"></a>
[Return to citation](#cite-ansible-add-host)
Ansible project contributors. (n.d.-a). *ansible.builtin.add_host module: Add a host (and alternatively a group) to the ansible-playbook in-memory inventory*. Ansible Community Documentation. Retrieved November 12, 2026, from https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/add_host_module.html

<a id="ref-ansible-config"></a>
[Return to citation](#cite-ansible-config)
Ansible project contributors. (n.d.-b). *Ansible configuration settings*. Ansible Community Documentation. Retrieved November 12, 2026, from https://docs.ansible.com/projects/ansible/latest/reference_appendices/config.html

<a id="ref-ansible-inventory"></a>
[Return to citation](#cite-ansible-inventory)
Ansible project contributors. (n.d.-c). *How to build your inventory*. Ansible Community Documentation. Retrieved November 12, 2026, from https://docs.ansible.com/projects/ansible/latest/inventory_guide/intro_inventory.html

<a id="ref-ansible-roles"></a>
[Return to citation](#cite-ansible-roles)
Ansible project contributors. (n.d.-d). *Roles*. Ansible Community Documentation. Retrieved November 12, 2026, from https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_reuse_roles.html

<a id="ref-ansible-sample-setup"></a>
[Return to citation](#cite-ansible-sample-setup)
Ansible project contributors. (n.d.-e). *Sample Ansible setup*. Ansible Community Documentation. Retrieved November 12, 2026, from https://docs.ansible.com/projects/ansible/latest/tips_tricks/sample_setup.html
