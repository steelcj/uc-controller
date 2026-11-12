# Migrating uc-controller to Option A: Advantages and Disadvantages

This document weighs the case for moving the uc-controller repository to the Option A design, a single repository with separate `ingress/` and `converge/` directories. It is based on three things: the Option A proposal, the bounded complexity note with its source taxonomy, and the repository as it stands on `main` at commit `6fd50af`. Where a claim could be tested, it was tested with ansible-core 2.22.0 against a scratch copy of the Option A layout, and the results are listed under Test Results.

## Summary

The layout change is cheap, reversible, and a good fit for where the controller is heading. It is worth doing. The proposal overstates one thing and leaves three things out, and those matter more than the directory move itself.

- The directories do not enforce the boundary. A converge playbook can use an ingress role, or condition on `ansible_connection`, without any path crossing a directory.
- Whether converge is source-agnostic is decided by inventory data, not by where the playbooks live. Today the onboard inventory does not declare how to reach an onboarded node, so a converge run that loads the raw inventory would still reach an Incus node as root over `incus exec`.
- The handoff from ingress to converge is in memory only. Run as two separate commands, converge does not see the nodes ingress just promoted.
- The playbooks printed in the proposal are older than the ones in the repository. Migrate the layout, keep the repository's playbook bodies.

The recommendation is to migrate, with the conditions listed under Conditions for Migrating.

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

### The layout matches the bounded complexity insight

The background note's central claim is that source diversity ends at the raw to onboard transition. Option A gives that claim a place in the tree. Someone opening the repository sees two concerns before reading a line of YAML, and the question "does this change care where the node came from?" has a default answer based on which directory the file is in.

### Ingress is where the growth will land

The source taxonomy lists 18 sources in six families: container, hypervisor, cloud, network, bare metal, and external. The connection matrix shows that four of its ten rows (Incus, LXD, Docker, libvirt) need a connection transition, and that discovery, bootstrap needs, and host naming differ across nearly all of them. Only Incus and the nmap scan exist in the repository so far. Every source added later brings plugin configuration, reachability checks, and naming rules, and all of it belongs to ingress. Separating now means converge stays the same size while ingress grows.

### Changes to ingress are visibly contained

With the split, a commit that only touches `ingress/` cannot have changed how compliant nodes are normalized or specialized. That makes review faster and makes it safer to experiment with a new source. It also gives a natural unit for testing: ingress can be exercised against throwaway Incus instances without running the converge roles at all.

### The migration is small

The move is four `git mv` operations, one edited line in `ansible.cfg`, and path fixes in two playbooks. The inventories, the vaults, and the scripts do not move. `promote_node.py` and `demote_node.py` locate stages by looking for `inventories/` in the path, so they are unaffected.

### It is reversible and it is a step toward a split

If the layout does not earn its keep, moving the playbooks back is the same four operations. If ingress later grows enough to deserve its own repository, the directory is already the unit that would be extracted. Neither Option B nor Option C offers that kind of low-commitment trial.

### Shared inventory keeps the firewall layering simple

The stage-namespaced variables (`firewall_rules_onboard` and the rest) stay in one inventory tree that both concerns read. No variable has to cross a repository boundary, and the `-i` ordering rules documented in v0.1.3 carry over unchanged.

## Disadvantages and Risks

### The directories do not enforce the boundary

The proposal says a converge playbook that needs something from ingress "has to reach across the directory divide". In practice it does not. Ansible resolves a role name by searching a `roles/` directory beside the playbook, then every directory on the configured `roles_path` <a id="cite-ansible-roles"></a>([Ansible project contributors, n.d.-d](#ref-ansible-roles)). Option A puts both `ingress/roles` and `converge/roles` on that one path, so a converge playbook can name an ingress role with no path in sight. In the test, a playbook in `converge/playbooks/` ran a role stored in `ingress/roles/` by its bare name.

The leak the proposal worries about most, a `when: ansible_connection == ...` added to `20_normalize.yml`, needs no cross-directory reference at all. It is one line inside a converge file.

The boundary is therefore a convention that is easy to see in a diff, not a wall. It becomes a wall only with a check, for example a pre-commit or CI step that fails when anything under `converge/` mentions `ansible_connection`, the `raw` module, or a connection plugin name.

### Source-agnostic converge depends on inventory data

Converge is meant to assume SSH as `initial` with passwordless sudo. Directories cannot make that true. Three facts about the current repository work against it:

- The Incus plugin configuration puts every running instance in the `raw` group, and it keeps doing so after the instance is onboarded.
- `inventories/raw/group_vars/incus.yml` sets `ansible_connection: community.general.incus` and `ansible_user: root`.
- `inventories/onboard/dev` sets neither `ansible_connection` nor `ansible_user`.

The proposal's converge commands pass `-i inventories/raw` first. Ansible flattens group variables onto the host, with child groups overriding the `all` group, and when several inventory sources are passed the later source wins a conflict <a id="cite-ansible-inventory"></a>([Ansible project contributors, n.d.-c](#ref-ansible-inventory)). Tested with a host in both `raw` and `onboarded`:

- Connection settings placed in the onboard inventory's `group_vars/all.yml` lost to the raw group's settings. The node resolved to the Incus connection as root.
- The same settings placed in `group_vars/onboarded.yml` won, but only while the onboard inventory was passed after the raw one. Reversing the `-i` order handed the node back to the Incus connection.
- Settings placed on the host itself in the onboard `hosts.yml` won in either order.

This weakness exists today and is not caused by Option A. It matters here because Option A's main promise rests on it. The onboard inventory has to state the connection contract explicitly, or converge runs have to stop loading the raw inventory.

### The handoff between ingress and converge is not persisted

`10_onboard.yml` promotes nodes with `add_host`, which changes only the in-memory inventory of the current run <a id="cite-ansible-add-host"></a>([Ansible project contributors, n.d.-a](#ref-ansible-add-host)). The proposal's preferred usage is no `site.yml`, with ingress and converge run as separate commands. Tested that way, a node promoted by the ingress run was not in `onboarded` when the converge run started. Chained through a root `site.yml`, it was.

The intended bridge is `promote_node.py`, but it reads `inventories/raw/hosts.yml`, and plugin-discovered hosts are never written there. Run against an Incus instance name it stops with "host not found". The SSH address chosen during onboarding is also derived from gathered facts and held only in memory, so nothing records where converge should connect.

Option A describes the handoff as "data, not code". For Incus nodes that data does not exist yet.

### The proposal's playbooks are behind the repository

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

### Shared roles lose their path

The proposal's `roles_path` drops `./roles`, which is where all 17 installed roles are vendored and tracked in git. In the test, a role left in `./roles` was reported as not found. `./roles` has to stay on the path, or the roles have to be reinstalled elsewhere.

There is also a modelling gap. Every role in use is a shared Galaxy role, and `robertdebock.firewall` is used by both concerns. The two-directory scheme has no home for shared roles, and `ingress/roles` and `converge/roles` would both start empty. A third location, `./roles` as it is now, is the honest answer, which makes the layout three role directories rather than two.

### Relative paths need correcting

`00_discover.yml` writes to `{{ playbook_dir }}/../inventories/raw/hosts.yml`. From `ingress/playbooks/` that resolves to `ingress/inventories/raw/hosts.yml`, which does not exist. The test confirmed the resolution from the sibling `converge/playbooks/` directory. The correct form after the move is `../../inventories`. The same expression in today's layout resolves to `playbooks/inventories`, so the path is already wrong and the migration is a chance to fix it. `scaffold.yml` uses the same pattern for both `roles` and `inventories`.

### The layout is unconventional and tied to the repository root

Ansible's sample layouts keep one `roles/` directory and note that moving playbooks into a subdirectory requires setting `roles_path` <a id="cite-ansible-sample-setup"></a>([Ansible project contributors, n.d.-e](#ref-ansible-sample-setup)). Two `playbooks/` and two `roles/` directories will surprise anyone who knows the usual shape, and tools that assume it, such as editor integrations and linters, may need configuration.

The layout also works only from the repository root. Ansible picks up `ansible.cfg` from the current directory and resolves relative settings such as `roles_path` against that file <a id="cite-ansible-config"></a>([Ansible project contributors, n.d.-b](#ref-ansible-config)). Run from inside `converge/playbooks/`, the test found no `ansible.cfg`, fell back to the default search path, and could not find the roles. This is true of the current layout too, but deeper nesting makes it easier to trip over.

### Loose ends the proposal does not place

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

The Incus plugin itself was not run in the test environment. The statement that onboarded instances remain in `raw` follows from the plugin configuration in the repository (`groups: raw: true`, filtered on running status) and should be confirmed with `ansible-inventory --graph` on the workstation.

## Conditions for Migrating

Migrating is recommended if these are done as part of it, or directly after.

- Move the repository's current playbooks, not the proposal's versions.
- Keep `./roles` on `roles_path`, ahead of or alongside the two new directories.
- Correct the `playbook_dir` paths in `00_discover.yml` and `scaffold.yml`, and decide where `scaffold.yml` lives.
- State the connection contract in the onboard inventory, at host level or in `group_vars/onboarded.yml`, so converge reaches nodes over SSH as `initial` regardless of what the raw inventory says.
- Persist promotion for plugin-discovered nodes, including the SSH address, so a separate converge run can find them.
- Add a check that fails when files under `converge/` reference connection types, the `raw` module, or connection plugins.
- Remove the stray root `10_onboard.yml` and update the `en/docs` guides.

The fourth and fifth items are needed whether or not the layout changes. They are listed here because Option A's claims about converge are only true once they are in place.

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
