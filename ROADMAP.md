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

### Install the committed outside roles from requirements.yml

`roles/` is for roles developed in uc-controller, and a role developed elsewhere is pinned in `requirements.yml` and installed, as `steelcj.foomuuri` is since 0.2.0. `roles/` still holds sixteen roles committed before that rule: fifteen robertdebock roles, released on Galaxy, and `steelcj.umask`, a fork with no release, pinned to a commit. All sixteen are already pinned in `requirements.yml`. Remove them from `roles/` and install them, and drop their per-role exclusions from `.ansible-lint`, so that `roles/` and its lint settings hold only roles developed here. Not needed for 0.2.0. To settle with it:

- **Where they are installed.** `~/.ansible/roles` is shared with other projects, and already holds other versions of some of these roles: on the controller host on 2026-11-27, `robertdebock.bootstrap` 7.1.7 where 7.3.1 is pinned, `epel` 4.3.1 for 4.1.7, `openssh` 5.1.0 for 5.0.4, `hostname` 3.3.0 for 3.1.11. `ansible-galaxy` leaves a role installed at another version as it is unless given `--force`. A git-ignored directory in the repository, on `roles_path` before `~/.ansible/roles`, would keep uc-controller's pins its own.
- **Checking the versions.** `tests/run_tests.py` offers to install a role it does not find, but takes a role it finds at any version as installed. `tests/test_firewall_fragments.py` checks `steelcj.foomuuri`'s commit. A check of every role's `meta/.galaxy_install_info` against its pin, in `run_tests.py` or a test of its own, replaces both.
- **`steelcj.umask`'s source** is `git@github.com:`, over SSH, so installing it needs a GitHub key. `steelcj.foomuuri` comes over HTTPS.
- **The design document.** Pinned Versions and Bumping a Pinned Version, in `en/docs/uc-controller-v0.1.8.md`, describe the roles as committed, with `git diff roles/` as the review. The next version describes the install and the version check.

## Ansible features

* fireball mode


