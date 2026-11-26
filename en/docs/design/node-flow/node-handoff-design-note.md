# Node Handoff Design Note

Status: proposal, for discussion in uc-contracts. Optional at the current scale: not needed while one operator runs both controllers and writes the candidates file.

Date: 2026-11-18

## Purpose

This note proposes a signed handoff from the pre-contract controller to the orchestration controller. The handoff names the nodes the pre-contract controller has built, with what the orchestration controller needs to admit them. It is vetted before any node is contacted, and it never replaces admission.

## Context

Node creation and node configuration are split between two controllers, with the raw node contract between them.

The pre-contract controller creates nodes from many sources and prepares them to meet the contract. It speaks whatever each node generator requires.

The orchestration controller, uc-controller, admits nodes that meet the contract and configures them with distro agnostic methods.

Today, admission takes candidates from an operator-written candidates file, from a list of addresses, or from a subnet scan. The candidates file is the strongest of these, because the operator reads each host key fingerprint at the node's console. A shim that creates a node can learn the same fingerprint directly, for example with `incus exec`. The handoff lets it pass that on, so the orchestration controller gets console-grade candidates without an operator at a console.

## Why the handoff must be vetted

In the handoff, the fingerprint takes the place of the operator reading the console. Admission checks that each node presents the fingerprint the handoff names. If anyone could write a handoff, they could name their own node with its own fingerprint, and admission would confirm the match. The fingerprint check is only as trustworthy as the handoff's origin.

A handoff is also a file of settings from another system. Loaded as an Ansible inventory or with `-e @file`, it could set connection variables such as `ansible_ssh_common_args` or a `ProxyCommand`. Those could switch off host key checking or run commands on the orchestration controller. The handoff is therefore read as data, never loaded as inventory or extra vars.

## The handoff document

### Fields

```yaml
handoff_format: 0.1.0
handoff_id: 2026-11-18-incus-01
producer: pre-contract-controller
contract: raw-node 0.3.1
created: '2026-11-18T18:56:00-05:00'
expires: '2026-11-19T18:56:00-05:00'
candidates:
  - name: incus-web-01
    address: 10.20.0.15
    ssh_port: 22
    fingerprint: SHA256:...
    batch: raw-1970-01-01-01
    source: incus-container
```

`handoff_format` is the version of this document format. `handoff_id` is unique per handoff. `producer` names the signer and must match the signature's identity. `contract` names the contract version the nodes were built to.

Each candidate needs `address`, `fingerprint` and `batch`. `name` is provisional, because admission files a node under its confirmed hostname. `ssh_port` defaults to 22. `source` is informational and is recorded, not trusted.

No other fields are allowed, at the top level or in a candidate.

### Signature

The handoff is signed with an SSH signature, which needs no tools beyond OpenSSH. The pre-contract controller signs with its own key, in the namespace `uc-handoff`:

```
ssh-keygen -Y sign -f ~/.ssh/pre-contract-controller -n uc-handoff handoff.yml
```

This writes `handoff.yml.sig`. The orchestration controller keeps an `allowed_signers` file naming the keys it accepts, and verifies before reading anything else:

```
ssh-keygen -Y verify -f allowed_signers -I pre-contract-controller \
  -n uc-handoff -s handoff.yml.sig < handoff.yml
```

The pre-contract controller's signing key is used for nothing else. In particular, it is not the key that logs into nodes.

### Lifetime

A handoff is valid from `created` until `expires`. An expired handoff is refused, so an old one cannot be replayed against an address that has since been reused. A day is a reasonable default lifetime. Admission is already idempotent for known nodes, so using a handoff twice within its lifetime is harmless. The orchestration controller may also record each `handoff_id` it has used.

## Vetting, in order

1. Verify the signature against `allowed_signers`. On failure, refuse the whole handoff without parsing it.
2. Parse it and check its shape: every required field present, formats correct, no unknown fields, no address twice. On failure, refuse the whole handoff.
3. Check that `producer` matches the signer, and that the time now is between `created` and `expires`.
4. Check that `contract` is a version admission supports, and that every named batch exists in the batch vault.
5. Pass the candidates to admission, which checks each node against the contract exactly as it does now.

Any refusal in steps 1 to 4 exits 2, matching admission's rule for refused candidates.

## Requirements published by the orchestration controller

Some information crosses the boundary in the other direction. The pre-contract controller needs it to build nodes that meet the contract:

- the orchestration controller's SSH public key, for the initial user;
- the initial username;
- the batch passphrase hash, for the initial user's password;
- the contract versions it accepts.

The orchestration controller generates each batch and publishes only its hash. The passphrase never leaves the side that uses it for become, and onboarding can replace it later.

## Other ways to nominate candidates

The operator candidates file stays, for metal installs that cannot report back. The operator is trusted, so the file needs no signature, but it should be read as data in the same way. Optionally, the operator could sign it with their own key, listed in `allowed_signers`, so every nomination path is checked the same way.

The subnet scan stays as a fallback. It carries no fingerprint, so its nodes are trusted on first use, as today.

Phone-home, where a node announces itself, would be a further source of nominations. An announcement is not signed by a trusted controller, so it would carry the same weight as a scan result.

## Open questions

- Should the contract promise a Python interpreter and report the operating system family? The orchestration controller needs both to configure nodes, and today the contract only reports Python.
- Should `contract` in the handoff allow a range of versions, or exactly one?
- Where does the handoff travel: a shared directory, a git repository, or an upload to the orchestration controller?
- Should admission move from `-e @candidates.yml` to reading the candidates file as data now, before the handoff exists?
