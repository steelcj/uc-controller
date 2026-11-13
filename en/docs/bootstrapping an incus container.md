# bootstrapping an incus container.

Good idea to rehearse it on the one container before trusting it. Here’s an ordered walkthrough built around your `ex2-test` Debian container, with a rollback net so you can run it as many times as you need.

### Step 0: Snapshot first

This is what makes iterating painless. Onboarding changes the container for real (installs packages, creates the user, rewrites sshd), so take a snapshot you can roll back to:

sh

```sh
incus snapshot create ex2-test pre-onboard
```

To reset between runs: `incus snapshot restore ex2-test pre-onboard`.

### Step 1: Install the roles

The playbook calls a dozen `robertdebock.*` roles. Install them into the active venv from the repo’s `requirements.yml`:

```sh
ansible-galaxy install -r requirements.yml
```

If any are missing from that file, the run fails at the first missing role with a clear name.

### Step 2: Define the `initial` user (prerequisite)

Plays 4 and 5 log in over SSH as `initial`, so `robertdebock.users` has to create that user with your public key and sudo during the baseline play. Until that’s defined, the run will get through bootstrap and baseline but fail at the SSH-as-initial check. That vars block belongs in `inventories/onboard/dev/group_vars/all.yml`. I didn’t want to guess the exact key names `robertdebock.users` expects, so let me draft that precisely before you run end to end. For now, know it’s the one missing piece.

### Step 3: Confirm the inventory wiring

Two inventories must be passed: `raw` (where the node is) and `onboard/dev` (where `firewall_rules_onboard` and the user vars live). Check the `raw` group exists and the onboard vars resolve:

sh

```sh
ansible-inventory -i inventories/raw/incus.yml -i inventories/onboard/dev --graph
```

You should see `@raw` with `ex2-test` under it. If `@raw` is missing, the `groups: raw: true` line in `incus.yml` didn’t take, and play 1 matches nothing.

### Step 4: Syntax check and dry list

sh

```sh
ansible-playbook -i inventories/raw/incus.yml -i inventories/onboard/dev \
  ingress/playbooks/10_onboard.yml --syntax-check

ansible-playbook -i inventories/raw/incus.yml -i inventories/onboard/dev \
  ingress/playbooks/10_onboard.yml -l ex2-test --list-hosts
```

Note: `--check` (dry run) is not reliable for this flow. Bootstrap uses `raw`, and several roles make real changes that check mode can’t model, so the snapshot from step 0 is your real safety net, not `--check`.

### Step 5: The run, one host, verbose

sh

```sh
ansible-playbook -i inventories/raw/incus.yml -i inventories/onboard/dev \
  ingress/playbooks/10_onboard.yml -l ex2-test -e target_group=webservers -e onboard_inventory=inventories/onboard/dev -vv
```

`-l ex2-test` keeps it to the one container, `-vv` shows you each task. Watch the play boundaries:

- **Play 1** (Confirm reachable / promote): the `raw: 'true'` probe succeeds immediately over incus, then promotes `ex2-test` into `onboarded`.
- **Play 2** (Bootstrap): installs Python via `raw`. This is the Incus-specific step; if it fails, the connection or `bootstrap_become` is the cause.
- **Play 3** (Baseline): the long one. `epel` should skip on Debian (it’s RedHat-family); `update`/`auto_update` will run apt and take a while; `openssh`, `firewall` and `users` are the ones that matter here.
- **Play 4** (Switch to initial): no visible work, just re-points the in-memory host at SSH as `initial`.
- **Play 5** (Confirm): `wait_for_connection` then `id`. Success here means SSH-as-initial and sudo both work. This is your pass/fail line.

### Step 6: Verify from outside Ansible

sh

```sh
incus exec ex2-test -- id initial                    # user exists, right groups
incus exec ex2-test -- sshd -T | grep -Ei 'permitrootlogin|passwordauth'
ssh initial@<container-ip> id                        # key login works
```

The container IP is in `incus list -c ns4t`.

### Step 7: Re-test

sh

```sh
incus snapshot restore ex2-test pre-onboard
```

Onboarding writes the node into `inventories/onboard/dev/hosts.yml` with an SSH connection contract. After a snapshot reset, the node has no sshd user to answer that contract, so demote it before onboarding it again. A plugin-discovered host such as this one is removed from the onboard inventory and not written to raw:

```sh
python3 scripts/demote_node.py --from inventories/onboard/dev --to inventories/raw --host ex2-test.default.local --no-commit
```

Or clear every stage inventory and the fact cache at once:

```sh
python3 scripts/reset_inventories.py
```

Then rerun step 5. Clean slate every time.

One config note for step 5: play 5’s SSH to a freshly created host will hit host-key checking. For a test controller, set `host_key_checking = False` in `ansible.cfg` (or `ANSIBLE_HOST_KEY_CHECKING=False` inline), or the first run stalls on the unknown-host prompt.

Want me to draft that `initial` user block now so step 2 is covered and you can run it straight through?