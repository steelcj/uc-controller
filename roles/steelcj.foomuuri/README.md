# [Ansible role foomuuri](#foomuuri)

Install and configure [Foomuuri](https://foomuuri.foobar.fi/latest/), a zone-based nftables firewall.

The role writes one Foomuuri fragment, `/etc/foomuuri/<fragment>.conf`. With the defaults, that fragment is a host firewall: DHCP, DHCPv6, ping and SSH in, everything out, and everything else in dropped and logged by Foomuuri's own final rule.

## [Example Playbook](#example-playbook)

This example is taken from [`molecule/default/converge.yml`](molecule/default/converge.yml). There is no CI yet: the scenario is run by hand against an Incus container, as described in [Testing](#testing).

```yaml
---
- name: Converge
  hosts: all
  become: true
  gather_facts: true

  roles:
    - role: steelcj.foomuuri
      foomuuri_ssh_port: 2222
      foomuuri_ssh_sources:
        - 192.0.2.0/24
        - 2001:db8::/32
      foomuuri_services:
        - name: https
        - name: 1337
        - name: 5353
          protocol: udp
          sources:
            - 198.51.100.0/24
        - name: http
          state: absent
```

The machine needs to be prepared. In CI this is done using [`molecule/default/prepare.yml`](molecule/default/prepare.yml):

```yaml
---
- name: Prepare
  hosts: all
  gather_facts: false
  tasks:
    - name: Install Python and sudo
      ansible.builtin.raw: >-
        (command -v python3 && command -v sudo) >/dev/null ||
        (apt-get update -q && apt-get install -y -q python3 sudo)
      changed_when: false
```

On real hosts, [robertdebock.bootstrap](https://github.com/robertdebock/ansible-role-bootstrap) does the same. On the RHEL family, Foomuuri comes from EPEL, so run [robertdebock.epel](https://github.com/robertdebock/ansible-role-epel) first.

The example renders this fragment on Foomuuri 0.33 or later. Before 0.33, as on Debian 13, the public zone line is `public eth* en* wl*`.

```
zone {
  localhost
  public *
}

public-localhost {
  dhcp-client
  dhcpv6-client
  ping
  tcp 2222 saddr 192.0.2.0/24 2001:db8::/32
  https
  tcp 1337
  udp 5353 saddr 198.51.100.0/24
}

localhost-public {
  accept
}
```

## [What the role calculates](#what-the-role-calculates)

| You give | The role renders |
| :-- | :-- |
| `foomuuri_ssh_port: 22`, no sources | `ssh` |
| `foomuuri_ssh_port: 2222`, no sources | `tcp 2222` |
| `foomuuri_ssh_port: 2222`, two sources | `tcp 2222 saddr 192.0.2.0/24 2001:db8::/32` |
| `- name: https` | `https` |
| `- name: 1337` | `tcp 1337` |
| `- name: 8000-8010` | `tcp 8000-8010` |
| `- name: 5353`, `protocol: udp`, one source | `udp 5353 saddr <source>` |
| `- name: http`, `state: absent` | nothing |
| `public: []` in `foomuuri_zones`, Foomuuri 0.33 or later | `public *` |
| `public: []` in `foomuuri_zones`, Foomuuri before 0.33 | `public eth* en* wl*` |

A name that is a number or a range of numbers is a port, and anything else is a [Foomuuri macro](https://foomuuri.foobar.fi/latest/config/section/macro/). Several sources are written on one line, separated by spaces, and IPv4 and IPv6 can be mixed.

Foomuuri supports the catch-all interface `*` from version 0.33. Earlier versions pass it to nftables as a literal interface name, which nftables refuses, so the role uses interface-name wildcards there: `eth*` for containers and older naming, `en*` for `enp…`, `ens…` and `eno…`, and `wl*` for wireless. Give the public zone its own interfaces in `foomuuri_zones` to override both.

## [Fragments](#fragments)

Foomuuri reads `/etc/foomuuri/*.conf` in alphabetical order and merges sections with the same name. The role uses that to let several plays or roles add rules:

- The base fragment, `10-base` by default, holds the `foomuuri` options, the zones, the base services, SSH and the outgoing rules. A zone may only be defined once, so only the base fragment defines zones.
- Any other fragment holds only its `foomuuri_services` and `foomuuri_rules`, which Foomuuri adds to the same sections.
- No section ends with a policy line. Foomuuri appends `drop log` itself, or `reject log` for `localhost-*` sections, after all fragments are merged, so a later fragment's rules are never hidden behind an earlier fragment's drop.

A second call, from another play:

```yaml
  roles:
    - role: steelcj.foomuuri
      foomuuri_fragment: 20-web
      foomuuri_keep_fragments:
        - 10-base
      foomuuri_services:
        - name: http
        - name: https
```

With `foomuuri_purge: unmanaged`, each call removes `.conf` files it does not manage, so list the other calls' fragments in `foomuuri_keep_fragments`, or set `foomuuri_purge: none` on the later calls.

## [Role Variables](#role-variables)

The default values for the variables are set in [`defaults/main.yml`](defaults/main.yml):

```yaml
---
# defaults file for foomuuri

# The port SSH listens on. 22 renders the ssh macro, any other port renders
# "tcp <port>". Set to 0 to render no SSH rule, which also needs
# foomuuri_require_ssh: false.
foomuuri_ssh_port: 22

# Addresses or networks, IPv4 or IPv6, allowed to reach SSH. Empty means any.
foomuuri_ssh_sources: []

# Extra services to accept from the public zone. A name is a Foomuuri macro
# (https, domain) or a port number or range (1337, 8000-8010). protocol
# defaults to foomuuri_default_protocol, sources to any. Use state: absent to
# leave a service out.
foomuuri_services: []

# The protocol for a service given as a port number.
foomuuri_default_protocol: tcp

# Services every host needs to stay reachable.
foomuuri_base_services:
  - dhcp-client
  - dhcpv6-client
  - ping

# Outgoing traffic: accept, or a list of services to allow. With a list,
# everything else outgoing is rejected and logged.
foomuuri_outgoing: accept

# Advanced: settings most callers never change.

# The file this call writes, /etc/foomuuri/<fragment>.conf, and whether it is
# present or absent.
foomuuri_fragment: 10-base
foomuuri_fragment_state: present

# The fragment that holds the foomuuri, zone, SSH, base and outgoing rules.
# Only one fragment may define the zones.
foomuuri_base_fragment: 10-base

# Remove .conf files in /etc/foomuuri that this call did not write: unmanaged
# or none. When the role is called more than once, list the other calls'
# fragments in foomuuri_keep_fragments. Paths in foomuuri_purge_exclude, relative
# to /etc/foomuuri, are never removed.
foomuuri_purge: unmanaged
foomuuri_keep_fragments: []
foomuuri_purge_exclude: []

# Remove ufw and firewalld, and mask nftables.service, whose stop action
# flushes the whole ruleset.
foomuuri_disable_conflicting: true

# Refuse a base fragment that does not accept SSH, to avoid locking out the
# caller.
foomuuri_require_ssh: true

# The oldest Foomuuri version the role accepts, read with "foomuuri --version".
foomuuri_minimum_version: "0.22"

# Connections where the service is not started or reloaded, such as Docker
# containers. The configuration is still written and checked.
foomuuri_skip_connections:
  - container
  - docker
  - community.docker.docker

# Options for the foomuuri { } section, for example dbus_firewalld: "yes".
foomuuri_config: {}

# Zones and their interfaces. A public zone given no interfaces gets
# foomuuri_public_interfaces.
foomuuri_zones:
  localhost: []
  public: []

# The interfaces of a public zone given none: the catch-all "*" on Foomuuri
# 0.33 or later, which first supported it, and interface-name wildcards before
# that.
foomuuri_public_interfaces: "{{ ['*'] if foomuuri_version.stdout | trim is version('0.33', '>=') else ['eth*', 'en*', 'wl*'] }}"

# Raw Foomuuri rules per zone pair, for anything foomuuri_services cannot
# express. Rules for public-localhost and localhost-public are added after the
# role's own rules for those sections.
foomuuri_rules: {}

# Foomuuri macro, iplist and template sections. Macros and iplists map a name
# to its value, templates map a name to a list of rules.
foomuuri_macros: {}
foomuuri_iplists: {}
foomuuri_templates: {}

# Extra files to place in /etc/foomuuri, each with a name and either content
# or src, and an optional state.
foomuuri_files: []
```

## [How the role applies a change](#how-the-role-applies-a-change)

1. Checks the variables, once, on the controller.
2. Removes `ufw` and `firewalld`, and installs `foomuuri`.
3. Checks that the installed Foomuuri is at least `foomuuri_minimum_version`.
4. Masks `nftables.service`.
5. Writes or removes the fragment and the extra files, and removes unmanaged `.conf` files.
6. Runs `foomuuri check` when anything changed, so a bad configuration fails the play before it is loaded.
7. Starts and enables `foomuuri.service`, and reloads it through a handler when the configuration changed.

The configuration is always written and checked. Only starting and reloading the service is skipped for the connections in `foomuuri_skip_connections`. An Incus system container, reached through `community.general.incus`, gets the full role, since it has its own network stack and needs its own firewall.

## [Requirements](#requirements)

- ansible-core 2.15 or later. The role itself uses ansible-core modules only.
- For the Molecule scenario: Molecule, the `incus` client with permission to use it, and the `community.general` collection for the `community.general.incus` connection plugin, listed in [`molecule/default/requirements.yml`](molecule/default/requirements.yml).

## [Testing](#testing)

The Molecule scenario launches `images:debian/13` as an Incus system container on the machine running Molecule, converges the role over `incus exec`, runs it again to prove it is idempotent, verifies the result and deletes the container:

```sh
molecule test
```

The verify step checks that the fragment holds the calculated rules, that the public zone matches the installed Foomuuri version, that `foomuuri check` passes, that `foomuuri.service` is active and enabled and `nftables.service` masked, that Foomuuri's table is the only nftables table, and that the SSH port is in the loaded ruleset.

The full procedure, from setting up a virtual environment to finding the cause of a failure, is in the [Molecule testing guide](en/docs/guides/manual-testing/molecule-incus-testing-v0.1.0.md).

| Date | Version | Platform | Result |
| :-- | :-- | :-- | :-- |
| 2026-11-22 | 0.1.1 | Incus `images:debian/13` | All Molecule actions successful |

## [Compatibility](#compatibility)

This role has been written for these platforms:

| container | tags |
| :-- | :-- |
| Debian | trixie |

Other distributions that package Foomuuri, such as Ubuntu and Fedora, and the RHEL family through EPEL, should work, but are not tested yet.

## [Roadmap](#roadmap)

Planned and possible work is in [`ROADMAP.md`](ROADMAP.md).

## [License](#license)

Apache-2.0

## [Author Information](#author-information)

Christopher Steel. Structure and conventions follow the roles of [Robert de Bock](https://github.com/robertdebock).
