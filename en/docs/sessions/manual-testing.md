# Manual Testing

This is the command sequence from the Option A migration session, in the order it was run. Each step can be repeated by hand from the root of the uc-controller repository. Commands under Next Steps have not been run yet.

## Environment

Activate the Ansible virtual environment and confirm Ansible runs.

```sh
cd ~/areas/development/uc-controller
```

```sh
source ~/.venvs/ansible/current/bin/activate
```

```sh
ansible --version
```

Result: `ansible [core 2.21.6]`, using the repository's `ansible.cfg`.

## Phase 0: Baseline

Commit the reset helper on its own, then commit the remaining untracked files so the working tree is clean.

```sh
git add scripts/reset_inventories.py
git commit -m "Add scripts/reset_inventories.py dev helper"
```

```sh
git add ROADMAP.md en/docs/fragment-001.md en/docs/onboarding-a-raw-dev-node.md en/docs/onboarding en/docs/sessions scripts/timestamp_prefix.py
git commit -m "docs: add onboarding notes, Option A analysis, and session prompt"
```

```sh
git status --short
```

Result: no output, the tree is clean.

Tag the pre-migration layout.

```sh
git tag v0.1.3-layout
```

Dry run of the inventory reset.

```sh
python3 scripts/reset_inventories.py -n
```

Result:

```text
Would clear raw: already empty
Would clear onboard/dev: already empty
Would clear onboard/stage: already empty
Would clear normalized/dev: already empty
Would clear normalized/stage: already empty
Would clear fact cache: 1 file(s) in /tmp/ansible_facts
```

Confirm the test instance name from the Incus inventory.

```sh
ansible-inventory -i inventories/raw/incus.yml --graph
```

Result: `ex2-test.default.local` is listed under `@raw` and under `@incus_local_default`.

```sh
incus list -c ns4t
```

```sh
incus snapshot list ex2-test
```

Result: `ex2-test` is running, with the snapshots `fresh`, `before-ansible2-20261110`, `ansible2-converged` and `pre-onboard`.

## Phase 1: Static Checks

Syntax-check the edited playbooks.

```sh
ansible-playbook -i inventories/raw -i inventories/onboard/dev playbooks/lifecycle/10_onboard.yml --syntax-check
```

```sh
ansible-playbook -i inventories/raw -i inventories/onboard/dev playbooks/lifecycle/00_discover.yml --syntax-check
```

```sh
ansible-playbook playbooks/lifecycle/scaffold.yml --syntax-check
```

Result: all three pass.

Confirm the `realpath` filter used by the persist play resolves against the directory `ansible-playbook` is started from.

```sh
ansible localhost -o -m debug -a "msg={{ 'inventories/raw' | ansible.builtin.realpath }}"
```

Result: the absolute path of `inventories/raw` in this repository.

## Phase 1: Promote and Demote Against a Copy

These run against a throwaway copy of the inventories, so nothing in the repository changes. `PYTHONDONTWRITEBYTECODE` keeps the tracked `scripts/__pycache__/` files untouched.

```sh
export PYTHONDONTWRITEBYTECODE=1
REPO="$PWD"
P="$REPO/scripts"
K='~/.ssh/gradus-raw-initial-id_ed25519'
T="$(mktemp -d)"
cp -r inventories "$T/"
cd "$T"
```

Seed one static host in the raw inventory.

```sh
printf 'raw:\n  hosts:\n    static-1:\n      ansible_host: 192.168.1.50\n      ansible_user: root\n' > inventories/raw/hosts.yml
```

Promote a static host. The contract replaces `ansible_user: root` and other variables are kept.

```sh
python3 "$P/promote_node.py" --from inventories/raw --to inventories/onboard/dev --host static-1 --key-file "$K" --no-commit
```

Promote a plugin-style host that is not in `raw/hosts.yml`, using `--address`.

```sh
python3 "$P/promote_node.py" --from inventories/raw --to inventories/onboard/dev --host ex2-test.default.local --address 10.119.134.207 --key-file "$K" --group webservers --no-commit
```

Result: `note: ex2-test.default.local was not in inventories/raw/hosts.yml; created from --address`. The raw file is left unchanged.

Promote the same host again with a new address. The entry is replaced, not duplicated.

```sh
python3 "$P/promote_node.py" --from inventories/raw --to inventories/onboard/dev --host ex2-test.default.local --address 10.119.134.208 --key-file "$K" --group webservers --no-commit
```

```sh
cat inventories/onboard/dev/hosts.yml
```

Result: one entry for each host under `onboarded`, each with `ansible_host`, `ansible_connection: ssh`, `ansible_user: initial` and `ansible_ssh_private_key_file`, and `ex2-test.default.local` under `webservers`.

Promote from onboard to normalized. The contract is kept.

```sh
python3 "$P/promote_node.py" --from inventories/onboard/dev --to inventories/normalized/dev --host ex2-test.default.local --no-commit
cat inventories/normalized/dev/hosts.yml
```

Demote from normalized to onboard. The contract is kept.

```sh
python3 "$P/demote_node.py" --from inventories/normalized/dev --to inventories/onboard/dev --host ex2-test.default.local --no-commit
cat inventories/onboard/dev/hosts.yml
```

Demote from onboard to raw. The contract is removed.

```sh
python3 "$P/demote_node.py" --from inventories/onboard/dev --to inventories/raw --host ex2-test.default.local --no-commit
cat inventories/raw/hosts.yml inventories/onboard/dev/hosts.yml
```

Result: `ex2-test.default.local: null` in `raw/hosts.yml`, and `onboarded` is empty.

Error cases.

```sh
python3 "$P/promote_node.py" --from inventories/raw --to inventories/onboard/dev --host nope --key-file "$K" --no-commit; echo "exit=$?"
```

Result: `error: host nope not found in inventories/raw/hosts.yml`, exit 1.

```sh
python3 "$P/promote_node.py" --from inventories/raw --to inventories/onboard/dev --host static-1 --no-commit; echo "exit=$?"
```

Result: `error: no key file for static-1; pass --key-file`, exit 1.

```sh
python3 "$P/promote_node.py" --from inventories/onboard/dev --to inventories/raw --host x --no-commit; echo "exit=$?"
```

Result: `error: cannot promote from onboard to raw`, exit 1.

Return to the repository.

```sh
cd "$REPO"
rm -rf "$T"
```

## Phase 1: From-Scratch Onboarding Cycle

This cycle ran four times. Run 1 failed on SSH authentication. Runs 2 and 3 passed but wrote an expanded key path. Run 4 is the final run, and all checks below come from it.

Before onboarding, make sure the onboarding key is in the SSH agent. Without it, the agent's other keys are offered first, sshd hits `MaxAuthTries 6`, and fail2ban bans the controller (see Run 1).

```sh
ssh-add -t 1h ~/.ssh/gradus-raw-initial-id_ed25519
```

```sh
ssh-add -l | grep -c h27xQHOLSZdjpBAd
```

Result: `1`, the key is loaded.

Restore the instance to the `fresh` snapshot.

```sh
incus snapshot restore ex2-test fresh
```

```sh
incus list ex2-test -c ns4t
```

Result: `ex2-test` is running at `10.119.134.207`.

Check that the instance is raw.

```sh
incus exec ex2-test -- sh -c 'id initial; command -v python3; command -v sshd'
```

Result: no `initial` user and no Python. The `fresh` snapshot already has `/usr/sbin/sshd`.

Clear the inventories and the fact cache.

```sh
python3 scripts/reset_inventories.py
```

Onboard the test instance.

```sh
ansible-playbook -i inventories/raw -i inventories/onboard/dev playbooks/lifecycle/10_onboard.yml -l ex2-test.default.local -e target_group=webservers -e onboard_inventory=inventories/onboard/dev
```

Result:

```text
ex2-test.default.local : ok=174 changed=33 unreachable=0 failed=0 skipped=76 rescued=1 ignored=0
```

The one rescued task is the `robertdebock.bootstrap` connection test, which is expected to fail before Python is installed.

Check that the contract is on disk at host level.

```sh
cat inventories/onboard/dev/hosts.yml
```

Result:

```yaml
onboarded:
  hosts:
    ex2-test.default.local:
      ansible_connection: ssh
      ansible_user: initial
      ansible_host: 10.119.134.207
      ansible_ssh_private_key_file: ~/.ssh/gradus-raw-initial-id_ed25519
webservers:
  hosts:
    ex2-test.default.local: null
```

```sh
ansible-inventory -i inventories/onboard/dev --graph --vars
```

Result: `ex2-test.default.local` under `@onboarded` and `@webservers` with the four contract variables. The output also lists every cached fact, because the jsonfile fact cache feeds `ansible-inventory`.

Check that the contract wins whichever order the inventories are loaded in.

```sh
ansible-inventory -i inventories/raw -i inventories/onboard/dev --host ex2-test.default.local
```

```sh
ansible-inventory -i inventories/onboard/dev -i inventories/raw --host ex2-test.default.local
```

Result, the same for both orders:

```json
{"ansible_host": "10.119.134.207", "ansible_connection": "ssh", "ansible_user": "initial", "ansible_ssh_private_key_file": "~/.ssh/gradus-raw-initial-id_ed25519"}
```

Check that a separate run reaches the node from the onboard inventory alone, over SSH as `initial` with sudo.

```sh
ansible -i inventories/onboard/dev onboarded -m ansible.builtin.ping
```

Result: `ex2-test.default.local | SUCCESS`, `ping: pong`.

```sh
ansible -i inventories/onboard/dev onboarded -b -m ansible.builtin.command -a id
```

Result: `uid=0(root) gid=0(root) groups=0(root)`.

## Run 1: fail2ban Ban

The first run reached the final check and failed with `ssh: connect to host 10.119.134.207 port 22: Connection refused`. The persist play never ran, so nothing was written to the inventory. These are the commands used to find the cause.

```sh
incus exec ex2-test -- sh -c 'systemctl is-active ssh; ss -tlnp | grep :22; ufw status verbose'
```

Result: sshd is active and listening on port 22, and ufw allows 22/tcp.

```sh
incus exec ex2-test -- sh -c 'fail2ban-client status sshd; nft list set inet f2b-table addr-set-sshd'
```

Result: the controller address `10.119.134.1` is banned, and nftables rejects it on port 22.

```sh
incus exec ex2-test -- sh -c 'journalctl -u ssh --no-pager | tail -25'
```

Result: `maximum authentication attempts exceeded for initial from 10.119.134.1` and `Too many authentication failures`.

Compare the public key on the node with the controller's public key.

```sh
incus exec ex2-test -- ssh-keygen -lf /home/initial/.ssh/authorized_keys
ssh-keygen -lf ~/.ssh/gradus-raw-initial-id_ed25519.pub
ssh-add -l | wc -l
```

Result: both fingerprints are `SHA256:h27xQHOLSZdjpBAd/ZLsXn00y5U7KyIAI2wyyuKodnA`, so the key is correct. The agent held 14 other keys, and `gradus-raw-initial` was not loaded. SSH offers agent keys before the `-i` key file, so the 6 allowed attempts ran out first. Each `wait_for_connection` retry added a failure, and fail2ban banned the controller after 5.

Lift the ban and test once with only the key file offered.

```sh
incus exec ex2-test -- fail2ban-client set sshd unbanip 10.119.134.1
```

```sh
ssh -o BatchMode=yes -o IdentitiesOnly=yes -i ~/.ssh/gradus-raw-initial-id_ed25519 initial@10.119.134.207 'id; sudo -n id'
```

Result: `uid=1000(initial)` then `uid=0(root)`. Once the key was added to the agent with `ssh-add`, login also works without `IdentitiesOnly`.

## Runs 2 and 3: Expanded Key Path

Run 2 passed every check, but `hosts.yml` held `/home/initial/.ssh/gradus-raw-initial-id_ed25519` instead of the `~/` form, which is not valid on another controller. Run 3 changed the persist task to read `onboard_ssh_private_key_file` instead of `ansible_ssh_private_key_file`, and the path was still expanded. This test found the cause:

```sh
cat > /tmp/tilde.yml <<'Y'
- hosts: localhost
  gather_facts: no
  become: no
  tasks:
    - command:
        argv: ['echo', '~/.ssh/x']
      register: a
    - command:
        argv: ['echo', '~/.ssh/x']
        expand_argument_vars: false
      register: b
    - debug: {msg: "default={{ a.stdout }} expand_false={{ b.stdout }}"}
Y
ansible-playbook /tmp/tilde.yml
```

Result: `default=/home/initial/.ssh/x expand_false=~/.ssh/x`. The `command` module expands `~` in arguments by default. The persist task now sets `expand_argument_vars: false`, and run 4 wrote the `~/` form.
