---
name: robertdebock-ansible-roles-cfap
org: universal-cake
lang: en
type: reference
version: 0.1.1
date: 2026-11-12
---

# Robert de Bock Ansible Roles: Concepts, Facts and Procedures (CFAP)

Version: 0.1.1

Status: Draft

A reference for understanding, consulting and maintaining Robert de Bock's Ansible roles within uc-gradus. It documents what needs to be understood, what needs to be memorized, and what needs to be done, so that the "consult before you create" principle in the uc-gradus CFAP can be followed reliably by a person or an ai-assistant.

The local cache file (`robertdebock-ansible-roles-cache`) is the lookup table. This document is the training material that explains when and how to use it, what its limits are, and what to do when it does not answer the question.

## Where the content comes from

| Label | Source | How far to trust it |
|---|---|---|
| Cache | `robertdebock-ansible-roles-cache-v0.1.0.md`, dated 2026-11-10 | The list of 175 roles, their descriptions and platform support. Built from the roles collection at version 1.8.3 (last commit 2025-08-29). A role's own repository may be newer. |
| Collection | `github.com/robertdebock/ansible-collection-roles`, version 1.8.3 | The packaged snapshot the cache was built from. |
| Repositories | Individual `github.com/robertdebock/ansible-role-<name>` repositories | Authoritative for current behaviour, parameters and platform support of a specific role. |
| Owner | Decisions the owner made about how these roles fit uc-gradus | Target: intent, it carries authority. |

## Concepts

What needs to be understood.

### Why these roles

Robert de Bock develops Ansible roles that are Linux-release agnostic, carefully crafted and tested. His roles handle the differences between distributions (Debian, Fedora, Arch, Alpine and others) behind a single set of variables, so a playbook written once works across families. For uc-gradus, which targets Debian 13 today but is described as OS agnostic, this means a role chosen here is less likely to need rewriting when a second distribution enters the picture.

### Consult before you create

The uc-gradus CFAP states: "Before creating a new Ansible role, playbook or task in order to serve a particular need, you should consult his work." The procedure is:

1. Identify the need in plain terms (for example, "manage firewall ports").
2. Look up the need in the cache's "Roles by need" table.
3. Open the candidate role's repository and read its `defaults/main.yml` and `README.md` to see whether the variables express what you need.
4. Report the finding either way: "this role can do it, here is how" or "this role cannot do it, here is why."

Step 4 is not optional. A negative finding is as valuable as a positive one because it records that the consultation happened, and it prevents a future person from repeating the same search.

### The cache is a starting point, not a decision

The cache lists 175 roles with one-line descriptions and a Debian-support flag. It does not show the variables a role accepts, the tasks it runs, or the conditions under which it fails. Those are in the role's own repository. Always open the repository before deciding.

### Three naming forms

The same role has three names depending on context:

| Context | Form | Example |
|---|---|---|
| GitHub repository | `github.com/robertdebock/ansible-role-<name>` | `github.com/robertdebock/ansible-role-firewall` |
| Ansible Galaxy (standalone install) | `robertdebock.<name>` | `robertdebock.firewall` |
| Inside the collection (imported) | `robertdebock.roles.<name>` | `robertdebock.roles.firewall` |

uc-gradus pins roles in `requirements.yml` using the Galaxy form (`robertdebock.<name>`), and installs them into `~/.ansible/roles/`. Roles are never copied into the repository.

### Platform support is a flag, not a guarantee

The cache marks each role "Yes" or "No" for Debian. This comes from `meta/main.yml` and reflects what Robert tested at the time of the collection's last commit. A "Yes" does not mean the role is bug-free on Debian 13 specifically; it means Debian appeared in his test matrix. A "No" does not mean the role cannot work on Debian; it means he did not test it there.

For Debian 13 (trixie), check the role's own repository for recent commits or issues that mention trixie or bookworm.

### Roles that do not exist

The cache records a list of needs with no matching role (as of 2026-11-10): `caddy`, `incus`, `nftables`, `sshguard`, `cinnamon`, `apparmor`, `sudo`, `timezone`, `unattended_upgrades`. A need in this list may still be met by a role with a different name (for example, automatic updates by `auto_update`, or timezone by `ntp`). If no role exists, uc-gradus writes its own, placed in `roles/` until it is tested, vetted and published.

### The roles are pinned, not floating

`requirements.yml` pins a specific version of each role. This is deliberate: a role update can change default behaviour, and a pinned version guarantees that what worked yesterday works today. Updating a pin is a deliberate act, tested in dev before promotion.

### The collection versus individual roles

The collection (`ansible-collection-roles`) bundles all roles into one installable unit. uc-gradus does not install the collection. It installs individual roles by name, pinned to specific versions, so that updating one role does not drag along changes to unrelated roles.

## Principles

Guidelines that need judgement.

| Principle | Stated in |
|---|---|
| Before writing a new role, playbook or task, consult the cache and the candidate's repository, and report the finding either way. | uc-gradus CFAP, "Specialized" |
| A "Yes" in the Debian column is a starting signal, not a guarantee. Check the repository for recent activity before trusting it on a specific release. | This document, "Platform support is a flag, not a guarantee" |
| Pin roles in `requirements.yml`. Never install unpinned. | This document, "The roles are pinned, not floating" |
| When a need has no role, write your own, but say so in the findings report so the gap is visible. | This document, "Roles that do not exist" |
| The cache is a lookup aid. The repository is the authority. | This document, "The cache is a starting point, not a decision" |

## Facts

What needs to be memorized.

### Cache metadata 

| Item | Value | Source |
|---|---|---|
| Cache file | `robertdebock-ansible-roles-cache-v0.1.0.md` | Cache |
| Built from | `ansible-collection-roles` version 1.8.3 | Cache |
| Collection last commit | 2025-08-29 | Cache |
| Roles listed | 175 | Cache |
| Descriptions and platforms read from | Each role's `meta/main.yml` in the collection | Cache |
| Repository existence confirmed | All 175, on 2026-11-10 | Cache |
| Not covered | Roles published after the collection's last commit | Cache |

### Naming

| Thing | Pattern | Example | Source |
|---|---|---|---|
| Repository | `github.com/robertdebock/ansible-role-<name>` | `github.com/robertdebock/ansible-role-firewall` | Cache |
| Galaxy role name | `robertdebock.<name>` | `robertdebock.firewall` | Cache |
| Collection role name | `robertdebock.roles.<name>` | `robertdebock.roles.firewall` | Cache |

### Installation in uc-gradus

| Fact | Value | Source |
|---|---|---|
| Where pinned | `requirements.yml` at the top of the Ansible directory | uc-gradus CFAP, "Ansible layout, target" |
| Where installed | `~/.ansible/roles/` | uc-gradus CFAP, "Ansible layout, target" |
| Never in the repository | The role source itself | uc-gradus CFAP, "Ansible layout, target" |
| Install command | `ansible-galaxy install -r requirements.yml` | README |
| Form used in `requirements.yml` | `robertdebock.<name>` with a `version` pin | Owner |

### Roles used by uc-gradus today

| Role | Version | Used by | Source |
|---|---|---|---|
| `robertdebock.bootstrap` | 7.1.7 | `onboard.yml` | Repo |
| `robertdebock.users` | 6.1.8 | `onboard.yml` | Repo |

The README lists eleven robertdebock roles as intended. Only two are installed today. The gap is tracked in the uc-gradus CFAP under "Where the files and the README disagree."

### Needs with no role (as of 2026-11-10)

| Name looked for | Possible substitute | Source |
|---|---|---|
| `caddy` | None found. uc-gradus writes its own. | Cache |
| `incus` | None found. uc-gradus writes its own. | Cache |
| `nftables` | `firewall` may cover port management; check whether it supports nftables specifically. | Cache |
| `sshguard` | `fail2ban` covers the same problem class with a different tool. | Cache |
| `cinnamon` | None found. | Cache |
| `apparmor` | None found. | Cache |
| `sudo` | `users` grants sudo membership via group. | Cache |
| `timezone` | `ntp` sets timezone as part of its configuration. | Cache |
| `unattended_upgrades` | `auto_update` covers this need. | Cache |

Source for this table: Cache, "Needs with no role."

### Key roles for the trunk and first chain

| Need | Role | Debian | Notes |
|---|---|---|---|
| Make a node Ansible-manageable | `bootstrap` | Yes | Installs Python, sudo, basic dependencies. Gathers facts itself. |
| Users and groups | `users` | Yes | Creates users, assigns groups, sets passwords, can write `authorized_keys`. |
| Firewall | `firewall` | Yes | Manages ports across distributions. Uses the distribution's native backend. |
| SSH hardening | `openssh` | Yes | Configures `sshd_config`. |
| Repeated failed logins | `fail2ban` | Yes | Alternative to sshguard. |
| Updates | `update` | Yes | Applies pending updates. |
| Automatic updates | `auto_update` | Yes | Configures `unattended-upgrades` on Debian. |
| Locale | `locale` | Yes | Sets system locale. |
| Cron | `cron` | Yes | Installs and configures cron. |
| NTP / time sync | `ntp` | Yes | Installs and configures NTP. Also sets timezone. |
| Hostname | `hostname` | Yes | Sets the hostname persistently. |
| Sysctl | `sysctl` | Yes | Applies kernel parameter tuning. |
| Audit | `auditd` | Yes | Installs and configures the Linux audit daemon. |
| SELinux | `selinux` | Yes | Relevant for Fedora/RHEL families. On Debian, a no-op or not applicable. |
| Logging | `rsyslog` | Yes | Central or local syslog. |
| PAM | `pam` | Not in collection | Listed in some playbooks but commented out of `requirements.yml`. |
| Limits | `ulimit` | Yes | Configures resource limits. |
| MOTD | `motd` | Not in collection | Listed in some playbooks but commented out. |

Source: Cache, and cross-checked against the uc-gradus `requirements.yml` and playbook excerpts.

## Procedures

What needs to be done.

### Consult the cache for a need

#### When

Before writing any new role, playbook or task.

#### Steps

1. State the need in plain terms. For example: "I need to restrict which users can log in via SSH."
2. Open the cache. Scan the "Roles by need" table for a matching category. If no category matches, scan the full "All roles" table alphabetically for a keyword.
3. If a candidate is found, open its repository URL. Read `defaults/main.yml` for the variables it accepts, and `README.md` for usage examples.
4. Determine: can this role express what I need using only its variables, or would I need to modify the role itself?
5. Report the finding. Format:

   | Field | Content |
   |---|---|
   | Need | The need in plain terms |
   | Candidate | Role name, or "none found" |
   | Repository | URL, or "n/a" |
   | Can it do it? | Yes, with variables / Yes, but needs modification / No |
   | Evidence | Which variables or tasks support the conclusion |
   | Action | Use the role / Write our own / Use a different tool that has a role |

#### Done when

The finding is recorded, and the decision (use, adapt, or write our own) is noted.

### Install or update pinned roles

#### When

A new role is added to `requirements.yml`, or an existing pin is bumped.

#### Steps

1. Edit `requirements.yml`. Add or change the entry:

   ```yaml
   - name: robertdebock.<name>
     version: "<pinned-version>"
   ```

2. Run `ansible-galaxy install -r requirements.yml` from the Ansible directory.
3. Verify the installed version: `ansible-galaxy list robertdebock.<name>`.
4. Run the playbook that uses the role in dev. Expect `changed=0` on a second run.
5. Commit the `requirements.yml` change. The role source stays in `~/.ansible/roles/`, never in the repository.

#### Done when

The role is installed at the pinned version, the playbook passes in dev, and `requirements.yml` is committed.

### Refresh the cache

#### When

Periodically, or when a need arises that the cache does not address and you suspect a new role may have been published.

#### Steps

1. Check the collection's repository for a newer version: `github.com/robertdebock/ansible-collection-roles`.
2. If newer, check Robert's GitHub account for roles published between the collection's last commit and today.
3. For each new role, read its `meta/main.yml` for description and platform support.
4. Update the cache file: add rows to "All roles," add the need to "Roles by need" if applicable, remove entries from "Needs with no role" if a role now exists.
5. Increment the cache version and update its changelog.
6. Note in this CFAP's "Open questions" whether any previously "no role" need is now covered.

#### Done when

The cache reflects the current state, its version is incremented, and its changelog records what changed.

### Evaluate a candidate role for a specific uc-gradus need

#### When

The cache points to a candidate, and you need to decide whether it fits.

#### Steps

1. Open the role's repository.
2. Read `defaults/main.yml`. List the variables that relate to your need.
3. Read `tasks/main.yml` and any OS-family-specific task files (`vars/Debian.yml`, `tasks/Debian.yml`). Confirm Debian is handled.
4. Check the repository's recent commits and open issues for anything that affects Debian 13 or your specific use case.
5. Check the role's Molecule test scenarios (if present) for Debian 13 coverage.
6. Decide: the role's variables express the need (use it as-is), the role almost expresses the need (fork or request a feature upstream), or the role does not express the need (write our own).
7. Record the finding per the "Consult the cache" procedure.

#### Done when

The finding is recorded with evidence, and the decision is made.

### Handle a need with no role

#### When

The cache and a manual search of Robert's repositories find no match.

#### Steps

1. Confirm the absence: search `github.com/robertdebock` for the keyword. Check alternate names (for example, "timezone" might be under `ntp`, "sudo" under `users`).
2. If truly absent, write a role in `roles/` following uc-gradus conventions.
3. Record the gap in the cache's "Needs with no role" table (if not already there), and note that uc-gradus wrote its own.
4. If the role is general enough, consider publishing it upstream and proposing it to Robert as a contribution.

#### Done when

The need is met (by our role or a substitute), and the gap is documented.

## Open questions and unclear points

| Question | Options or recommendation |
|---|---|
| The cache was built from collection version 1.8.3 (2025-08-29). Robert publishes continuously. How often should the cache be refreshed? | Option A: on demand, when a gap is encountered. Option B: quarterly. Recommended: A for now, revisit when the fleet grows and gaps become costly. |
| Some roles in the cache are for software uc-gradus will never install (Bareos, GitLab, Jenkins, mediawiki). Should the cache be trimmed to a relevant subset? | Option A: keep all 175, the "Roles by need" table already filters. Option B: a "uc-gradus relevant" subset. Recommended: A, the full list costs nothing to keep and prevents missing a useful role. |
| The `firewall` role's backend on Debian: does it use nftables, iptables, or ufw? The cache does not say. | Must be checked against the role's repository. If it uses iptables and uc-gradus wants nftables, this is a conflict to resolve. |
| `robertdebock.pam`, `robertdebock.motd`, `robertdebock.limits`, `robertdebock.chrony` appear in some playbook drafts but are not in the collection or the cache. Do they exist as standalone repositories? | Must be checked. If they do not exist, the playbooks referencing them need correction. |
| The cache says "Not covered: roles he published after the collection's last commit." How many roles now exist beyond 175? | Unknown. Requires a manual check of his GitHub account. |
| Should this CFAP and the cache file be one document or two? | Option A: two, as they are now (cache is the lookup, CFAP is the training). Option B: merge. Recommended: A, they serve different purposes and update at different frequencies. |
| Where does this CFAP live in the repository? | Recommended: beside the cache, in `en/docs/` or at the repository root. The owner to decide. |

## Resources

- [Robert de Bock's GitHub account](https://github.com/robertdebock)
- [Ansible roles collection](https://github.com/robertdebock/ansible-collection-roles)
- [Ansible Galaxy](https://galaxy.ansible.com/robertdebock)

## Changelog

| Version | Status | Notes |
|---|---|---|
| 0.1.1 | Draft | First CFAP for the Robert de Bock roles: Concepts (why these roles, consult before create, cache as starting point, naming forms, platform support, missing roles, pinning, collection vs individual), Principles (five rules), Facts (cache metadata, naming, installation, roles used today, needs with no role, key roles for the trunk), Procedures (consult, install, refresh cache, evaluate candidate, handle a gap), Open questions (refresh cadence, trimming, firewall backend, phantom roles, role count beyond 175, one or two documents, location) |
