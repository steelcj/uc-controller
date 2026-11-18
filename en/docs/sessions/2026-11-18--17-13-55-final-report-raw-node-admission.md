---
title: "Kickoff final report: raw node admission"
date: 2026-11-18
author: "Christopher Steel"
status: "Final report"
description: "Outcome of the raw node admission kickoff: what was built, how it was verified against a uc-ventoy metal node, how admission checks the raw node contract and meets the privileged access policy, what the next kickoff must change, and a phone-home proposal."
---

# Kickoff final report: raw node admission

Date: 2026-11-18
Kickoff: `2026-11-16--23-55-01-kickoff-raw-node-admission.md`
Session record: `2026-11-18--17-13-54-session-raw-node-admission.md`

## Abstract

uc-controller can now admit a raw node that meets the raw node contract into its raw inventory, as a new source, `admitted`. Admission checks the node's confirmation against the contract, requires its host keys to match the confirmation and a fingerprint read at its console, matches its identity against every stage inventory, records its keys in a committed `ssh/known_hosts`, and confirms a connection as `initial` and a become with the batch passphrase, with strict host key checking. It was verified against `deb13-vt-55b1`, a uc-ventoy metal node. Batch passphrases are kept with plain Ansible Vault, after the scripts first written for them were withdrawn on review. Three gaps found during verification were fixed: a known node whose keys had changed was not refused, refusals did not affect the exit status, and the discovery scan could not see contract nodes. Nothing is pushed or merged. Admitted nodes are not onboarded yet.

## Sources and acknowledgements

The work implements the ingress side of the raw node contract <a name="apa-steel-raw-node-contract-citation"></a>([Steel, 2026c](#apa-steel-raw-node-contract-reference)), prepares for the onboarding egress contract <a name="apa-steel-onboarding-egress-citation"></a>([Steel, 2026a](#apa-steel-onboarding-egress-reference)), and applies part of the privileged access policy <a name="apa-steel-privileged-access-citation"></a>([Steel, 2026b](#apa-steel-privileged-access-reference)). It follows the kickoff named above, with the changes agreed during the session and recorded in the session record.

## Branches, in merge order

Each branch contains the one before it, so merging `docs/raw-node-admission` brings in all four. They were developed in the worktree `../uc-controller-admission`.

| Order | Branch | Commits | Contents |
| --- | --- | --- | --- |
| 1 | `feat/secrets-and-batch-password` | 5 | Phase 1: the first secrets pattern, a vault client and `new_raw_batch.py`, and the batch store. Superseded: the scripts and the store were removed in branch 3 |
| 2 | `feat/raw-node-confirmation-check` | 7, and a merge of branch 1 | Phase 2: `check_raw_confirmation.py`, 33 fixtures, the test runner, and the batch store changes asked for at the Phase 1 checkpoint |
| 3 | `feat/raw-node-admission` | 12 | Phase 3: the `admitted` source, `ssh/known_hosts`, `match_raw_identity.py`, `05_admit.yml`, promotion and reset, `10_onboard.yml` exclusion, then plain Ansible Vault in place of the scripts, and the plain-vault guide |
| 4 | `docs/raw-node-admission` | 5, and these documents | Phase 4: the trusted keys of `deb13-vt-55b1`, the three fixes found during verification, the candidates file, and the Phase 4 documents |

Merging into the current `main`:
- `en/docs/guides/vault-guide.md` conflicts, add and add. `main` has the earlier guide to the removed scripts, from `a04450e` and `b5abaa5`. Keep this branch's version.
- `inventories/raw/group_vars/admitted/vault.yml` is identical on both sides, and merges cleanly.
- `en/docs/guides/plain-vault-batch-passwords.md`, on `main` only, describes the same procedure as the branch's `vault-guide.md`. It can be removed after the merge.

## Decisions and fixes

| Item | Status |
| --- | --- |
| Secrets pattern | Done, changed on review. First `vault-client.py`, `new_raw_batch.py` and a per-batch store; replaced by plain Ansible Vault: one encrypted file, `inventories/raw/group_vars/admitted/vault.yml`, vault ID `batches`, passphrases made with dice by the operator. Batch `raw-2026-11-17-manual` was retired with the store, because it held a vault password by mistake |
| Batch passphrase hash for uc-ventoy | Done: `openssl passwd -6`, at a hidden prompt. The pure-Python SHA-512 crypt was removed with the scripts |
| Confirmation checker | Done: contract 0.3.0 and 0.3.1, read with `BaseLoader`, duplicate keys refused, unknown fields as notes, `firewall_active: false` as a warning |
| `admitted` source | Done: SSH as `initial` with the controller key alone, strict host key checking for this group only, become password from the node's own batch |
| Controller's known hosts | Done: `ssh/known_hosts`, committed, keyed by inventory hostname through `HostKeyAlias` |
| Admission playbook | Done: `05_admit.yml`, the six steps of the kickoff, with undo when confirmation fails |
| Identity decisions | Done, with one decision added: `conflict`, a new hostname with a known `machine_id` or MAC address, stops the node |
| Promotion and reset | Done. `promote_node.py` keeps a host's strict host key settings, and warns when it passes over an encrypted vars file |
| `10_onboard.yml` | Done: targets `raw:!admitted`, and says in one line that onboarding contract nodes comes in a later kickoff |
| Known node with changed host keys | Fixed during verification: refused when its presented keys differ from `ssh/known_hosts` in any key type, or none are recorded |
| Exit status | Fixed during verification: 2 after the report for any refused or stopped candidate or an unconfirmed admission; 0 otherwise, including hosts that are not contract nodes |
| Discovery scan | Fixed during verification: `nmap -sn -PS22`. Without root, the default probes only ports 80 and 443, which a contract node drops |
| Candidates file | Added: `admit_candidates`, each address with its console fingerprint, as the main way to name candidates |
| Design document | Done: v0.1.7 |
| `en/docs/contracts.md` | Done |
| Guides | Done: `en/docs/admitting-a-raw-node.md`, and `en/docs/guides/vault-guide.md` for plain Ansible Vault |
| Session record | Done |

## Final verification

Against `deb13-vt-55b1`, a uc-ventoy metal node at 192.168.1.109, raw node contract 0.3.0, baseline 0.4.0, batch `raw-2026-11-18-01`. Nothing on the node was changed by any run.

| Check | Result |
| --- | --- |
| Fixture tests | `python3 tests/run_tests.py`: 34 tests pass, including the playbook end to end against stand-in nodes. `check_converge_boundary.py` passes; every playbook passes `--syntax-check` |
| Admission | `admitted`, exit 0. Every field in `admitted.yml`, three keys in `ssh/known_hosts`, connection, become and `ping` confirmed over the strict connection. Trusted on first use; the ED25519 fingerprint was then confirmed at the console |
| Rerun | `known`, exit 0. `admitted.yml` and `ssh/known_hosts` unchanged by checksum and modification time |
| Effective SSH options | From Ansible's own arguments with `ssh -G`: `StrictHostKeyChecking` on, `HostKeyAlias deb13-vt-55b1`, `UserKnownHostsFile` the repository's `ssh/known_hosts` only, `GlobalKnownHostsFile /dev/null`. `~/.ssh/known_hosts` holds an older entry for 192.168.1.109, which is not read |
| One character of the recorded ED25519 key changed | Connection refused: `REMOTE HOST IDENTIFICATION HAS CHANGED`. Admission reported `known` before the fix, and `refused`, exit 2, after it. Restored by checksum each time; the connection worked again |
| Discovery on `192.168.1.109/32` | No host found before the scan fix. After it, only 192.168.1.109 listed, and `admit_from_discovered=true` reported `known`, exit 0 |

## Raw node contract: what admission relies on

| Clause or field | How admission checks it |
| --- | --- |
| Versioning, `contract` | The confirmation's `contract` must be 0.3.0 or 0.3.1. Otherwise refused |
| RN-NET-01, top-level key | Exactly one key, a valid hostname, not an installer or image default, including uc-ventoy's names before the MAC suffix |
| RN-ACC-01, `user` | Must equal `initial` |
| RN-ACC-02 | Tested: the confirmation is read over SSH as `initial` with the controller key alone. A refusal makes the host `not-contract` |
| RN-ACC-04, `sudo` | `sudo` must be true, and become with the batch passphrase is tested before the node is kept |
| RN-ACC-05 | Not checked. The confirmation does not report it |
| RN-ACC-06 | Not checked by admission. The operator logs in at the console with the batch passphrase to read the fingerprint, which exercises it by procedure |
| RN-ACC-07, `sudo_nopasswd` | Must be false |
| RN-ACC-08 | Measured on the controller from the batch passphrase in Ansible Vault, never logged. Under 15 characters is a warning, and the node is still admitted |
| RN-SSH-01, `ssh_port` | Must equal the expected port, and the connection is made on it |
| RN-SSH-02, `interfaces` | At least one address must be reported, and the node must answer on the candidate address |
| RN-SSH-03, `ssh_password_auth` | Must be false, as reported. Not tested against the server |
| RN-FW-01 to RN-FW-04 | Not checked. `firewall_active: false` is reported as a warning only |
| RN-REP-01 | The confirmation is read from `/var/lib/raw-node/confirmation.yml` as `initial`, every field must be present with its shape, and duplicate keys are refused |
| `machine_id`, `interfaces[].mac` | Used for identity only, never for trust: known, reinstall, collision, conflict or new |
| `ssh_host_keys` | Must equal the keys the node presents, must include the console fingerprint when one is given, and, for a known node, must still equal the keys in `ssh/known_hosts` |
| `timestamp`, `baseline` | Shape checked; `baseline` recorded as `raw_node_baseline` |
| `python` | Reported, not relied on: Ansible's `ping` runs only when an interpreter is reported |

## Privileged access policy clauses

| Clause | Status | How |
| --- | --- | --- |
| PA-PWD-01 | Partly met | Batch passphrases are generated with dice, never chosen, and admission measures their length. Letters and digits are a procedure, a digit added from one more roll, and are not checked by code. `pwquality` on nodes is normalization's |
| PA-PWD-02 | Partly met | The batch passphrase is in the controller's secret store, Ansible Vault, but is shared by every node of a batch, as the raw node contract allows during the raw window. A password unique to each node is onboarding's, OE-ACC-03 |
| PA-HOST-01 | Met for admitted nodes | Strict checking against the keys recorded at admission, refusal on any difference, verified live. Other sources still run with `host_key_checking = False` |
| PA-HOST-02 | Partly met | A changed key is refused, and recording a change is a commit to `ssh/known_hosts`. There is no key register yet |
| PA-KEY-02 | Partly met | The controller's key for `initial` is Ed25519. Its private part is in `~/.ssh` on the workstation, not in the secret store |

## What the onboarding kickoff must change

To onboard admitted contract nodes, `ingress/playbooks/10_onboard.yml` must change as follows:

- **Admitted nodes.** Target the `admitted` group, through a play or a source-aware path, in place of the `raw:!admitted` exclusion and its message.
- **Connection.** Connect as `initial` with become and the batch passphrase, not as root. The first play's probes and `meta: end_host` guard assume a root connection.
- **Re-onboarding guard.** The `id initial` guard is commented out, since `initial` exists on every contract node. It needs a replacement, such as membership of the onboard inventory or a marker the onboarding writes.
- **Python.** Bootstrap Python with `raw` and become when the confirmation reports none.
- **sudo.** Stop granting `NOPASSWD`. `inventories/onboard/dev/group_vars/all.yml` still sets `sudo_options: "ALL=(ALL) NOPASSWD: ALL"` for `initial`.
- **Node password.** Generate a password unique to the node, set it, keep it in Ansible Vault under the `node` vault ID, and add `node` to `vault_identity_list`. Decide the file layout for node secrets.
- **Promotion.** Write the node's own become password into the onboard stage, as promotion already keeps its strict host key settings.
- **SSH.** Prove key-only SSH with `sshd -T`.

Onboarding egress clauses it would then deliver:
- OE-CON-05, `initial` obtains root with its password;
- OE-ACC-03, a password unique to the node in the secret store;
- OE-ACC-04, no `NOPASSWD` or `!authenticate`;
- OE-SSH-03, key-only SSH, tested;
- and it would stop delivering the retired OE-CON-02.

The firewall clauses OE-FW-01 to OE-FW-05 and OE-FWM-01 to OE-FWM-03 are also "Not yet". They are a separate piece of work, unless that kickoff takes them on.

## Phone-home proposal

Scanning is a poor fit for metal nodes: it cannot reach other subnets, it touches every host, and it can never confirm a host key out of band. A node that announces itself to the controller would replace it. This is input to the next kickoff, not part of this one.

### For uc-contracts

A minor version of the raw node contract would add:
- **A shared parameter, `controller_announce`:** the address and port, or URL, the node announces itself to. Empty means no announcement.
- **A clause, RN-REP-02:** the node announces itself at first boot and on every change of address, and repeats every few minutes until the controller has read its confirmation over SSH.
- **A message:** the confirmation's hostname, `contract`, `machine_id`, interface addresses, `ssh_port` and `ssh_host_keys`, as JSON. It holds no secret.
- **Trust:** an announcement only nominates a candidate. The controller trusts nothing in it, and admits the node only by the existing checks.

Outbound traffic is already allowed by RN-FW-03, so the node's firewall does not change.

### For uc-ventoy

A first-boot service, after `raw-node-firstboot.service`, sends the message with `curl` or `nc`, on a timer, and an address-change hook does the same. `controller_announce` becomes an optional input in `raw-node-input.yml`.

### For uc-controller

The simplest listener is a mode of the admission playbook that runs for a set time during a build session, such as `-e admit_listen=10m`. It collects announcements from configured networks only, and feeds each address to the same checks. The fingerprints in an announcement can be compared with the presented keys and the console. They are never a substitute for the console. A permanent service is possible later, at the cost of a daemon to run and secure.

## Untested, and why

- **The candidates file and the exit status rule against the real node:** tested offline only, against stand-in nodes. The live runs used `admit_addresses` and `admit_from_discovered`.
- **A node built to contract 0.3.1:** none exists yet. 0.3.1 changed wording only, and a fixture covers it.
- **Admission of a second node, a reinstall, or a name collision on real hardware:** only one contract node exists. These are covered by tests.
- **A full subnet scan:** not run, by decision. Only `192.168.1.109/32` was scanned.
- **RN-SSH-03 against the server:** admission relies on the reported `ssh_password_auth`.

## Open questions and things not done

- **`firewall_active`.** It is a warning, not a failure, because the agreed checks do not include it. Since the firewall is a security baseline, whether the raw node contract should make it a failure is a decision for uc-contracts.
- **Incus hosts in identity matching.** Hosts that only the Incus plugin supplies are in no file, and are not compared. Contract nodes have MAC-suffixed names, so a clash is unlikely.
- **Stale pointer.** `en/docs/contracts/uc-raw-node-contract.md` points to an old path in uc-contracts. `en/docs/contracts.md` has the current links.
- **Obsolete guide.** `en/docs/guides/using-vault-for-batched-passwords.md` describes the removed scripts, and is left for you to remove.
- **Old password files.** `~/.config/uc-controller/vault/raw_batch` and `~/.config/uc-controller/vault/node`, from the removed scripts, are no longer read.
- **Session file names.** The sessions README names only `session` and `kickoff-...` files. This report is named `...-final-report-raw-node-admission.md`. The README may want a line for final reports.
- **Worktree.** `../uc-controller-admission` can be removed after the merge, with `git worktree remove ../uc-controller-admission`. Its `inventories/raw/admitted.yml` and `discovered.yml` are generated and not committed. `admitted.yml` holds the entry for `deb13-vt-55b1`, which a checkout of the merged `main` will not have until admission runs there.
- **Phone-home.** Proposed above, for the next kickoff.
- **Convert the design document to Citation Anchor Pairs.** `en/docs/uc-controller-v0.1.7.md` still cites with its older `cite-` and `ref-` anchors. The documents written in this kickoff use Citation Anchor Pairs, the house style.

## Resources

### Contracts and policy

- [Raw node contract](#apa-steel-raw-node-contract-reference)
- [Onboarding egress contract](#apa-steel-onboarding-egress-reference)
- [Privileged access policy](#apa-steel-privileged-access-reference)

## References

<a name="apa-steel-onboarding-egress-reference"></a>Steel, C. (2026a). *Onboarding egress contract* (Version 0.3.0) [Draft]. uc-contracts. https://github.com/steelcj/uc-contracts/blob/main/en/docs/node-onboarding-pipeline/2-ansible-ingress-egress-contract/uc-onboarding-egress-contract.md
[Return to citation](#apa-steel-onboarding-egress-citation)

<a name="apa-steel-privileged-access-reference"></a>Steel, C. (2026b). *Privileged access policy* (Version 0.1.0) [Draft]. uc-contracts. https://github.com/steelcj/uc-contracts/blob/main/en/docs/node-policies/privileged-access/uc-privileged-access-policy.md
[Return to citation](#apa-steel-privileged-access-citation)

<a name="apa-steel-raw-node-contract-reference"></a>Steel, C. (2026c). *Raw node contract* (Version 0.3.1) [Draft]. uc-contracts. https://github.com/steelcj/uc-contracts/blob/main/en/docs/node-onboarding-pipeline/1-raw-node-egress/uc-raw-node-contract.md
[Return to citation](#apa-steel-raw-node-contract-citation)

## Changelog

| Date | Notes |
| --- | --- |
| 2026-11-18 | First version |
