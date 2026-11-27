---
title: Handover for uc-controller, Plan and Kickoff Prompt
description: The plan for bringing uc-controller into line with uc-node's handover, so admission reads candidates and names nodes by fully qualified domain name, and onboarding manages the Foomuuri firewall uc-node leaves, and the Claude Code kickoff prompt that carries it out.
version: 0.1.1
status: provisional
date: 2026-11-27
language: en-CA
---

# Handover for uc-controller, Plan and Kickoff Prompt

## Where things stand

uc-node's handoff work is done on its branch `handoff`, through phase two. A build ends at connected securely: the confirmation on the node, the candidate in the client inventory's `candidates/`, and a rejection in the client log when it cannot secure the node. In phase two, uc-controller admitted `dev.example.org` from a candidate turned by hand into `admit_candidates`, and everything agreed: three host keys, the machine ID and the become with the batch password.

The run also showed where uc-controller falls short:

| Area | State at uc-controller 0.1.7, `main` at `8799481` |
| :-- | :-- |
| Admitted names | `05_admit.yml` and `tasks/admit_candidate.yml` name a node by the confirmation's hostname, so `dev.example.org` was admitted as `dev`. Known hosts entries follow, through `HostKeyAlias={{ inventory_hostname }}` |
| Candidates | Admission takes `admit_candidates`, a list of `{address, fingerprint}` given with `-e @<file>`, `admit_addresses`, or `admit_from_discovered`. It does not read `candidates/` |
| Firewall | `10_onboard.yml`, `20_normalize.yml` and `30_specialize.yml` apply `shared/roles/uc_firewall`, which on Debian installs and enables ufw. `steelcj.foomuuri` is pinned in `requirements.yml`, at the same commit as uc-node, and called nowhere. A node uc-node built keeps Foomuuri, so onboarding it would leave two firewall managers, each with its own nftables table: SSH would pass both, and any service normalize opens in ufw would still be dropped by Foomuuri's `10-base` |
| Client inventory template | No `intake/` or `candidates/`. `line-length` is an error at 120, which a key line with a client's comment passes. `scripts/new-inventory` makes a `master` branch, makes no first commit, and prints nothing on success |
| `check_inventory.py` | Passes a candidate only because it reads it as a hosts file with a group and no variables |
| Documents | uc-controller has no guide for admission or onboarding: uc-node's guide 4 covers admission from its side. `en/docs/guides/batch-secrets.md` says uc-node does not read `~/.secrets/uc/build/` yet, and its recipe uses `raw-1970-01-01-01`, the register's reserved name. `05_admit.yml`'s usage comment shows `~/uc-inventories/example.org` |

The ROADMAP lists each of these on the branch `design-after-uc-node-phase-one`, under Take uc-node's handover as it is now and Switch to steelcj.foomuuri. This plan is written on a branch from there, `handover`, so the ROADMAP items it does are removed in the same branch. The work is done in the worktree `~/areas/development/uc-controller-handover`, on `handover`, so the main checkout stays on `main`.

## What uc-controller comes into line with

The design documents in uc-contracts, on the branch `design-after-uc-node-phase-one` until Christopher merges it: raw node handoff 0.1.2, client inventory layout 0.1.1, node lifecycle overview 0.1.6, the safe values register 0.1.2 and the raw node contract 0.3.1. They are evolving designs, not rules: where building shows that one does not fit, the design changes, with Christopher, rather than the code bending to it or the session editing the document.

uc-node's side is fixed for this work, at `handoff`: the candidate's fields, `confirmation.yml`, the rejection entry, and the bootstrap fragment `10-base`.

## Decisions

Each is taken as recommended in the kickoff prompt below. Change any of them before starting, and the prompt with them.

| Decision | Recommended | Why |
| :-- | :-- | :-- |
| The admitted name | The fully qualified domain name, from the candidate's top-level key. Admission checks that the confirmation's hostname is the name's first label, and refuses the candidate otherwise | Christopher's decision after uc-node's phase two, recorded in the handoff design 0.1.2. The node keeps one name from `intake/` to `normalized/`, and two domains in one client inventory cannot collide |
| Known hosts entries | Keyed by the admitted name, through `HostKeyAlias`, as now. They move with the name: a node admitted again as `dev.example.org` has its keys under `dev.example.org`, and its old lines under `dev` are removed by hand | Christopher's decision, and the ROADMAP's. A key held by name stays with the node when its address changes, and addresses such as those in 203.0.113.0/24 are reused between test nodes. The handoff design 0.1.2 says known hosts are keyed by address, so the name does not change them: that sentence is for Christopher to correct in uc-contracts, and the session does not stop on it |
| The name when there is no candidate | `admit_addresses` and `admit_from_discovered` stay, for nodes uc-node did not build, and require `admit_client_domain`. The name is `<hostname>.<admit_client_domain>` | The console path stays in the handoff design. Without a candidate the domain has to come from somewhere, and one extra variable says it plainly. A client inventory may hold more than one domain, so it is not a fixed fact of the inventory |
| How admission takes candidates | A fourth source, `admit_from_candidates=true`, reads every `candidates/*.yml` whose `raw_node_batch` is `admit_batch_id`. The candidate's `fingerprint` is the console fingerprint for its address. `admit_candidates` is removed | Exactly one source per run, as now. Reading by batch matches the batch password admission needs. uc-node read the fingerprint through `incus exec` or the pinned first contact, which the handoff design accepts in place of the console |
| A candidate's label and the run's environment | A `raw` candidate may be admitted with any onboard stage. A `dev`, `stage` or `prod` candidate only with the onboard stage of the same name, or it is refused | The handoff design refuses a `prod` candidate admitted with `onboard/dev`. `raw` means no destination yet, so any is fine |
| Existing admitted nodes named by hostname | No migration. example-org's `dev` is removed from `raw/admitted.yml` and `ssh/known_hosts` by hand, as the guide will say, and admitted again from its candidate | Nothing else is admitted under a hostname: example-org is the only client inventory, and its node is a test node. As with uc-node 0.3.0, there is no upgrade path to keep |
| The firewall | `steelcj.foomuuri` as the ROADMAP's Switch to steelcj.foomuuri says: onboard writes `10-base`, replacing uc-node's, normalize `20-normalize`, specialize `30-specialize`, each keeping the others with `foomuuri_keep_fragments`, and a stage with no services removes its fragment. `uc_firewall`, `uc_firewall_interim.yml` and its test go | The ROADMAP's approach, unchanged. The client inventory's variables keep their names and shape |
| Nodes onboarded with ufw | Out of scope. The role removes ufw and firewalld on the nodes it manages, which the session confirms at the pin | Every node onboarded so far was a test node. The one to onboard now, `dev.example.org`, has Foomuuri only |
| `check_inventory.py` and candidates | It checks each `candidates/*.yml` against the handoff design's candidate fields and types, and each `intake/*.yml` for a hash, a secret or logic, as it does elsewhere | The pre-commit hook then catches a bad candidate before admission reads it |
| The template's `line-length` | `level: warning`, at 120 | No limit fits every public key line: RSA keys run to several hundred characters. The hook shows the warning and does not stop on it. example-org's inventory does this already |
| `scripts/new-inventory` | `git init -b main`, prints what it made and the next steps, and makes no commit | The first commit comes once the `CHANGE-ME` values are filled in, as uc-node's guide 0 says. `main` matches every other repository |
| The checker's unnamed findings | Deferred | `check_raw_confirmation.py` reports `Versioning`, `Host keys`, `Firewall` and `Firewall manager`, which are not clause identifiers. Giving them identifiers is a contract change, for Christopher, when a rejection needs them |
| `NOPASSWD: ALL` during onboarding | Deferred, as in the ROADMAP | Its own piece of work, with the privileged access policy |
| The release | 0.2.0 | Admission's sources and names change, and the firewall role changes on every stage |

## The plan

The kickoff carries out the steps, then stops before the run on example-org. A short "go" from Christopher starts the run, since it changes a node and a client inventory he keeps.

1. Admitted names. Admission names by fully qualified domain name, checks the hostname against the first label, and keeps the name through the identity match, known hosts, promotion and demotion. `check_inventory.py` refuses an admitted host whose name is not fully qualified.
2. Admission reads `candidates/`. `admit_from_candidates`, the label rule, and `admit_client_domain` for the other sources. `admit_candidates` goes.
3. The template, `new-inventory` and `check_inventory.py`. `intake/` and `candidates/`, the warning, `main`, the candidate and intake checks.
4. The firewall. `steelcj.foomuuri` on every stage, `uc_firewall` removed.
5. Documents. A new guide for admission and onboarding, `client-inventories.md`, the batch-secrets guide, `05_admit.yml`'s usage comment, the README, the ROADMAP and the CHANGELOG.
6. The run on example-org, after Christopher's go. Move `dev` to `dev.example.org` by admitting it again from its candidate, onboard it with `onboard/dev`, normalize it with `normalized/dev`, and check the firewall on the node.

## Kickoff prompt

```text
Read en/docs/sessions/2026-11-27--17-58-28-uc-controller-handover-plan-and-kickoff.md first: it holds the reasons and decisions behind this prompt. Then read, in uc-contracts, on the branch design-after-uc-node-phase-one if it is not merged, en/docs/design/raw-node-handoff-inventories-and-secrets-v0.1.2.md, client-inventory-layout-v0.1.1.md, node-lifecycle-overview-v0.1.6.md and safe-values-and-substitutions-v0.1.2.md, and en/docs/node-onboarding-pipeline/1-raw-node-egress/uc-raw-node-contract.md. In uc-node, on the branch handoff, read templates/candidate.yml.j2, en/docs/guides/4-hand-over-to-the-fleet.md and en/docs/sessions/2026-11-27--17-31-42-uc-node-handoff-phase-two-report.md. Read steelcj.foomuuri at the commit requirements.yml pins, in ~/.ansible/roles/steelcj.foomuuri, and check that the installed copy is that commit: it has no .git, so compare the version in its meta/.galaxy_install_info.

Work in the worktree ~/areas/development/uc-controller-handover, on the branch handover, which holds this plan, and commit after each step. Never switch branches in the main checkout, ~/areas/development/uc-controller, which stays on main. Stop after step 5 and write the step report. Step 6 starts only when Christopher says go.

Ground rules for the whole piece of work:
- The design documents in uc-contracts are evolving designs, not rules. Where one does not fit what you find, or a step cannot follow it without a choice the documents do not make, stop and ask, saying what does not fit and the options you see. Never edit a uc-contracts document, and change nothing in uc-node.
- Never read anything under ~/.secrets/, and never print a secret or a hash. Admission reads the batch through uc_secret, which is allowed. Search every run's output for $6$ and $y$.
- Under ~/.private/, read and write only ~/.private/uc/example-org/, and only in step 6. Tests make their own client inventory and secrets root in a temporary directory, with register values.
- Every example, test value and document uses the safe values register: example.org, example-org, raw-1970-01-01-NN in documents and tests only, 203.0.113.0/24 and 198.51.100.0/24, the register's fingerprints, operator and /home/operator.
- Follow uc-node's CLAUDE.md known issues for every SSH connection: one try per login, no wait_for_connection against a host that may refuse the login, and IdentitiesOnly.
- Run tests/run_tests.py, ansible-lint and the syntax check of every playbook before each commit. Where a step changes what a playbook does on a node, run it against a throwaway node built by uc-node's scripts/build into a temporary client inventory, and remove the node afterwards.
- Never push, never merge, never cut a release.

1. Admitted names.
   - tasks/admit_candidate.yml names the node by its fully qualified domain name: the candidate's top-level key when the source is candidates, otherwise <hostname>.<admit_client_domain>. Refuse a candidate whose confirmation hostname is not the name's first label, naming both. Use the name for the admitted entry, the known hosts lookups and entries, HostKeyAlias, the run's report, and match_raw_identity.py. Known hosts stay keyed by the name, as the plan's decisions say, although the handoff design 0.1.2 says by address: do not stop on that.
   - Check promote_node.py and demote_node.py carry the name unchanged, and test it.
   - check_inventory.py refuses an admitted, onboarded or normalized host whose name is not a fully qualified domain name, by the same rule uc-node's build.yml uses for client_domain.
   - Update the tests and fixtures that name a host by its hostname alone.

2. Admission reads candidates/.
   - Add admit_from_candidates=true: read every <client root>/candidates/*.yml whose raw_node_batch equals admit_batch_id, with yaml BaseLoader as the contract asks of confirmations, checking each against the handoff design's candidate fields before use. Each gives the name, address, ssh_port and the console fingerprint. A candidate file that does not parse or lacks a field is reported and skipped, and the run exits 2.
   - Refuse a candidate whose node_label is dev, stage or prod when the run's onboard stage is not onboard/<that label>. Accept raw with any.
   - Remove admit_candidates. admit_addresses and admit_from_discovered require admit_client_domain, checked as a domain.
   - Keep exactly one source per run, and keep admission from changing candidates/.
   - Tests: candidates for two batches, a label mismatch, a hostname mismatch, a broken candidate file, and a run with no candidates for the batch.

3. The template, new-inventory and check_inventory.py.
   - inventory-template/ gains intake/ and candidates/, each with a .gitkeep, and a line for each in its README saying uc-node writes them.
   - inventory-template/.yamllint sets line-length level: warning at 120, with a comment saying why.
   - scripts/new-inventory runs git init -b main, prints the path it made, that no commit was made, and the next step, uc-node's guide 0, and still refuses a path that exists and is not empty.
   - check_inventory.py checks each candidates/*.yml against the candidate's fields and types, and treats intake/*.yml as it treats other client files: no hash, no vault header, no private key, no lookup.
   - Tests for each.

4. The firewall.
   - Replace uc_firewall in 10_onboard.yml, 20_normalize.yml and 30_specialize.yml with steelcj.foomuuri, as the ROADMAP's Switch to steelcj.foomuuri says, keeping the client inventory's variable names and shapes. Remove shared/roles/uc_firewall, shared/vars/uc_firewall_interim.yml and tests/test_uc_firewall_interim.py.
   - Before removing it, list every rule uc_firewall enforces, such as refusing a run with no SSH rule, and show where each is kept.
   - Test on a throwaway node built by uc-node: after onboard, /etc/foomuuri/ holds only 10-base.conf, uc-controller's, with SSH on 22 from the onboard sources; after normalize, 10-base and 20-normalize, and a normalize service reachable from the controller host; after rerunning normalize after specialize, 30-specialize is still there. One nftables table, inet foomuuri. ufw and firewalld absent.

5. Documents.
   - A new guide, en/docs/guides/admit-and-onboard.md, for the steps after uc-node's guide 4 hands a node over: admitting from candidates, the name, admit_client_domain for the other sources, moving a node admitted under its hostname by removing its entry and its known hosts lines and admitting it again from its candidate, then onboarding and normalizing it, with what the firewall holds after each. uc-controller has no such guide yet. Link it from the README's guides and from client-inventories.md.
   - en/docs/guides/client-inventories.md: intake/ and candidates/, what new-inventory now prints, the first commit on main, and the line-length warning.
   - en/docs/guides/batch-secrets.md: point uc-node's part at uc-node's guide 0 and scripts/new-batch, and use raw-YYYY-MM-DD-NN in commands, with a line saying 1970 dates are for documents and tests.
   - 05_admit.yml's usage comment: ~/.private/uc/example-org/uc-inventory, admit_from_candidates and raw-YYYY-MM-DD-NN.
   - README, ROADMAP (remove what this work did) and CHANGELOG, an Unreleased section for 0.2.0.
   - Write the step report, en/docs/sessions/<timestamp>-uc-controller-handover-step-report.md, by the sessions README: what changed, the checks and their results, anything in this prompt or the design documents that did not fit, with the changes you would suggest, and what step 6 will change in example-org. Then stop.

6. The run on example-org, after Christopher says go.
   - Remove dev from raw/admitted.yml and its lines from ssh/known_hosts, as admit-and-onboard.md says, and commit with a message saying it is a test of that guide.
   - Admit dev.example.org with admit_from_candidates, admit_batch_id raw-2026-11-27-01 and onboard/dev. Check it is admitted as dev.example.org, with its host keys under that name. Commit as the guide says.
   - Onboard it with 10_onboard.yml and onboard/dev, then normalize it with 20_normalize.yml and normalized/dev. After each, check the firewall on the node as in step 4, and that SSH as initial still works with the client's key. Commit what each writes.
   - Fix every guide that did not match what happened, one commit each, and write the run report, en/docs/sessions/<timestamp>-uc-controller-handover-run-report.md: the run step by step, the firewall on the node after each stage, every guide change, anything that did not fit, what is left in example-org, and what remains before release 0.2.0.
```

## Changelog

| Version | Date | Change |
| :-- | :-- | :-- |
| 0.1.0 | 2026-11-27 | First version |
| 0.1.1 | 2026-11-27 | Known hosts stay keyed by the admitted name, against the handoff design 0.1.2's sentence that they are keyed by address. The work is done in a worktree beside the main checkout. The pinned role is checked through its install info |
