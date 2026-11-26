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

## Inventories

### Admission as a reviewed event

Once a second person admits nodes, make admission a change that is reviewed: admit on a branch of the client inventory repository, and merge the branch to admit, so that someone other than the admitter sees each new node and each newly trusted host key.

### Check confirmations and candidates on commit

The handoff phase has uc-node write `confirmation.yml` and a candidates entry into the client's inventory repository. Extend the client repository's pre-commit hook then, to check those files with `scripts/check_raw_confirmation.py` and the candidates rules of `05_admit.yml`.

### discover_subnet in the client inventory

`ingress/playbooks/00_discover.yml` defaults `discover_subnet` to an address range in code. Which subnet to scan is a fact about a client, so move it to the client inventory, in `raw/group_vars/all.yml` or the template's place for it, and give the code no default: a run without it refuses, rather than scanning a range that belongs to nobody in particular.

## Firewall

### Switch to steelcj.foomuuri

uc-node builds raw nodes with Foomuuri and writes the base fragment, `10-base`, as a bootstrap rule that lets the controller in. From admission on, uc-controller owns every fragment, as the raw node contract 0.3.1 allows and `en/docs/design/raw-node-handoff-inventories-and-secrets-v0.1.0.md` in uc-contracts describes. Replace `shared/roles/uc_firewall` with calls to `steelcj.foomuuri`, already in `requirements.yml`. `shared/vars/uc_firewall_interim.yml` and its test, `tests/test_uc_firewall_interim.py`, are removed with `uc_firewall`:

- Onboard writes `10-base`, the role's default fragment, replacing uc-node's file under the same name, from `firewall_onboard_ssh`. `foomuuri_require_ssh` stays true.
- Normalize writes `20-normalize`, and specialize `30-specialize`, from their service lists.
- Every call lists all of uc-controller's other fragments in `foomuuri_keep_fragments`, so rerunning normalize after specialize does not purge `30-specialize`.
- A stage whose service list is empty sets `foomuuri_fragment_state: absent`, so its old fragment is removed.

The client inventory's variables keep their names and shape. The approach is to be tried, and adjusted if testing shows a better way.

### Change the SSH port at onboard

Dev and stage both stay on port 22 for now. `steelcj.foomuuri` allows only `foomuuri_ssh_port`, and sshd moves later in the same run, so changing the port at onboard would lock the controller out: the lockout uc-node's ROADMAP describes under "Change the SSH port after first contact". Settle it together with uc-node.

### Narrow SSH on stage

`onboard/stage` allows SSH from `0.0.0.0/0`, any IPv4 address, which is as open as dev for IPv4. Narrow the IPv4 sources for SSH on stage.

## Ansible features

* fireball mode


