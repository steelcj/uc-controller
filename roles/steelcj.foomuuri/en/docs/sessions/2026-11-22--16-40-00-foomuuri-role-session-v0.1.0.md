# Session record: creating ansible-role-foomuuri

- **Version:** 0.1.0
- **Date:** 2026-11-22
- **License:** Apache-2.0
- **Author:** Christopher Steel, with Claude

## Purpose

Records how `steelcj.foomuuri` was designed, built and tested on 2026-11-22, during the uc-raw-node refactor, and the decisions taken along the way. The role's behaviour is described in the README; this record explains why it is the way it is.

## Why a role of its own

uc-raw-node needs a firewall that meets the raw node contract's firewall clauses (RN-FW-01 to RN-FW-04): Foomuuri, as the only nftables table, with `nftables.service` masked. Following the "consult before you create" principle of the robertdebock roles CFAP:

| Field | Content |
| :-- | :-- |
| Need | A firewall on nftables that meets the raw node contract's firewall clauses |
| Candidate | `robertdebock.firewall`; the `foomuuri` role in `lanefu/ansible-collection-clammy` |
| Repository | `github.com/robertdebock/ansible-role-firewall`; `github.com/lanefu/ansible-collection-clammy` |
| Can it do it? | No. `robertdebock.firewall` installs `ufw` on Debian with a default of `allow`, and never masks `nftables.service`. The clammy role is built for routers, with no README. |
| Evidence | `robertdebock.firewall`'s `vars/main.yml` and `tasks/main.yml`; the clammy collection's role listing |
| Action | Write our own: `steelcj.foomuuri` |

`robertdebock.firewall` was kept as the model for the role's shape: a short list of services as the interface, removal of conflicting packages, per-distribution vars with a fallback chain, and validation before a change is applied.

## Decisions

### One general role, configured by variables

The firewall's install, service and configuration live in one role, used as `steelcj.foomuuri`. The role knows Foomuuri and nothing about raw nodes. uc-raw-node passes its contract values as role variables, written directly under the role entry in the style of Robert de Bock's READMEs.

### The role calculates, the caller decides

A caller states only what a person decides, and the role works out the Foomuuri syntax:

- `foomuuri_ssh_port: 22` renders the `ssh` macro, any other port renders `tcp <port>`.
- `foomuuri_ssh_sources` and a service's `sources` become `saddr`, with addresses separated by spaces and IPv4 and IPv6 mixed, or are left out when empty, meaning any source.
- A service name that is a number or range is a port, anything else a Foomuuri macro.
- The public zone's interfaces come from the installed Foomuuri version.

uc-raw-node's call is therefore two variables, `foomuuri_ssh_port` and `foomuuri_ssh_sources`.

### Fragments, and no policy lines

Foomuuri reads `/etc/foomuuri/*.conf` in alphabetical order and merges sections with the same name, except that a zone may be defined only once and a repeated macro overwrites the earlier one. The role writes one fragment per call. The base fragment, `10-base`, holds the zones, base services, SSH and outgoing rules, and later fragments only add rules. No section ends with a policy line, because Foomuuri appends `drop log`, or `reject log` for `localhost-*` sections, after merging, and an explicit drop in an early fragment would hide every later rule.

### Checked before loaded

`foomuuri check` runs as a task right after any configuration change, before the reload handler, so a bad configuration fails the play at the step that wrote it and is never loaded.

### The version from Foomuuri itself

The installed version is read with `foomuuri --version`, rather than from package facts, which need `python3-apt` on Debian.

### No SSH rate limit

Foomuuri's host firewall example limits SSH to 5 connections a minute per source. The role sets no limit, because that would throttle an orchestration controller running Ansible, which opens many connections.

## Testing

### Checks before the first run

`yamllint` and `ansible-lint` with the production profile passed, every playbook passed `--syntax-check`, and `molecule syntax` passed. The template was rendered for several cases, and the variable checks were fed bad input. Foomuuri itself could not be run in the build environment.

### First run: the catch-all interface

The first `molecule test`, of 0.1.0, failed at `foomuuri check` with "All-wildcard strings are not supported". The zone line `public *` came from Foomuuri's current documentation, but the catch-all interface `*` was added in Foomuuri 0.33, released 2026-06-03. Debian 13 ships an earlier version, which passes `*` to nftables as a literal interface name.

Version 0.1.1 calculates the public zone's interfaces from the installed version: `*` on 0.33 or later, and `eth* en* wl*` before that. The 0.27 and 0.28 source tags were read to confirm that interface-name wildcards such as `eth*` already work there.

### Second run: passed

A rerun first used the old 0.1.0 folder by mistake, since the 0.1.1 tarball unpacks into a folder without a version in its name. The testing guide now says to check the folder's version first. Run from the 0.1.1 folder, every Molecule action succeeded: create, prepare, converge, idempotence, verify and destroy.

## Left for later

Recorded in `ROADMAP.md`: a converge case for `ssh saddr …` on port 22, Foomuuri's full list of conflicting firewalls, an empty cleanup playbook, publishing and tagging the repository, a LICENSE file, CI, and, if needed, installing Foomuuri from source.

## Changes

### v0.1.0

- First version, recording the design, build and testing of `steelcj.foomuuri` 0.1.0 to 0.1.2 on 2026-11-22.
