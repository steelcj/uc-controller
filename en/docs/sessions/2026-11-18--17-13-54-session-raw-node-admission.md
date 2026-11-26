---
title: "Session record: raw node admission"
date: 2026-11-18
author: "Christopher Steel"
status: "Session record"
description: "What happened in the raw node admission session, phase by phase: what was built, what was decided along the way and why, what verification found, and where the work stands."
---

# Session record: raw node admission

Kickoff: `2026-11-16--23-55-01-kickoff-raw-node-admission.md`
Final report: `2026-11-18--17-13-55-final-report-raw-node-admission.md`
Sessions: 2026-11-17 evening to 2026-11-18 evening, with Claude Code (Claude Opus 5.5)

## Abstract

The kickoff asked for four phases: a secrets pattern and a batch password script, a checker for raw node confirmations, an admission playbook with a new raw source, and verification with documents. All four are done, on four branches in a separate worktree. Two things changed course along the way. The secrets scripts were replaced by plain Ansible Vault after review. Verification against a real node found three gaps in admission, each fixed and verified on the node. This record follows the order of the work. The outcome, the clause tables and the proposals for the next kickoff are in the final report.

## Before the phases

The kickoff required the pre-freeze branches to be merged into `main` first. They were not, and the working tree held uncommitted changes. You merged the post-freeze work up to `chore/pin-versions` and committed the onboarding changes. You answered two open questions:
- the supported contract versions are 0.3.0 and 0.3.1;
- session records and the final report go in `en/docs/sessions/`.

## Phase 1: secrets and the batch password

The first pattern used three pieces:
- `ansible-vault`, with encrypted files under `secrets/raw-batches/`;
- a vault password client, `scripts/vault-client.py`, reading `~/.config/uc-controller/vault/<id>`;
- `scripts/new_raw_batch.py`, to create, import, rehash and retire batches, with a pure-Python SHA-512 crypt, because Python 3.13 has no `crypt` module.

Three behaviours of Ansible shaped it:
- a failing client stops every run, even one that decrypts nothing;
- a client that is not executable has its text used as the vault password;
- the client path is resolved against the directory Ansible starts in.

The second was hit while testing, and a guard was added.

At the checkpoint you asked for three changes:
- `--retire` to check `raw_node_batch` on hosts;
- short imported passwords to be recorded as `meets_min_length: false` rather than refused;
- the seventh SHA-512 test vector.

You also asked that a missing `meets_min_length` be an error, not a default. The one existing entry was filled in by hand.

## Phase 2: reading and checking a confirmation

`scripts/check_raw_confirmation.py` reads a confirmation with PyYAML's `BaseLoader`, so a MAC such as `52:54:00:12:34:56` stays a string, and checks it against contract 0.3.0 and 0.3.1. It reports each finding with its clause and field, and prints the values admission needs.

There are 33 fixtures, each stating its expectations in its header. They include the real 0.1.0 confirmation of `deb13-vt-0001`, which fails on its version. `firewall_active: false` was made a warning, and you asked that whether it should be a failure be decided on purpose in the contract.

## Phase 3: admission

The `admitted` source joined `raw`, with these pieces:
- its own connection settings, with strict host key checking for that group only;
- a committed `ssh/known_hosts`, keyed by hostname through `HostKeyAlias`;
- `scripts/match_raw_identity.py`;
- `ingress/playbooks/05_admit.yml`, with an offline end-to-end test against stand-in `ssh` and `ssh-keyscan` programs.

`promote_node.py` and `reset_inventories.py` learned about `admitted.yml`, and `10_onboard.yml` now leaves admitted nodes out.

Midway through, you switched the shared checkout to `main` while a branch was being created, and the branch started from `main`. From then on all work moved to the worktree `../uc-controller-admission`, and the shared checkout was not switched again.

At the checkpoint you approved four choices:
- a short batch is admitted with a warning;
- the become password follows each host's own batch;
- the extra `conflict` decision;
- Incus hosts are not compared.

You asked that promotion keep strict host key settings, and that it warn rather than silently skip an encrypted vars file.

## The move to plain Ansible Vault

While you created the batch for the real node, the store turned out to hold a vault password as a batch password, and the scripts proved harder to follow than the problem warranted. You asked for plain Ansible Vault instead.

The instructions were written first and tested by hand on `main`:
- passphrases made with dice;
- one encrypted file under the vault ID `batches`;
- `openssl passwd -6` for the hash;
- an ad-hoc become against 203.0.113.10.

The repository then changed to match:
- the scripts, the store and their tests were removed;
- `ansible.cfg` names the passphrase file;
- admission takes `-e admit_batch_id` and measures the passphrase length itself;
- a test checks that no passphrase is ever printed, even at `-vvv`.

## Phase 4: verification

All against `deb13-vt-0001` at 203.0.113.10, one step at a time, reporting after each:

1. **Admission.** Admitted on first use, with every field written. You confirmed the ED25519 fingerprint at the console.
2. **Rerun.** Reported known, nothing changed.
3. **Changed key.** First the effective SSH options were shown, and `~/.ssh/known_hosts` was checked. Then one character of the recorded ED25519 key was changed: the strict connection refused the node, but admission still reported it known. This was the first gap. After the fix, admission refused it. `ssh/known_hosts` was restored by checksum each time.
4. **Discovery on `203.0.113.10/32`.** It found nothing. Without root, `nmap -sn` probes only ports 80 and 443, which a contract node drops. This was the third gap. We discussed letting the node announce itself instead, and the operator naming nodes by hand. You chose to fix the scan, and with `-PS22` it found the node, which admission reported known.

The second gap was the exit status: refused and stopped candidates now make the run exit 2, after the report.

You then asked for a candidates file pairing each address with its console fingerprint, so several nodes can be admitted without trusting any on first use. While testing it, a test of my own made all its invalid cases share one file. The fault was in the test, not the playbook, and it was fixed.

## Documents

Written for this kickoff, in the house style from sat-doc-automa:
- the design document v0.1.7;
- `en/docs/contracts.md`;
- `en/docs/admitting-a-raw-node.md`;
- the vault guide rewritten for plain Ansible Vault;
- this record and the final report.

The final report holds the clause tables, the changes the onboarding kickoff must make, and a phone-home proposal.

## Where things stand

- Every phase is committed, except these documents, which wait for your review.
- The boundary check and all 34 tests pass.
- Nothing is pushed or merged.
- The node `deb13-vt-0001` is admitted in the worktree's generated `admitted.yml`, and its keys are committed in `ssh/known_hosts`.

## Changelog

| Date | Notes |
| --- | --- |
| 2026-11-18 | First version |
| 2026-11-26 | Real host, address, batch, MAC and machine id values replaced by example values before the repository is recreated |
