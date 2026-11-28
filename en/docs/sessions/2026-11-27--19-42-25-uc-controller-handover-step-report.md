---
title: Handover for uc-controller, Step Report
description: What steps one to five of the handover work changed, the decisions taken on the way, the checks and their results, the throwaway node test of the Foomuuri switch, what in the kickoff and the design documents did not fit, the corrections left outside this repository, and what step six will change in example-org.
version: 0.1.10
status: provisional
date: 2026-11-27
language: en-CA
---

# Handover for uc-controller, Step Report

## Summary

Steps one to five of the handover plan, 0.1.1, are done on the branch `handover`, in the worktree `~/areas/development/uc-controller-handover`, one commit per step. Nothing is pushed, merged or released. Admission names nodes by fully qualified domain name and reads uc-node's `candidates/`. The client inventory template has `intake/` and `candidates/`, and `check_inventory.py` checks both. The firewall is `steelcj.foomuuri` on every stage, and `uc_firewall` is gone. A new guide, Admit and Onboard, covers what follows uc-node's guide 4.

Two things in the kickoff did not fit what the repository does, and Christopher decided both before step one's code was written:

- The rule that names must be fully qualified covers the hosts that came through admission, not every onboarded and normalized host.
- `10_onboard.yml` does not onboard admitted nodes, which the kickoff assumed for step four's test and step six. The work stays with the firewall. The switch was tested on a throwaway node reached as root through Incus, and step six admits `dev.example.org` without onboarding or normalizing it.

The session stops here, before step six.

## Before starting

| Item | Found |
| :-- | :-- |
| uc-controller | `handover` at `5eb51ee`, the plan 0.1.1, the working tree clean. `main` at `8799481` in the main checkout, untouched |
| uc-contracts | The branch `design-after-uc-node-phase-one` is merged into `main`, so the design documents were read from `main` with `git show`: raw node handoff 0.1.2, client inventory layout 0.1.1, node lifecycle overview 0.1.6, safe values and substitutions 0.1.2, the raw node contract 0.3.1 |
| uc-node | `handoff` at `7f3da99`, checked out in its own checkout. Read with `git show`: `templates/candidate.yml.j2`, guide 4, the phase two report, `CLAUDE.md`, and, for the rules uc-controller repeats, `build.yml`'s `client_domain` rule, `labels.yml` and `batches.yml` |
| `steelcj.foomuuri` | `~/.ansible/roles/steelcj.foomuuri/meta/.galaxy_install_info` gives `b62b02b5ee0c7dbf2bf2721aad46cf52ce60ebe3`, the commit `requirements.yml` pins |
| Checks on the starting tree | 96 tests pass. Every playbook passes `--syntax-check`, and the converge boundary check passes. `ansible-lint` already fails, with 186 findings, kept as the baseline below |

Under `~/.secrets/` I opened nothing. Under `~/.private/` I read and wrote nothing. Every run's output was searched for `$6$` and `$y$`, and none held either.

## Decisions taken during the work

| Question | Options | Christopher's answer |
| :-- | :-- | :-- |
| Which hosts must have a fully qualified name in `check_inventory.py`. The kickoff says every admitted, onboarded and normalized host, but `10_onboard.yml` promotes Incus and scanned nodes under names such as `dev-example-org` and `disc-203-0-113-20`, so every onboarding the controller can do today would be refused at commit | The hosts that came through admission, or every host | The hosts that came through admission: every host in `raw/admitted.yml`, and every onboarded or normalized host carrying `raw_node_batch`. This matches the handoff design, which names only admitted hosts |
| Admitted nodes cannot be onboarded: `10_onboard.yml` targets `raw:!admitted`, and the onboard-contract-nodes kickoff of 2026-11-18 was never run | A minimal onboarding path for admitted nodes, the firewall switch only, or stop after step three | The firewall only. Test the switch on a throwaway uc-node Incus node reached as root, with `-l`. Step six admits `dev.example.org` and neither onboards nor normalizes it |

One decision was mine, not in the plan, and was reversed by Christopher after the step stop:

| Decision | Taken | Now |
| :-- | :-- | :-- |
| Where `steelcj.foomuuri` comes from | I vendored it under `roles/` in step four, at the pinned commit `b62b02b5ee0c7dbf2bf2721aad46cf52ce60ebe3`, because the robertdebock roles and `steelcj.umask` are committed there. The copy equalled `git archive b62b02b5…` of `~/areas/development/ansible-role-foomuuri` file for file | Not vendored. uc-controller's `roles/` is for roles developed in uc-controller, and an outside role is pinned in `requirements.yml` and installed with `ansible-galaxy role install -r requirements.yml -p ~/.ansible/roles`, Christopher's rule. Without `-p`, run from the repository, `ansible-galaxy` installs into `roles/`, the first entry on `roles_path`. The copy is removed, and Ansible finds the installed role on `roles_path`. `tests/test_firewall_fragments.py` reads the installed role, is skipped when it is not installed, and fails when it is not at the pinned commit. `tests/run_tests.py` counts a skip as a failure, and offers the operator to install a missing role. The robertdebock roles and `steelcj.umask`, committed under `roles/` before, were moved out by Christopher on `main`, in `eca41e0`, merged into `handover`. Ten of them were installed nowhere, and are now installed at their pins into `~/.ansible/roles`. Three were there at newer versions, and the confirmed ones were installed over them with `--force`: `robertdebock.epel` 4.1.7, `openssh` 5.0.4 and `hostname` 3.1.11. `requirements.yml` pins the last set confirmed to work, by Christopher's version policy in the ROADMAP, which is the set the node test of step four ran. That set has `robertdebock.bootstrap` at 7.1.7, the copy committed under `roles/`, equal file for file to Galaxy's 7.1.7, though the pin said 7.3.1, so the pin is now 7.1.7. `tests/run_tests.py` fails on any role at another version than its pin |

## What changed

| Step | Commit | What |
| :-- | :-- | :-- |
| 1. Admitted names | `7165cb6` | `05_admit.yml` and `tasks/admit_candidate.yml` name a node by its fully qualified domain name: the name a target gives, or `<hostname>.<admit_client_domain>`. A confirmation whose hostname is not the name's first label is refused, naming both, and so is a name that is not fully qualified. The name is used for the admitted entry, the known hosts lookups and entries, `HostKeyAlias`, the report and the identity match. `admit_client_domain` is checked by uc-node's `client_domain` rule. `match_raw_identity.py` takes `--name`, compared whole. `check_inventory.py` refuses a host from admission whose name is not fully qualified. Tests: the domain, one hostname in two domains, bad hostnames, a node admitted under its hostname, and promotion and demotion keeping the name |
| 2. Candidates | `8d4bbc9` | `admit_from_candidates=true` reads every `candidates/*.yml` whose `raw_node_batch` is the batch, through a new `scripts/read_candidates.py`, which uses `BaseLoader` and checks every field before use. A candidate file that is not valid is reported and skipped, and the run exits 2. The label rule refuses a `dev`, `stage` or `prod` candidate before it is contacted unless the run's one onboard stage matches. `admit_candidates` is removed and refused with a message naming its replacement. `admit_client_domain` is required with `admit_addresses` and `admit_from_discovered`, and refused with candidates, as `admit_ssh_port` is. Admission never changes `candidates/`. Tests: two batches, a label mismatch, a hostname mismatch, a wrong fingerprint, broken files, a batch with no candidates, and the refusals before contact |
| 3. Template | `b3aa9c2` | `intake/` and `candidates/` with `.gitkeep` and README lines. `line-length` a warning at 120, with the reason. `new-inventory` runs `git init -b main`, prints the path, that no commit was made, and the next step, uc-node's guide 0. `check_inventory.py` checks each candidate with `read_candidates.py` and treats `intake/` as other client files, without reading either as hosts files. `inventory_hosts.py` skips both |
| 4. Firewall | `24d8b5c` | `steelcj.foomuuri` in all three playbooks, as the ROADMAP's Switch to steelcj.foomuuri says, with the client variables unchanged. The role was vendored under `roles/` here, and is installed from `requirements.yml` since, as the decision above says. `uc_firewall`, its interim vars file and its test are removed. `tests/test_firewall_fragments.py` renders each playbook's call |
| 5. Documents | `626c8f6` | `en/docs/guides/admit-and-onboard.md`, new. `client-inventories.md` 0.2.0, `batch-secrets.md` 0.1.5, the README, the ROADMAP and the CHANGELOG's Unreleased section for 0.2.0. `admitting-a-raw-node.md` says it describes 0.1.x. The usage comments of `00_discover.yml`, `10_onboard.yml`, `scripts/inventory-args` and `require-client-inventory.yml` name `~/.private/uc/example-org/uc-inventory`. `05_admit.yml`'s usage comment changed in step two |
| After the step stop | `b64aac3`, `b0a846f`, `3b62643`, and the commit of this report's 0.1.2 | `.gitignore` leaves out `.ansible/`, ansible-lint's cache, so `git add -A` cannot commit it. `.ansible-lint` leaves out `roles/`. This report: the vendoring decision, how SSH was checked, the node's kind, the lint findings, and the corrections outside this repository. Then `steelcj.foomuuri` taken out of `roles/`, its test reading the installed role |

### Every commit on handover

Twenty commits from `7165cb6` to `d7f5f0f`, oldest first, with the commit of this report's 0.1.8 after them. `bfe3d31` and `eca41e0` are Christopher's, on `main`, and came in with the merge `2494a60`. The other eighteen are on `handover`'s first-parent line. `git log --reverse --format='%h %s' 7165cb6^..handover` lists the same commits, for review against this table.

| Commit | Time | Part | Subject |
| :-- | :-- | :-- | :-- |
| `7165cb6` | 18:59 | Step 1 | Admission names nodes by fully qualified domain name |
| `8d4bbc9` | 19:08 | Step 2 | Admission reads uc-node's candidates/ |
| `b3aa9c2` | 19:17 | Step 3 | Client inventory template: intake/, candidates/, line-length warning |
| `24d8b5c` | 19:41 | Step 4 | Firewall: steelcj.foomuuri on every stage, uc_firewall removed |
| `626c8f6` | 19:46 | Step 5 | Documents for the handover, and the step report |
| `b64aac3` | 19:52 | After the step stop | Ignore ansible-lint's cache, .ansible/ |
| `b0a846f` | 19:53 | After the step stop | ansible-lint: leave out the vendored roles under roles/ |
| `3b62643` | 19:54 | After the step stop | Step report 0.1.1, after review |
| `086c16a` | 20:03 | Step 6 | Admit and Onboard 0.1.1: the hook's warnings, and an empty admitted.yml |
| `141262c` | 20:04 | Step 6 | Run report for step six, on example-org |
| `5a1c0ee` | 20:18 | Roles | steelcj.foomuuri installed from requirements.yml, not vendored |
| `bfe3d31` | 20:23 | From `main`, Christopher's | add uc-repo template |
| `eca41e0` | 20:37 | From `main`, Christopher's | mograted tested roles out of repo and into repo requirements.yml |
| `3a20143` | 20:43 | Roles | run_tests.py fails on skips and offers to install a missing role |
| `2494a60` | 20:43 | Roles, the merge of `main` | Merge main: the committed roles moved out of roles/ into requirements.yml |
| `72897a6` | 20:49 | Roles | After main's move of the roles: pins, version check, lint, ROADMAP |
| `e7e4dc2` | 21:02 | Roles | Roles: pin the confirmed set, and the version policy in the ROADMAP |
| `bc9b0af` | 21:13 | Roles | ROADMAP: what step four exercised, a dated snapshot, the role catalog |
| `e5c0231` | 21:15 | Outside corrections | Step report 0.1.7: the three outside corrections are made |
| `d7f5f0f` | 21:17 | Roles | ROADMAP: where the logs behind the confirmed roles are kept |

### What uc_firewall enforced, and where each rule is now

| uc_firewall | Now |
| :-- | :-- |
| Refused to enable the firewall without a TCP rule for the SSH port in use, `ansible_port` or 22 | Onboard: a pre-task refuses the run unless `firewall_onboard_ssh` is a mapping whose port is `ansible_port` or 22, with a list of sources, before any role runs. The role's own `foomuuri_require_ssh: true` refuses a base fragment without SSH. Normalize and specialize: a pre-task refuses a node without `/etc/foomuuri/10-base.conf`, since their fragments accept no SSH, and each call keeps `10-base` |
| Every rule has a name and a port, protocol `tcp` or `udp` | The role's `assert.yml`, for each entry of `foomuuri_services`: a name, protocol `tcp` or `udp`, state `present` or `absent`, sources a list, no brace |
| Allow rules applied before the default deny, then enabled | Foomuuri loads the merged fragments as one ruleset. The role runs `foomuuri check` on any change before it reloads |
| Removed the conflicting manager, firewalld on Debian | The role removes ufw and firewalld, and masks `nftables.service`, whose stop flushes the ruleset |
| Default policy: deny incoming, allow outgoing | `foomuuri_outgoing: accept`, and Foomuuri's own final `drop log` for incoming |
| One rule per source. `ssh`, `http` and `https` mapped to ports | One Foomuuri rule per service, with all its sources on one `saddr`. Names are Foomuuri macros or ports |
| Additive: a rule left out of the list stayed | Changed on purpose: each fragment is rewritten whole, a stage with no service removes its fragment, and any `.conf` file uc-controller does not write is removed |
| Supported the Debian family with ufw and the Red Hat family with firewalld | The role installs Foomuuri on any family that packages it, EPEL on the Red Hat family, which `10_onboard.yml` already installs first. Only Debian 13 is tested |

## The node test of step four

A throwaway node, built by uc-node's `scripts/build` from `handoff` into a temporary client inventory for `example.net`, with a temporary build and fleet secrets root holding a made-up batch `raw-1970-01-01-01`, through `UC_NODE_SECRETS_DIR` and `UC_SECRETS_DIR`. The node definition's `ssh_sources` and every firewall source in the client values were the controller host's address on the Incus bridge, 10.0.0.1 in the register's terms. The temporary inventory's Incus plugin was filtered to the one instance, and every run was limited to it. The node was an Incus system container, `images:debian/13`, as uc-node's incus platform launches it, without `--vm`. The instance and the temporary files were removed afterwards. Disk space was checked first: 66 GB free on the root filesystem.

Onboarding reaches the node through Incus, so a run would pass whatever the firewall did to port 22. SSH on 22 was therefore checked from the controller host after every stage, besides the ports in the table:

| After | How SSH on 22 was checked |
| :-- | :-- |
| Each `10_onboard.yml` | Its own task "wait for SSH to answer as initial" passed, and one manual login as `initial` with the client's key alone, `ssh -F /dev/null -o BatchMode=yes -o IdentitiesOnly=yes`, printed `initial` |
| Each `20_normalize.yml` and `30_specialize.yml` | The run itself: both reach the node only over SSH as `initial`, the connection onboarding wrote into `onboard/dev/hosts.yml`, and every one of the six passed. Normalize's "confirm reachability", a TCP check of port 22 from the controller host, passed on all four normalize runs |

Not checked: that SSH is refused from a source outside the onboard sources. That needs a second host on another address.

| Step | Result |
| :-- | :-- |
| Build `dev.example.net` | Exit 0, the confirmation passed this worktree's `check_raw_confirmation.py`, the candidate written. Before onboarding the node had uc-node's `10-base.conf` alone, SSH from the bridge address, one table `inet foomuuri`, no ufw or firewalld, Foomuuri 0.27 |
| Admit it from its candidate, with `admit_from_candidates` | `admitted dev.example.net - dev.example.net is new on every count`, exit 0. `raw/admitted.yml` names it `dev.example.net`, `ssh/known_hosts` holds its three keys under that name, the ED25519 key is the console's, `check_inventory.py` passes. A second run: `known` |
| `10_onboard.yml`, through Incus as root | Exit 0. `/etc/foomuuri/` held `10-base.conf` alone, SSH from the onboard sources. The fragment matched uc-node's byte for byte, both being written by the same role from the same values, so it was left as it was. SSH as `initial` with the client's key worked |
| Onboard again with SSH on 2222 | Refused by the new pre-task, exit 2, before any role task ran. Nothing on the node changed |
| Onboard again with a second source and a stray `99-stray.conf` | `10-base.conf` rewritten with both sources, the stray file removed, still one table, SSH as `initial` still working |
| `20_normalize.yml`, `-e target_group=webservers` | Exit 0. `10-base.conf` and `20-normalize.conf`. Port 9100, the normalize service, answered from the controller host. Port 9101, also listening and in no fragment, was dropped. One table, no ufw or firewalld |
| `30_specialize.yml`, `-e specialize_role=webserver` | Exit 0. All three fragments, nginx answering on 80 from the controller host |
| `20_normalize.yml` again | Exit 0, `changed=0`. All three fragments kept, 80 and 9100 answering, 9101 dropped |
| Normalize with an empty `firewall_normalize_services` | `20-normalize.conf` removed, the others kept, 9100 dropped. Normalize again restored it |
| Specialize, then normalize, with `10-base.conf` moved aside | Both refused, exit 2, before any role task. The file was put back |

Two things the test met that the code did not change:

- `-l dev-example-net` alone fails: every playbook's first play runs on `localhost`, to find the client inventory, and a limit without `localhost` skips it, so the next play fails with `'HostVarsVars' has no attribute 'uc_client_stages'`. `-l dev-example-net,localhost` works. The new guide says so, and the ROADMAP has an item for it.
- Once onboarded, a node cannot be onboarded again: its onboard entry makes Ansible reach it over SSH as `initial` without become, and the bootstrap fails. Onboarding is one-shot by design. The test demoted the entry with `demote_node.py` before each repeat.

## Checks

Before each commit I ran `tests/run_tests.py`, `ansible-lint` compared with the baseline, `ansible-playbook --syntax-check` on every playbook and `site.yml`, and `scripts/check_converge_boundary.py`.

| Check | On the final tree |
| :-- | :-- |
| `tests/run_tests.py` | 118 tests, all pass, none skipped. With `steelcj.foomuuri` missing, under an empty home directory, the six firewall tests are skipped and the run exits 1, naming each. Asked, the operator declining or no terminal fails the run with the command to install. Accepting installs the role at the pinned commit into that home's `~/.ansible/roles`, and the firewall tests then pass against it. The 118th, since 0.1.1, checks that the installed `steelcj.foomuuri` is at the pinned commit and not under `roles/` |
| `--syntax-check` | Every playbook and `site.yml` pass |
| Converge boundary | Passes |
| `ansible-lint` | Fails, as on the starting tree. With `roles/` left out, as `.ansible-lint` says, since roles are linted and tested only in work on them, and every outside role installed outside the repository, 167 findings on the starting tree and 170 on the final one. Four are new, all `name[template]` on new tasks in `tasks/admit_candidate.yml`, named as its 23 other tasks are, `"{{ candidate }}: …"`, so the report reads one line per candidate address. One is gone, `var-naming[no-role-prefix]` in `uc_firewall`'s defaults. Before `roles/` was left out the counts were 186 and 195, the difference being nineteen findings in the robertdebock roles committed there and six in the vendored `steelcj.foomuuri`, which is no longer in the repository |
| `check_inventory.py` on an admitted host without `raw_node_batch` | Still refused, as before, by `test_admitted_host_needs_a_batch`. The name rule for onboarded and normalized hosts keys on `raw_node_batch`, which promotion carries from `raw/admitted.yml`, where it is required, so a host loses the rule only if its batch is removed by hand |
| Links and anchors in the changed documents | None broken. The old admission guide's `<a name>` citation anchors were checked by eye |
| `$6$` and `$y$` in every run's output | None |

## What did not fit

None of these stopped a step once the two decisions above were taken. I edited no uc-contracts document and changed nothing in uc-node.

### In the kickoff

- **Onboarding admitted nodes.** Step four's node test and step six assume `10_onboard.yml` onboards an admitted node, but it leaves the `admitted` group out. Suggested: the ROADMAP's new item, Onboard admitted nodes, as its own piece of work with the privileged access policy and `NOPASSWD: ALL`, then the onboard and normalize half of step six.
- **The name rule's scope**, decided above. Suggested: the plan's step one says "a host that came through admission".
- **The step boundary.** Step one needs the name before step two adds candidates, so `admit_client_domain` came in step one, and step two made it apply to the address and scan sources only.
- **"The same rule uc-node's build.yml uses for client_domain".** uc-node's rule is for a domain, at least two labels. An admitted name is a hostname label in front of such a domain, so the rule applied is that, at least three labels. `dev.example` is refused.

### In the design documents

- **Known hosts by address.** The handoff design 0.1.2 says known hosts entries are keyed by address. They are keyed by the name, as the plan decided. For Christopher to correct in uc-contracts, as the plan says.
- **The firewall variables.** The handoff design's fleet inventory section shows `firewall_rules_onboard`, `firewall_rules_normalize` and `firewall_rules_specialize`, and says they are the names the repository uses. The repository uses `firewall_onboard_ssh`, `firewall_normalize_services` and `firewall_specialize_services`, as the client inventory layout 0.1.1 shows. Suggested: the handoff design's examples take those names and shapes.
- **Fields a candidate does not define.** `read_candidates.py` refuses a candidate with a field the handoff design does not list, as well as one missing a field, so a field uc-node adds is a design change first. Suggested: the design says so.
- **A register name for numbered nodes.** The register lists `deb13-vt-0001` and `dev.example.org`, but no fully qualified name for numbered nodes. The admission tests use `deb13-vt-00NN.example.org`, made from the register's host name and domain. Suggested: add `^deb13-vt-0\d{3}\.example\.(org|net|com)$` to the register's hosts.

### For uc-node, not changed

- Guide 4's Admit the node section turns candidates into `admit_candidates`, which uc-controller 0.2.0 refuses, with a message naming `admit_from_candidates`. It should point at uc-controller's Admit and Onboard guide.

### In uc-controller, left for later

- **Removing an admitted host.** The guide removes a host from `raw/admitted.yml` with a short Python snippet, and its known hosts block with `sed`, as `match_raw_identity.py`'s advice already says to do by hand, although the file's header says not to edit it by hand. Suggested: a script, such as `scripts/forget_node.py`, that removes both and keeps the header.
- **Nodes onboarded with ufw.** Normalize and specialize now refuse a node without `10-base.conf`, so a node onboarded before 0.2.0, with ufw, is refused rather than left with two firewall managers. Onboarding it again means demoting it first. The plan puts these nodes out of scope.
- **The design document.** `en/docs/uc-controller-v0.1.8.md` still describes `admit_candidates`, admission by hostname and `uc_firewall`. It is versioned, so it was left as it is. Suggested: a 0.1.9 with this work.
- **The older walkthroughs** still show `uc_firewall` output, and are already in the ROADMAP's item for them.

## Corrections outside this repository

The two in uc-contracts are made, in its handoff design 0.1.3, on the branch `handover` in the worktree `~/areas/development/uc-contracts-handover`, commit `a94e232`, not pushed. 0.1.2 is kept, as earlier versions are. The one in uc-node is made in guide 4 0.1.4, on the branch `handoff-guide-4-admission`, from `handoff`, in the worktree `~/areas/development/uc-node-handoff-guide-4`, commit `dd59019`, not pushed. All three:

| Where | Correction |
| :-- | :-- |
| uc-node, `en/docs/guides/4-hand-over-to-the-fleet.md`, Admit the node | Replace the conversion to `admit_candidates`, which uc-controller 0.2.0 refuses, with a pointer to uc-controller's Admit and Onboard guide and `admit_from_candidates=true` |
| uc-contracts, `en/docs/design/raw-node-handoff-inventories-and-secrets-v0.1.2.md`, line 207 | "Known hosts entries are keyed by address, so the name does not change them" becomes: entries are keyed by the admitted name, through `HostKeyAlias`, so they move with the name |
| uc-contracts, the same document, the fleet inventory examples | `firewall_rules_onboard`, `firewall_rules_normalize` and `firewall_rules_specialize` become `firewall_onboard_ssh`, `firewall_normalize_services` and `firewall_specialize_services`, in the shapes the client inventory template uses |

## What step six will change in example-org

Admission changes nothing on a node, so step six changes the client inventory only. `dev-example-org` stays as it is, running, with uc-node's firewall.

1. Remove `dev` from `raw/admitted.yml` and its block from `ssh/known_hosts`, with the commands in Admit and Onboard, Move a node admitted under its hostname, and commit, with a message saying it is a test of that guide.
2. Admit `dev.example.org` with `admit_from_candidates=true`, `admit_batch_id=raw-2026-11-27-01` and `raw onboard/dev`. Check it is admitted as `dev.example.org`, with its three host keys under that name and the ED25519 key the console shows, and commit `raw/admitted.yml` and `ssh/known_hosts` as the guide says. The pre-commit hook will now also check the committed candidate and the name.
3. Not done, by the decision above: onboarding with `10_onboard.yml` and normalizing with `20_normalize.yml`, and the firewall checks on the node after each. `dev.example.org` stays admitted.
4. Fix every guide that did not match what happened, one commit each, and write the run report.

## What remains before 0.2.0

Step six ran as narrowed above, its run report is `141262c`, and the three corrections outside this repository are made. In order:

1. **uc-contracts: done.** `handover` fast-forwarded into `main`, to `a94e232`, the handoff design 0.1.3, with Christopher's go-ahead. Not pushed.
2. **uc-node: done.** `handoff` fast-forwarded to `dd59019`, guide 4 0.1.4, with Christopher's go-ahead. Guide 4 exists only on `handoff`, not on `main`, so that is the one place its old text was. `handoff` is one commit ahead of `origin/handoff`, not pushed. It does not go into uc-node's `main` for this release: it is 31 commits ahead of `main`, unreviewed, and its phase two report leaves open the review, whether the contract says how `sudo` is measured, cutting 0.3.0 and rebuilding `dev.example.org` after it, an ssh platform build, and retiring example-org's test batch and instance. `handoff` reaches `main` through uc-node's own review and its 0.3.0.
3. **uc-controller:** Christopher reviews `handover` against the table of every commit above, with `git log --reverse 7165cb6^..handover`, then merges it into `main` and tags 0.2.0.
4. **After 0.2.0:** onboarding admitted nodes, through the onboard-contract-nodes kickoff, so `dev.example.org` can be onboarded. Then the ROADMAP's Test the latest versions run, the role catalog in uc-contracts, and uc-node's own review and 0.3.0.

The instance `dev-example-org` is stopped, with `incus stop`, not deleted, in case uc-node's rebuild of `dev.example.org` needs it. Deleting it is left to uc-node's cleanup. The worktrees `~/areas/development/uc-contracts-handover` and `~/areas/development/uc-node-handoff-guide-4` are removed, and uc-contracts' branch `handover` deleted with `git branch -d`.

## Changelog

| Version | Date | Change |
| :-- | :-- | :-- |
| 0.1.10 | 2026-11-27 | `dev-example-org` stopped, not deleted. The two outside worktrees removed, and uc-contracts' `handover` branch deleted |
| 0.1.9 | 2026-11-27 | Merge order changed: uc-node's `handoff` stays off `main` for this release, and takes guide 4 by a fast-forward. uc-contracts' `handover` fast-forwarded into `main`, and uc-node's `handoff` to `dd59019`, with Christopher's go-ahead. uc-controller's merge and the 0.2.0 tag wait on his review |
| 0.1.8 | 2026-11-27 | Every commit on `handover`, in a table for the review. What remains is in merge order: uc-contracts, then uc-node with `handoff`, then uc-controller and the 0.2.0 tag, then onboarding admitted nodes, the latest-versions run and the role catalog. What is still open on uc-node's `handoff` |
| 0.1.7 | 2026-11-27 | The uc-node correction made, in guide 4 0.1.4. No correction outside this repository is open |
| 0.1.6 | 2026-11-27 | The two uc-contracts corrections made, in the handoff design 0.1.3. The ROADMAP's confirmed roles carry their evidence from step four's full output: thirteen confirmed, and `robertdebock.epel`, `ntp`, `selinux` and `auditd` pinned, not exercised, every task skipped on a Debian container |
| 0.1.5 | 2026-11-27 | The four re-pins of 0.1.4 undone: `requirements.yml` pins the confirmed set, by the ROADMAP's version policy, with `robertdebock.bootstrap` at 7.1.7, the version step four ran. `epel`, `openssh` and `hostname` reinstalled at their pins with `--force` |
| 0.1.4 | 2026-11-27 | `main`'s move of every outside role out of `roles/` merged. The ten roles installed nowhere installed at their pins, four pins moved to the versions installed. `tests/run_tests.py` checks every role's version. `.ansible-lint` leaves out `roles/` as a whole, since roles are linted and tested only in work on them. Syntax-check, the boundary check, 118 tests and the 170 lint findings unchanged |
| 0.1.3 | 2026-11-27 | The install command takes `-p ~/.ansible/roles`, since without it `ansible-galaxy` installs into `roles/`. `tests/run_tests.py` fails on a skip and offers to install a missing role, both checked. The robertdebock roles and `steelcj.umask` are a ROADMAP item, Install the committed outside roles from requirements.yml |
| 0.1.2 | 2026-11-27 | `steelcj.foomuuri` is not vendored: the decision row records Christopher's rule that `roles/` is for roles developed in uc-controller, and step four's row says the role is installed from `requirements.yml`. `.ansible-lint` lists the committed outside roles by name, and the comments in `ansible.cfg` and `requirements.yml` and the README say what `roles/` is for. 118 tests, and the same 170 lint findings |
| 0.1.1 | 2026-11-27 | After review: the vendoring of `steelcj.foomuuri` as a decision, with its check against upstream; how SSH on 22 was checked after each stage, and that the node was a container; the lint counts with `roles/` left out, and the finding that went with `uc_firewall` named correctly; the `raw_node_batch` refusal; the corrections outside this repository; the commits after the stop |
| 0.1.0 | 2026-11-27 | First version |
