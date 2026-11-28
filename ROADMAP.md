# uc-controller ROADMAP.md

## Documentation

### Development Documentation

### Bring the older walkthroughs up to the client inventories

These documents still give `-i inventories/...` commands, the vault, or paths in the repository, from before the inventory split: `onboarding-a-raw-dev-node.md`, `onboarding/onboarding-a-new-incus-node-deb13.md` and its `-v0.1.2` copy, `fragment-001.md`, `bootstrapping an incus container.md`, `Preparing incus containers and vm's for ansible runs.md`, `incus-container-and-vm-discovery.md`, `incus--instance-naming-v0.1.3.md` and `uc-controller-adding-support-for-multi-source-raw-inventory-and-optimising-for-speed-v0.1.0.md`, all under `en/docs/`. Update each to `scripts/inventory-args` and a client inventory, or mark it as a record of its time. `guides/ssh/plain-vault-batch-passwords.md` is misnamed for what it holds, where documents and the Diceware kit belong, and names a private address and the controller's key file.

## Controller Features

### "dummy inventory"

At some point in time a dummy inventory can be created and/or generated for testing controller OOB using some standard containers or vm's 


## Secrets

### Change the test values that were public

The two test batches made before the batch files, and whatever `vaults/raw_secrets.yml`, `vaults/onboard_secrets.yml` and `vaults/normalized_secrets.yml` held, were committed to this public repository, encrypted or not. They were for testing only. Change them regardless, and build no node with them again.

### Recreate the repository

Once the inventory split is merged and works, recreate the GitHub repository with no history: delete it on GitHub, create it empty, delete `.git` locally, then `git init`, commit the current files, which are cleaned first, and push. The old tags and releases go with the old repository. The plan's "Later: recreating the repository" section, in `en/docs/sessions/2026-11-24--22-46-54-uc-controller-inventory-split-plan-and-kickoff.md`, gives the steps.

### An OpenBao backend for uc_secret

`shared/plugins/lookup/uc_secret.py` reads `~/.secrets/uc/fleet/<path>.yml`. Replace its file read with OpenBao, at `batches/<batch>` in the client namespace's `fleet` mount, which the file path maps onto, as `en/docs/design/raw-node-handoff-inventories-and-secrets-v0.1.0.md` in uc-contracts describes. Playbooks and inventories do not change.

### NOPASSWD: ALL during onboarding

`inventory-defaults/onboard/group_vars/all.yml` gives `initial` `sudo_options: "ALL=(ALL) NOPASSWD: ALL"`. That conflicts with the privileged access policy. The inventory split moved it unchanged. The onboarding of contract nodes, which gives each node its own password (OE-ACC-03), is a natural place to settle it.

## Onboarding

### Onboard admitted nodes

`10_onboard.yml` targets `raw:!admitted`: it onboards nodes it reaches as root, through Incus or a subnet scan, and leaves out nodes admitted under the raw node contract, which are reached as `initial` with sudo asking for the batch password. The onboard-contract-nodes kickoff, `en/docs/sessions/2026-11-18--17-38-56-kickoff-onboard-contract-nodes.md`, was written for this and never run. Onboarding an admitted node runs over the admitted group's strict SSH connection, becomes root with the batch password, skips the Python bootstrap the contract does not need, and keeps strict host key checking when it promotes the node. It should not use `wait_for_connection` against a node that may refuse the login, which OpenSSH 10 penalises. Until it is done, `dev.example.org` in example-org stays admitted, and the firewall switch has been tried on nodes reached as root only.

### Limits that leave out localhost

Every playbook starts with a play on `localhost` that finds the client inventory, so `-l <host>` alone skips it, and the next play fails with `'HostVarsVars' has no attribute 'uc_client_stages'`. `-l <host>,localhost` works, and the guides say so. Either have the first play say it was left out, or find the client inventory without a play on `localhost`.

## Inventories

### Move towards the proposed client inventory layout

The client inventory's layout is evolving. `en/docs/design/client-inventory-layout-v0.1.1.md` in uc-contracts sets today's tree beside the one the design is heading towards. uc-node's `intake/` and `candidates/` are in the template since 0.2.0, and the guides use the client's folder, `~/.private/uc/<client>/uc-inventory`. Still to come: a `specialized/<env>/` stage with `roles.yml` that takes the role files out of `normalized/`, `secrets.yml`, and admission writing its rejections to the client log beside the inventory. Try each change when its work comes due, and update `inventory-template/` and `en/docs/guides/client-inventories.md` with it.

### Admission as a reviewed event

Once a second person admits nodes, make admission a change that is reviewed: admit on a branch of the client inventory repository, and merge the branch to admit, so that someone other than the admitter sees each new node and each newly trusted host key.

### Name the checker's findings by clause

`scripts/check_raw_confirmation.py` reports some findings under names that are not clause identifiers, such as `Versioning`, `Host keys`, `Firewall` and `Firewall manager`, so a rejection cannot list them in `clauses`. Give those checks identifiers when the contract does. That is a contract change, in uc-contracts.

### discover_subnet in the client inventory

`ingress/playbooks/00_discover.yml` defaults `discover_subnet` to an address range in code. Which subnet to scan is a fact about a client, so move it to the client inventory, in `raw/group_vars/all.yml` or the template's place for it, and give the code no default: a run without it refuses, rather than scanning a range that belongs to nobody in particular.

## Firewall

### Change the SSH port at onboard

Dev and stage both stay on port 22 for now. `steelcj.foomuuri` allows only `foomuuri_ssh_port`, and sshd moves later in the same run, so changing the port at onboard would lock the controller out: the lockout uc-node's ROADMAP describes under "Change the SSH port after first contact". Settle it together with uc-node.

### Narrow SSH on stage

`onboard/stage` allows SSH from `0.0.0.0/0`, any IPv4 address, which is as open as dev for IPv4. Narrow the IPv4 sources for SSH on stage.

## Roles

### Version policy

We aim to run the latest release of every role. requirements.yml always pins the last set confirmed to work, and each bump to the latest is tested on a branch before its pin changes.

### Confirmed working

Confirmed on 2026-11-27 by the handover step 4 node test (throwaway uc-node node, Incus system container, images:debian/13) through onboard, normalize and specialize. The versions are those of the copies then committed under `roles/`, read from each copy's `meta/.galaxy_install_info` at `24d8b5c`. `robertdebock.bootstrap` was 7.1.7, though requirements.yml pinned 7.3.1, and requirements.yml now pins 7.1.7: its files equal Galaxy's 7.1.7. `steelcj.umask`'s copy said `master`, and its files equal the pinned commit.

| Role | Version |
|---|---|
| robertdebock.bootstrap | 7.1.7 |
| steelcj.umask | 42496062 |
| robertdebock.epel | 4.1.7 |
| robertdebock.update | 3.1.10 |
| robertdebock.locale | 3.3.12 |
| robertdebock.auto_update | 3.1.9 |
| robertdebock.cron | 2.2.8 |
| robertdebock.ntp | 3.1.7 |
| robertdebock.openssh | 5.0.4 |
| robertdebock.fail2ban | 5.0.7 |
| steelcj.foomuuri | b62b02b5 |
| robertdebock.users | 6.1.8 |
| robertdebock.selinux | 3.1.12 |
| robertdebock.auditd | 3.2.13 |
| robertdebock.sysctl | 2.1.10 |
| robertdebock.hostname | 3.1.11 |
| robertdebock.rsyslog | 5.0.1 |

### Test the latest versions

On the next run, on its own branch:

1. Look up the latest release of each pinned role. For the robertdebock roles, Robert's chart, <https://robertdebock.nl/ansible.html>, shows each role's Molecule and GitLab CI state and a badge counting commits since its latest release, but not the version number. Take the version from the role's Galaxy page or its GitHub releases. On 2026-11-27, Galaxy and GitHub agreed, and every robertdebock role had a newer release than its confirmed pin, all released between 2026-11-20 and 2026-11-21:

   | Role | Confirmed | Latest on 2026-11-27 |
   |---|---|---|
   | robertdebock.auditd | 3.2.13 | 3.3.1 |
   | robertdebock.auto_update | 3.1.9 | 3.2.0 |
   | robertdebock.bootstrap | 7.1.7 | 7.3.1 |
   | robertdebock.cron | 2.2.8 | 2.3.0 |
   | robertdebock.epel | 4.1.7 | 4.3.1 |
   | robertdebock.fail2ban | 5.0.7 | 5.1.0 |
   | robertdebock.hostname | 3.1.11 | 3.3.0 |
   | robertdebock.locale | 3.3.12 | 3.4.1 |
   | robertdebock.ntp | 3.1.7 | 3.3.0 |
   | robertdebock.openssh | 5.0.4 | 5.1.0 |
   | robertdebock.rsyslog | 5.0.1 | 5.2.1 |
   | robertdebock.selinux | 3.1.12 | 3.2.0 |
   | robertdebock.sysctl | 2.1.10 | 2.2.0 |
   | robertdebock.update | 3.1.10 | 3.3.1 |
   | robertdebock.users | 6.1.8 | 6.2.1 |

   `steelcj.umask` and `steelcj.foomuuri` are pinned to commits: compare each with its repository's head.
2. Pin the latest versions and install them with `ansible-galaxy role install -r requirements.yml -p ~/.ansible/roles --force`.
3. Run onboard, normalize and specialize on a throwaway uc-node node, using the test steps from the handover step report.
4. If everything passes, keep the new pins and replace the confirmed table with the new set and date. If a role fails, put back its confirmed version, record the failure here, and fix it in that role's repository or upstream.

### Revisit the robertdebock roles

Fifteen roles come from robertdebock, released on Galaxy and developed outside uc-controller. When one falls behind current Ansible practice, such as a deprecated module or option, a pattern `ansible-lint` or `ansible-core` warns about, missing argument specs, or a Debian or Rocky release it does not support, decide for that role: move to a newer release, contribute the fix upstream, fork it, as `steelcj.umask` forks a role, or replace it with a role developed in `roles/` and, once tested, released and pinned like the others. Look again at each such role whenever its pin is bumped.

### Smaller points

- `steelcj.umask`'s source is `git@github.com:`, over SSH, so installing it needs a GitHub key. `steelcj.foomuuri` comes over HTTPS.
- The design document's Pinned Versions and Bumping a Pinned Version, in `en/docs/uc-controller-v0.1.8.md`, describe the roles as committed under `roles/`, with `git diff roles/` as the review. The next version describes the install into `~/.ansible/roles` and `tests/run_tests.py`'s check of every pin.

## Ansible features

* fireball mode


