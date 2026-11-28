# Testing ansible-role-foomuuri with Molecule and Incus

- **Version:** 0.1.0
- **Date:** 2026-11-22
- **License:** Apache-2.0
- **Author:** Christopher Steel

## Purpose

How to run the role's Molecule scenario by hand, from a Python virtual environment through a full run, and how to find the cause when a step fails. The scenario launches `images:debian/13` as an Incus system container on the machine running Molecule, so it needs a working Incus installation on that machine.

## Set up the venv

```sh
. ~/.venvs/ansible/current/bin/activate
pip install molecule ansible-core ansible-lint yamllint
```

If ansible-core is already in that venv, pip leaves it alone. You don't need a Molecule driver plugin, because the scenario uses Molecule's built-in default driver and runs `incus` itself.

## Check that Incus works for your user

```sh
incus list
incus image list images: debian/13 --format csv | head -3
```

The first command must work without `sudo`. If it doesn't, your user needs to be in the `incus-admin` group. The second confirms the `images:` remote can reach `debian/13`. The first run downloads that image, so it takes a minute.

## Get the role and run

From a clone of the repository:

```sh
cd ~/src/ansible-role-foomuuri
molecule test
```

* [molecule-test-output-example.md](./molecule-test-output-example.md)

Or from a release tarball, which unpacks into a folder named `ansible-role-foomuuri` whatever the version:

```sh
mkdir -p ~/src && cd ~/src
tar -xzf ~/Downloads/ansible-role-foomuuri-<version>.tar.gz
cd ansible-role-foomuuri
molecule test
```

Before running, make sure you are in the folder of the version you mean to test. Unpacking a new tarball beside an older, renamed folder leaves the older one in place:

```sh
head -5 CHANGELOG.md
```

`molecule test` installs `community.general` from `molecule/default/requirements.yml` and launches `foomuuri-debian13`. It then converges the role, runs it a second time to check idempotence, runs the verify step and deletes the container. A good run ends with every action marked successful in the scenario recap:

```
SCENARIO RECAP
default                   : actions=9  successful=8  disabled=0  skipped=0  missing=0  failed=0
```

## When something fails

Run the steps one at a time and keep the container:

```sh
molecule create
molecule prepare
molecule converge
molecule idempotence
molecule verify
```

To look inside the container, use Incus directly. `molecule login` won't work, because it expects SSH:

```sh
incus exec foomuuri-debian13 -- bash
cat /etc/foomuuri/10-base.conf
foomuuri --version
foomuuri check
nft list ruleset
systemctl status foomuuri nftables
```

To keep the container after a failed full run:

```sh
molecule test --destroy=never
```

Clean up afterwards with:

```sh
molecule destroy
```

When reporting a problem, include the output of the first failing step, whether create, converge, idempotence or verify, and the Foomuuri version from `foomuuri --version`.

## Recording a result

After a full run, add a row to the results table in the README's Testing section, with the date, the role version, the platform and the result.

## Changes

### v0.1.0

- First version, from the first manual runs on 2026-11-22: setting up the venv, checking Incus, running from a clone or a tarball, checking the folder's version, working through a failure, and recording a result.
