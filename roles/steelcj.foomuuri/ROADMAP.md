# Roadmap

## Next

### Test SSH on port 22 with sources

Add a converge case with `foomuuri_ssh_port: 22` and `foomuuri_ssh_sources` set. It renders `ssh saddr …`, the Foomuuri macro followed by an address matcher, which has not yet been through `foomuuri check`. The documented scenario uses port 2222, which renders `tcp 2222 saddr …` instead.

### Remove every conflicting firewall

Foomuuri's [installation guide](https://foomuuri.foobar.fi/latest/install/) lists ferm, firehol, firewalld, netfilter-persistent, nftables, ufw and shorewall as firewall services to disable. The role removes `ufw` and `firewalld` and masks `nftables.service`. Extend `_foomuuri_packages_conflicting` to the full list.

### Add an empty cleanup playbook

Molecule runs a cleanup step after a failed action, and the scenario has none, so a failed run warns "cleanup: Executed: Missing playbook". An empty `molecule/default/cleanup.yml` removes the warning.

### Publish and tag

Publish the role as its own repository, `github.com/steelcj/ansible-role-foomuuri`, with a version tag, so callers can pin it in `requirements.yml`.

### Add a LICENSE file

`meta/main.yml` and the README state Apache-2.0, but the repository has no `LICENSE` file yet.

## If needed

### Install Foomuuri from source

Add `foomuuri_install_method`, with `package` as the default and `source` as an option, for when a feature needs a newer Foomuuri than the distribution ships.

- Install a pinned release, `foomuuri_source_version`, checked against `foomuuri_source_checksum`.
- Download the release tarball from `https://github.com/FoobarOy/foomuuri/releases` on the controller and copy it to the node, so nodes with poor or no internet access still work.
- Run upstream's own `make install DESTDIR=/`, then `systemctl daemon-reload` and `sysctl --system`, as the [installation guide](https://foomuuri.foobar.fi/latest/install/) documents, rather than repeating its file list in tasks. The node needs `make`, but no compiler.
- Install only when `foomuuri --version` differs from the pinned version, so a rerun changes nothing.
- Remove the distribution package first.
- Requirements: nftables 1.0.0 or later with JSON support, and Python 3.9 or later for 0.34, 3.12 or later from 0.35.
- Test it in a second Molecule scenario, `source`, beside `default`.

The cost: with `source`, the distribution no longer sends security fixes for Foomuuri, so updating it means changing the pin.

### Run the scenario in CI

The scenario needs an Incus host, so it cannot run on GitHub's hosted runners as it stands. A self-hosted runner with Incus, or a second scenario on a container driver CI supports, would give the role CI like Robert de Bock's roles have.
