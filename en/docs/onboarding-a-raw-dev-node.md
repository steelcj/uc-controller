# Onboarding a Raw Dev Node to a Bootstrapped Dev Node

This guide walks through taking a fresh Incus instance from raw, reachable only as root over the Incus CLI, to onboarded, reachable over SSH as the `initial` management user with a hardened baseline. It covers the controller setup, the Incus node, SSH key loading, the run itself, verification, and a troubleshooting section for the problems you are most likely to hit on Debian trixie.

## Overview

The onboard stage reaches a raw node over the `community.general.incus` connection, which runs commands with `incus exec` as root, so the node needs no SSH, no network key, and no `initial` user to begin with. Over that connection the play installs Python, sets a tight system-wide umask before any user exists, installs and hardens sshd, opens the firewall, and creates the `initial` user with your public key and passwordless sudo. Only at the end does it switch the connection to SSH as `initial`, which is how every later stage reaches the node.

The practical consequence is that you drive the whole onboard from the controller without ever logging into the node by hand. The manual SSH steps below are for verification and troubleshooting, not for the onboard itself.

## Prerequisites

### Controller

Build and activate the Ansible virtual environment, then install the roles.

```sh
python3 scripts/make_ansible_venv.py
. ~/.venvs/ansible/current/bin/activate
ansible-galaxy install -r requirements.yml
```

The `requirements.yml` sources `steelcj.umask` from git over SSH, so that fork must be pushed to GitHub and your GitHub SSH key must be available before the install runs. The remaining roles come from Ansible Galaxy.

### The initial user's SSH key

The controller reaches onboarded nodes as `initial` using a dedicated key. Generate one if you do not have it yet.

```sh
ssh-keygen -t ed25519 -f ~/.ssh/gradus-raw-initial-id_ed25519 -C "initial@controller"
```

Put the public half into `inventories/onboard/dev/group_vars/all.yml` under the `initial` user's `authorized_keys`. The private half never leaves the controller. If your keys carry a passphrase, which is good practice, see the key-loading step below, since the passphrase workflow is the most common source of confusion during a run.

## Create the raw snapshot

Right after launching a new container, before Ansible touches it, snapshot it as `raw`. The name follows *Incus: Instance Naming*: `raw` is the origin you return to, and it is never overwritten.

```sh
incus launch images:debian/13 deb13
incus snapshot create deb13 raw
incus snapshot list deb13
```

This lets you restore an untouched node between testing and development runs.

## Restore the raw snapshot

When developing or testing, start from a container that has never been configured, to prove the infrastructure code works from scratch.

### Restore your snapshot

```bash
incus snapshot restore deb13 raw
python3 scripts/reset_inventories.py
```

The restore reverts the container only. `reset_inventories.py` clears the stage inventories and the fact cache on the controller, which still describe the node as it was before the restore. It clears every node; to clear one node only, see Restore and Resume in the design document.

### Start the instance

The inventory only lists running instances, so start the node you intend to onboard.

```sh
incus list
incus start deb13
```

For a virtual machine rather than a container, wait for the guest agent before Ansible can reach it. `incus exec deb13 -- true` returning without error is the signal it is ready. For the dev workflow here, containers are simpler and faster.

### Confirm it is running and has an address

```sh
incus list status=running -c ns4t
```

This shows the name, state, IPv4 address, and type. Note the address, you will use it for the manual verification SSH later.



## Secrets and Ansible vaults

The secrets pattern is not decided yet, and nothing in the lifecycle reads a vault today.

## Confirm the inventory sees the node

```sh
ansible-inventory -i inventories/raw -i inventories/onboard/dev --graph
```

Output example:

```bash
@all:
  |--@ungrouped:
  |--@raw:
  |  |--@incus:
  |  |  |--@incus_local:
  |  |  |  |--@incus_local_default:
  |  |  |  |  |--deb13
  |  |--@discovered:
  |--@onboarded:
```

You should see the node under `@raw`. `inventories/raw/incus.yml` sets `host_fqdn: false`, so the inventory name is the instance name, `deb13`, and `-l deb13` matches it. Without that setting the plugin would name it `deb13.default.local`.

## Load the SSH key into the agent

Because the key has a passphrase, Ansible cannot type it during a run. Load the key into your agent first, with a lifetime long enough to cover the development session.

For testing I use 8 hours and less depending how much time I expect to be testing.

```sh
ssh-add -l >/dev/null    # key still loaded?
ssh-add -t 8h ~/.ssh/gradus-raw-initial-id_ed25519 # LOAD KEY
ssh-add -l
```

The group variables pin this key and set `IdentitiesOnly=yes`, so ssh offers only this one key rather than spraying every key you have loaded. That matters: spraying several keys trips sshd's `MaxAuthTries` and gets the controller penalised or banned before the right key is tried.

## Run the onboard playbook

### Testing with new ansible.cfg environment variables

In this command we specify items that may or may not be set with different values in the ansible.cfg. Doing this ensures that these cfg  and override them with 

```sh
ANSIBLE_HOST_KEY_CHECKING=False ANSIBLE_STDOUT_CALLBACK=default ANSIBLE_CALLBACK_RESULT_FORMAT=yaml \
ansible-playbook -i inventories/raw -i inventories/onboard/dev \
  ingress/playbooks/10_onboard.yml -l deb13 -e target_group=webservers \
  -e onboard_inventory=inventories/onboard/dev
```

`target_group=webservers` also puts the node in the `webservers` group, which the specialize stage uses. The run moves through six plays: it confirms the raw node is reachable and promotes it, bootstraps Python over the Incus connection, converges the baseline roles, switches the connection to SSH as `initial`, confirms SSH and sudo work, and writes the node into `inventories/onboard/dev/hosts.yml`. A clean result is `failed=0`.

Output on 2026-11-11

```bash

PLAY RECAP ***********************************************************************************************************************************************************
deb13                      : ok=172  changed=32   unreachable=0    failed=0    skipped=76   rescued=1    ignored=0
```

### Adding options to ansible.cfg

```bash
nano ansible.cfg
```

Content example:

After testing the ansible run above if, for example, the following variable did what was desired then you can add them to ansible.cfg if you want to used them all the time. So the following:

```bash
ANSIBLE_HOST_KEY_CHECKING=False
ANSIBLE_STDOUT_CALLBACK=default
ANSIBLE_CALLBACK_RESULT_FORMAT=yaml
```

Look like this when placed in the `ansible.cfg` file:

```cfg
[defaults]
roles_path = ./roles:~/.ansible/roles:/usr/share/ansible/roles
inventory = ./inventories/raw
host_key_checking = False     # same as ANSIBLE_HOST_KEY_CHECKING=False
gathering = smart
fact_caching = jsonfile
fact_caching_connection = /tmp/ansible_facts
fact_caching_timeout = 3600
stdout_callback = default     # same as ANSIBLE_STDOUT_CALLBACK=default
callback_result_format = yaml # same as ANSIBLE_CALLBACK_RESULT_FORMAT=yaml
#stdout_callback = yaml
#callbacks_enabled = profile_tasks

[privilege_escalation]
become = True
become_method = sudo
become_user = root
become_ask_pass = False
```

Once in `ansible.cfg`you can simply run:

```bash
ansible-playbook -i inventories/raw -i inventories/onboard/dev \
  ingress/playbooks/10_onboard.yml -l deb13 -e target_group=webservers \
  -e onboard_inventory=inventories/onboard/dev
```

## Verify

From the controller, confirm login, sudo, and the umask settings.

### Set container ip address to var IP

```bash
IP=$(incus list deb13 -c4 --format csv | cut -d' ' -f1)
echo "$IP"
```

### Confirm initial user uid in container

```bash
ssh -i ~/.ssh/gradus-raw-initial-id_ed25519 -o IdentitiesOnly=yes initial@$IP id
```

Output

```bash
uid=1000(initial) gid=1000(initial) groups=1000(initial)
```

### Confirm passwordless sudo for user initial

```bash
ssh -i ~/.ssh/gradus-raw-initial-id_ed25519 -o IdentitiesOnly=yes initial@$IP sudo -n id
```

Output:

```bash
uid=0(root) gid=0(root) groups=0(root)
```

### Confirm `UMASK 0027` and `HOME_MODE 0750`

```bash
incus exec deb13 -- grep -E '^(UMASK|HOME_MODE)' /etc/login.defs
```

Output example:

```bash
HOME_MODE	0750
UMASK		0027
```

### Confirm permissions `750` on the home directory.

```sh
incus exec deb13 -- stat -c '%a %n' /home/initial
```

Output example:

```bash
750 /home/initial
```

## Rerun onboard.yml

A clean `failed=0` starting from the restored snapshot is the strongest proof that a brand-new node onboards in a single pass. Running onboard again on a node that is already onboarded changes nothing: the first play finds the `initial` user and skips the host.

## Next stages

Normalize and specialize follow, each as its own command. [Onboarding a New Incus Node: deb13](onboarding/onboarding-a-new-incus-node-deb13.md) walks through the whole chain from launch to a specialized web server, with a stopped snapshot after each stage.

```bash
ansible-playbook -i inventories/raw -i inventories/onboard/dev -i inventories/normalized/dev \
  converge/playbooks/20_normalize.yml -l deb13 \
  -e onboard_inventory=inventories/onboard/dev \
  -e normalized_inventory=inventories/normalized/dev

ansible-playbook -i inventories/raw -i inventories/onboard/dev -i inventories/normalized/dev \
  converge/playbooks/30_specialize.yml -l deb13 \
  -e specialize_role=webserver
```

## Troubleshooting

### Could not match supplied host pattern

The `--limit` value did not match any inventory host. Usually the node is stopped, and the `status=running` filter leaves it out of the inventory. Start the node and check `ansible-inventory --graph` for the exact name.

### The callback plugin has been removed

An `ansible.cfg` that sets `stdout_callback = community.general.yaml` fails on recent collections, since that callback was removed in community.general 12.0.0. Replace it with the in-core default callback and its YAML result format.

```ini
[defaults]
stdout_callback = default
callback_result_format = yaml
```

### No package matching 'ntp' is available

Debian trixie dropped the `ntp` package, and containers take their clock from the host and usually cannot set time anyway. The playbook guards the ntp role so it skips on containers. For virtual machines or bare metal on trixie, time sync needs a different approach, chrony or systemd-timesyncd, rather than the `ntp` package.

### Connection refused on port 22

Connection refused means nothing is listening, or an explicit reject rule is in the way, as opposed to a timeout which means packets are being dropped. Check in order, over the Incus connection so you do not depend on SSH.

```sh
incus exec deb13 -- ss -tlnp 'sport = :22'
incus exec deb13 -- systemctl status ssh --no-pager
incus exec deb13 -- systemctl status ssh ssh.socket --no-pager | tail -30
incus exec deb13 -- nft list ruleset
incus exec deb13 -- fail2ban-client status sshd
```

If nothing is listening, the openssh role has not run yet, the most common reason is an earlier task failing before it. If sshd is listening but the fail2ban jail shows your controller banned, note that the jail rejects with `icmp port-unreachable`, which presents as connection refused rather than a timeout. Clear it with `fail2ban-client set sshd unbanip <controller-ip>` or restart fail2ban.

### Too many authentication failures

The sshd log shows `maximum authentication attempts exceeded` and the client is disconnected before the right key is tried. This happens when ssh offers several keys and hits `MaxAuthTries`. Using `ssh -i <key>` alone does not prevent it, since ssh still offers every other loaded key. Add `-o IdentitiesOnly=yes` so only the named key is offered, which is also set for Ansible in the group variables.

### ssh-agent ssh-add anomalies

#### Desktop ssh-agent and gnome-keyring interactions

On a GNOME or Cinnamon desktop, which is what Mint runs, `gnome-keyring-daemon` can provide its own SSH agent and export `SSH_AUTH_SOCK` pointing at its socket, so when you run `ssh-add` the key often lands in gnome-keyring rather than the plain OpenSSH `ssh-agent`. gnome-keyring then stores the passphrase in your login keyring and can auto-unlock it at login, which is convenient, but its agent historically lagged OpenSSH on newer key types and options, so ed25519 keys and constraints like `ssh-add -t` or `-c` are where you see oddities, including the “agent refused operation” signing failures. The two agents also compete: whichever one owns `SSH_AUTH_SOCK` is the one ssh talks to, so a key loaded into one is invisible to the other, which is a common reason a key “isn’t loaded” even though you just added it. If you want predictable behaviour for automation, the usual fix is to disable gnome-keyring’s SSH component (its `gnome-keyring-ssh` autostart) and let the real `ssh-agent` own the socket, then confirm with `echo $SSH_AUTH_SOCK` and `ssh-add -l` that you are talking to the agent you think you are.

#### Possible solutions

A few concrete fixes, most reliable first.

Make the OpenSSH agent own the socket, disable gnome-keyring’s SSH component. Mask the autostart so it stops grabbing `SSH_AUTH_SOCK`:

```sh
cp /etc/xdg/autostart/gnome-keyring-ssh.desktop ~/.config/autostart/ 2>/dev/null
printf 'Hidden=true\nX-GNOME-Autostart-enabled=false\n' >> ~/.config/autostart/gnome-keyring-ssh.desktop
```

Log out and back in, then run a real agent and point your shell at it. The simplest durable setup on a systemd distro is the user service:

```sh
systemctl --user enable --now ssh-agent.service 2>/dev/null
echo 'export SSH_AUTH_SOCK="$XDG_RUNTIME_DIR/ssh-agent.socket"' >> ~/.profile
```

If there is no `ssh-agent.service`, start one per login instead with `eval "$(ssh-agent -s)"` in your shell profile.

Let ssh manage key loading so you stop doing it by hand. In `~/.ssh/config`:

```
AddKeysToAgent yes
IdentitiesOnly yes

Host deb13 10.119.134.*
    User initial
    IdentityFile ~/.ssh/gradus-raw-initial-id_ed25519
```

With `AddKeysToAgent yes`, the first connect prompts for the passphrase once and loads the key for the session, and `IdentitiesOnly yes` stops the key spraying that tripped `MaxAuthTries` earlier.

Check which agent you are actually talking to before debugging anything else:

```sh
echo "$SSH_AUTH_SOCK"     # a keyring path means gnome-keyring still owns it
ssh-add -l                # is the right key there?
```

A quick per-shell override if you just need a clean agent now, without logout:

```sh
eval "$(ssh-agent -s)"
ssh-add -t 8h ~/.ssh/gradus-raw-initial-id_ed25519
```

One caveat worth checking: recent gnome-keyring versions dropped the SSH agent entirely, so on an up-to-date Mint the keyring may not be in the picture at all. If `echo $SSH_AUTH_SOCK` already shows an `ssh-agent` or `XDG_RUNTIME_DIR` path rather than a `keyring` one, OpenSSH’s agent is already in charge and the autostart step is unnecessary.

#### Agent refused operation

```
sign_and_send_pubkey: signing failed for ED25519 ... from agent: agent refused operation
```

The key is loaded in the agent but the agent declined to sign, often because the key was added with a confirmation constraint, the agent is locked, or a passphrase-protected key was not properly loaded. Reload it cleanly.

```sh
ssh-add -d ~/.ssh/gradus-raw-initial-id_ed25519
ssh-add -t 8h ~/.ssh/gradus-raw-initial-id_ed25519
```

To test the key file directly, bypassing the agent, add `-o IdentityAgent=none`, but only for a passphraseless key, since bypassing the agent makes ssh ask for the passphrase, which Ansible cannot supply.

### AuthorizedKeysCommand path is not absolute

The sshd log repeats this error on trixie. The openssh role writes `AuthorizedKeysCommand none` unconditionally, and this OpenSSH version rejects `none` there. It is noise rather than a blocker, sshd falls back to the `authorized_keys` file, so it does not stop a correctly keyed login. The clean fix is a role patch that only emits the `AuthorizedKeysCommand` lines when the value is not `none`.
