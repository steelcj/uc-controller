# [Ansible role umask](#ansible-role-umask)

Install and configure umask on your system.

|GitHub|GitLab|Downloads|Version|
|------|------|---------|-------|
|[![github](https://github.com/robertdebock/ansible-role-umask/workflows/Ansible%20Molecule/badge.svg)](https://github.com/robertdebock/ansible-role-umask/actions)|[![gitlab](https://gitlab.com/robertdebock-iac/ansible-role-umask/badges/master/pipeline.svg)](https://gitlab.com/robertdebock-iac/ansible-role-umask)|[![downloads](https://img.shields.io/ansible/role/d/robertdebock/umask)](https://galaxy.ansible.com/robertdebock/umask)|[![Version](https://img.shields.io/github/release/robertdebock/ansible-role-umask.svg)](https://github.com/robertdebock/ansible-role-umask/releases/)|

## [Example Playbook](#example-playbook)

This example is taken from [`molecule/default/converge.yml`](https://github.com/robertdebock/ansible-role-umask/blob/master/molecule/default/converge.yml) and is tested on each push, pull request and release.

```yaml
---
- name: Converge
  hosts: all
  become: true
  gather_facts: true

  roles:
    - role: robertdebock.umask
      umask: "0027"
```

To also set a system-wide umask, in `/etc/login.defs` and `/etc/profile.d`, turn on `umask_system`. This is what governs the permissions `useradd` gives new home directories and what `pam_umask` applies to login sessions, so run the role before any users are created.

```yaml
---
- name: Converge
  hosts: all
  become: true
  gather_facts: true

  roles:
    - role: robertdebock.umask
      umask: "0027"
      umask_system: true
```

The machine needs to be prepared. In CI this is done using [`molecule/default/prepare.yml`](https://github.com/robertdebock/ansible-role-umask/blob/master/molecule/default/prepare.yml):

```yaml
---
- name: Prepare
  hosts: all
  become: true
  gather_facts: false

  roles:
    - role: robertdebock.bootstrap
```

Also see a [full explanation and example](https://robertdebock.nl/how-to-use-these-roles.html) on how to use these roles.

## [Role Variables](#role-variables)

The default values for the variables are set in [`defaults/main.yml`](https://github.com/robertdebock/ansible-role-umask/blob/master/defaults/main.yml):

```yaml
---
# defaults file for umask

umask: "0022"

umask_users:
  - root

# Configure a system-wide umask, not just per-user shell rc files.
# Off by default so the role's original behaviour is unchanged.
umask_system: false

# Mode for new home directories, written as HOME_MODE in login.defs and
# applied by useradd. Leave empty ("") to let useradd derive it from UMASK.
umask_home_mode: "0750"

# Also write /etc/profile.d/umask.sh so login shells pick up the umask
# regardless of the distribution's own profile defaults.
umask_profile_d: true
```

By default the role only appends a `umask` line to each `umask_users` account's `~/.bashrc`. That reaches interactive shells for those users and nothing else.

### System-wide umask

Set `umask_system: true` to configure the umask at the system level instead of, or in addition to, the per-user shell files. When enabled the role:

- sets `UMASK` in `login.defs` to `umask`, keeping a backup, which `pam_umask` and `useradd` read,
- sets `HOME_MODE` in `login.defs` to `umask_home_mode`, which `useradd` uses for the mode of a new home directory, and
- writes `/etc/profile.d/umask.sh` so login shells pick up the umask regardless of the distribution's profile defaults, controllable with `umask_profile_d`.

Editing `login.defs` does not change the umask of the running Ansible connection, so the effect is on `useradd` and future logins. Run the role before creating users so their home directories are created with the intended permissions. Set `umask_users: []` to skip the per-user `~/.bashrc` step and rely on the system-wide configuration alone.

The role does not modify PAM configuration. Current Debian and RedHat family systems already include `pam_umask` in the session stack, honouring `login.defs`.

## [Requirements](#requirements)

- pip packages listed in [requirements.txt](https://github.com/robertdebock/ansible-role-umask/blob/master/requirements.txt).

## [State of used roles](#state-of-used-roles)

The following roles are used to prepare a system. You can prepare your system in another way.

| Requirement | GitHub | GitLab |
|-------------|--------|--------|
|[robertdebock.bootstrap](https://galaxy.ansible.com/robertdebock/bootstrap)|[![Build Status GitHub](https://github.com/robertdebock/ansible-role-bootstrap/workflows/Ansible%20Molecule/badge.svg)](https://github.com/robertdebock/ansible-role-bootstrap/actions)|[![Build Status GitLab](https://gitlab.com/robertdebock-iac/ansible-role-bootstrap/badges/master/pipeline.svg)](https://gitlab.com/robertdebock-iac/ansible-role-bootstrap)|

## [Context](#context)

This role is part of many compatible roles. Have a look at [the documentation of these roles](https://robertdebock.nl/) for further information.

Here is an overview of related roles:
![dependencies](https://raw.githubusercontent.com/robertdebock/ansible-role-umask/png/requirements.png "Dependencies")

## [Compatibility](#compatibility)

This role has been tested on these [container images](https://hub.docker.com/u/robertdebock):

|container|tags|
|---------|----|
|[Alpine](https://hub.docker.com/r/robertdebock/alpine)|all|
|[Debian](https://hub.docker.com/r/robertdebock/debian)|all|
|[EL](https://hub.docker.com/r/robertdebock/enterpriselinux)|9|
|[Fedora](https://hub.docker.com/r/robertdebock/fedora)|all|
|[Ubuntu](https://hub.docker.com/r/robertdebock/ubuntu)|all|

The minimum version of Ansible required is 2.12, tests have been done on:

- The previous version.
- The current version.
- The development version.

If you find issues, please register them on [GitHub](https://github.com/robertdebock/ansible-role-umask/issues).

## [License](#license)

[Apache-2.0](https://github.com/robertdebock/ansible-role-umask/blob/master/LICENSE).

## [Author Information](#author-information)

[robertdebock](https://robertdebock.nl/)

Please consider [sponsoring me](https://github.com/sponsors/robertdebock).
