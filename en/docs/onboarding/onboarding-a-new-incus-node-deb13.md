# Onboarding a New Incus Node: deb13

This guide takes a brand-new Debian 13 Incus container called `deb13` from launch to an onboarded and normalized node that the controller manages over SSH as the `initial` user. Every command runs on the controller, from the root of the `uc-controller` repository.

The node goes through four states, and each one gets a snapshot so you can return to it later:

| State | How it gets there | Snapshot | Inventory that holds it |
|-------|-------------------|----------|-------------------------|
| Raw | `incus launch` | `pristine`, `raw` | `inventories/raw`, through the Incus plugin |
| Onboarded | `10_onboard.yml` | `10-onboarded` | `inventories/onboard/dev/hosts.yml` |
| Normalized | `20_normalize.yml` | `20-normalized` | `inventories/normalized/dev/hosts.yml` |

## Before you start

You need the controller set up once, as described in [Onboarding a Raw Dev Node](../onboarding-a-raw-dev-node.md):

- the Ansible virtual environment built and the roles installed
- the `initial` user's key pair at `~/.ssh/gradus-raw-initial-id_ed25519`, with its public half in `inventories/onboard/dev/group_vars/all.yml`

Activate the environment in the shell you will use:

```bash
. ~/.venvs/ansible/current/bin/activate
```

## 1. Launch the container and take the first snapshots

```bash
incus launch images:debian/13 deb13  # launch, fetching the image if needed
incus snapshot create deb13 pristine # create deb13 snapshot named pristine
incus snapshot create deb13 raw      # create deb13 snapshot named raw
incus snapshot list deb13            # list snapshots of deb13 to confirm
```

Expected output:

```text
┌──────────┬──────────────────────┬────────────┬──────────┐
│   NAME   │       TAKEN AT       │ EXPIRES AT │ STATEFUL │
├──────────┼──────────────────────┼────────────┼──────────┤
│ raw      │ 2026/11/12 23:33 EST │            │ NO       │
├──────────┼──────────────────────┼────────────┼──────────┤
│ pristine │ 2026/11/12 23:39 EST │            │ NO       │
└──────────┴──────────────────────┴────────────┴──────────┘
```

`raw` is the origin you return to when you want to onboard again. Never overwrite it: if the image changes, launch a new instance instead. Both snapshots are taken before Ansible touches the node, so they hold the image exactly as launched.

## 2. Confirm the container is running and reachable

```bash
incus list                                   # list running containers and VMs
incus exec deb13 -- cat /etc/os-release      # confirm connectivity
incus exec deb13 -- systemctl status         # confirm systemd is up
incus exec deb13 -- ip a                     # get the IP address
```

`incus list` shows the address directly:

```text
┌─────────┬─────────┬──────────────────────┬─────────────────┐
│  NAME   │  STATE  │         IPV4         │      TYPE       │
├─────────┼─────────┼──────────────────────┼─────────────────┤
│ deb13   │ RUNNING │ 10.119.134.49 (eth0) │ CONTAINER       │
└─────────┴─────────┴──────────────────────┴─────────────────┘
```

In this walkthrough the address is `10.119.134.49`. Yours will differ. Keep it in a shell variable for the checks later on:

```bash
IP=$(incus list deb13 -c4 --format csv | cut -d' ' -f1)
echo "$IP"
```

## 3. Add the node to the virtual inventory

There is nothing to type into a hosts file. The raw inventory for Incus is virtual: `inventories/raw/incus.yml` is a configuration for the `community.general.incus` inventory plugin, which asks Incus for its running instances every time Ansible runs and creates one host for each.

```yaml
plugin: community.general.incus
host_fqdn: false
filters:
  - status=running
```

Two settings matter here:

- `filters: status=running` means the node is in the inventory only while it runs. A stopped container is invisible to Ansible.
- `host_fqdn: false` keeps the inventory name equal to the instance name, `deb13`, so `-l deb13` matches it.

The plugin puts the node in the `incus` group, and `inventories/raw/hosts.yml` makes `incus` a child of `raw`. That is how the node becomes a raw host. `inventories/raw/group_vars/incus.yml` tells Ansible to reach it through the Incus API as root, with no SSH.

### Clear entries left by an earlier deb13

Instance names are reused, so the stage inventories may still hold an entry for a previous `deb13` with an old address. Check before you onboard:

```bash
grep -n -A6 'deb13' inventories/onboard/dev/hosts.yml inventories/normalized/dev/hosts.yml
```

If an entry is there, remove it. On a development machine where every node is reset together, clear all stage inventories and the fact cache at once:

```bash
python3 scripts/reset_inventories.py
```

To remove only `deb13`, demote it to raw and flush its cached facts:

```bash
python3 scripts/demote_node.py --from inventories/normalized/dev --to inventories/raw --host deb13 --no-commit
CACHE="$(ansible-config dump | awk -F' = ' '/^CACHE_PLUGIN_CONNECTION/{print $2}')"; CACHE="${CACHE/#\~/$HOME}"
find "$CACHE" -maxdepth 1 \( -name deb13 -o -name '*_deb13' \) -delete
```

Use `--from inventories/onboard/dev` instead if the old entry is in the onboard inventory. A stale entry matters because `20_normalize.yml` leaves a host that is already in the normalized inventory where it is, so the old address would never be replaced.

### Confirm Ansible sees the node

```bash
ansible-inventory -i inventories/raw -i inventories/onboard/dev --graph
```

Expected output:

```text
@all:
  |--@ungrouped:
  |--@raw:
  |  |--@incus:
  |  |  |--@incus_local:
  |  |  |  |--@incus_local_default:
  |  |  |  |  |--deb13
  |  |--@discovered:
  |--@onboarded:
  |--@webservers:
```

`deb13` sits under `@raw` and nowhere else. If it is missing, the container is stopped or the name is different; check `incus list`.

## 4. Load the SSH key into the agent

The last plays of the onboard run switch to SSH as `initial`, and Ansible cannot type a key passphrase. Load the key first, with a lifetime that covers the session:

```bash
ssh-add -t 8h ~/.ssh/gradus-raw-initial-id_ed25519
ssh-add -l
```

If the key does not show up, or signing fails, see the ssh-agent section of [Onboarding a Raw Dev Node](../onboarding-a-raw-dev-node.md#ssh-agent-ssh-add-anomalies).

## 5. Onboard

```bash
ansible-playbook -i inventories/raw -i inventories/onboard/dev \
  ingress/playbooks/10_onboard.yml -l deb13 \
  -e target_group=webservers \
  -e onboard_inventory=inventories/onboard/dev
```

What the run does, play by play:

1. Skips the node if the `initial` user already exists, then probes it over the Incus connection and promotes it to `onboarded` in memory.
2. Installs Python, still as root over Incus.
3. Converges the onboarding baseline: umask, sshd hardening, firewall, locale, and the `initial` user with your public key and passwordless sudo.
4. Switches the connection to SSH as `initial`.
5. Confirms SSH and sudo work.
6. Writes the node and its connection settings to `inventories/onboard/dev/hosts.yml` with `promote_node.py`, in the `onboarded` group and in `webservers` because of `target_group`.

A good run ends with `failed=0`. 

Output tail example:

```text
PLAY RECAP *******************************************************************************************************************************
deb13                      : ok=178  changed=33   unreachable=0    failed=0    skipped=69   rescued=1    ignored=0   


TASKS RECAP ******************************************************************************************************************************
Friday 13 November 2026  01:21:57 -0500 (0:00:00.383)       0:01:55.530 ******* 
=============================================================================== 
robertdebock.bootstrap : Install bootstrap packages (raw) ------------------------------------------------------------------------ 19.79s
robertdebock.cron : Install cron ------------------------------------------------------------------------------------------------- 16.97s
robertdebock.locale : Install requirements --------------------------------------------------------------------------------------- 15.15s
robertdebock.fail2ban : Install fail2ban ------------------------------------------------------------------------------------------ 9.74s
robertdebock.openssh : Install openssh -------------------------------------------------------------------------------------------- 7.81s
robertdebock.auto_update : Install packages --------------------------------------------------------------------------------------- 7.02s
robertdebock.bootstrap : Install bootstrap packages (package) --------------------------------------------------------------------- 3.58s
robertdebock.bootstrap : Test connection ------------------------------------------------------------------------------------------ 3.30s
uc_firewall : Install ufw --------------------------------------------------------------------------------------------------------- 3.30s
robertdebock.auto_update : Start and enable auto_update --------------------------------------------------------------------------- 1.83s
robertdebock.fail2ban : Configure jail.local -------------------------------------------------------------------------------------- 1.65s
robertdebock.users : user | Check users password valid time for initial ----------------------------------------------------------- 1.28s
robertdebock.update : Update all software (apt) ----------------------------------------------------------------------------------- 1.12s
robertdebock.fail2ban : Restart fail2ban ------------------------------------------------------------------------------------------ 0.97s
robertdebock.bootstrap : Gather ansible facts ------------------------------------------------------------------------------------- 0.79s
steelcj.umask : system | Deploy /etc/profile.d/umask.sh --------------------------------------------------------------------------- 0.79s
robertdebock.openssh : Generate host key ------------------------------------------------------------------------------------------ 0.77s
robertdebock.users : Manage cron permission --------------------------------------------------------------------------------------- 0.77s
robertdebock.openssh : Configure openssh ------------------------------------------------------------------------------------------ 0.68s
robertdebock.users : user | Set sudo options for initial -------------------------------------------------------------------------- 0.68s

```



The new inventory entry is left uncommitted for you to review:

```bash
git diff inventories/onboard/dev/hosts.yml
```

It should look like this, with your address:

```yaml
onboarded:
  hosts:
    deb13:
      uc_origin: plugin
      ansible_connection: ssh
      ansible_user: initial
      ansible_ssh_common_args: -o IdentitiesOnly=yes
      ansible_host: 10.119.134.49
      ansible_ssh_private_key_file: ~/.ssh/gradus-raw-initial-id_ed25519
webservers:
  hosts:
    deb13: null
```

`uc_origin: plugin` records that the host came from the Incus plugin, so demoting it to raw later removes the entry instead of writing it into `inventories/raw/hosts.yml`.

## 6. Verify the onboarded node

Log in as `initial`:

```bash
ssh -i ~/.ssh/gradus-raw-initial-id_ed25519 -o IdentitiesOnly=yes initial@$IP id
```

```text
uid=1000(initial) gid=1000(initial) groups=1000(initial)
```

Passwordless sudo:

```bash
ssh -i ~/.ssh/gradus-raw-initial-id_ed25519 -o IdentitiesOnly=yes initial@$IP sudo -n id
```

```text
uid=0(root) gid=0(root) groups=0(root)
```

The umask and home directory mode:

```bash
incus exec deb13 -- grep -E '^(UMASK|HOME_MODE)' /etc/login.defs
incus exec deb13 -- stat -c '%a %n' /home/initial
incus exec deb13 -- ufw status
```

output examples:

```text
HOME_MODE	0750
UMASK		0027
750 /home/initial
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere                   # allow-ssh
22/tcp (v6)                ALLOW       Anywhere (v6)              # allow-ssh
```

Ansible over the new connection:

```bash
ansible -i inventories/onboard/dev deb13 -m ansible.builtin.ping
```

output

```bash
ansible -i inventories/onboard/dev deb13 -m ansible.builtin.ping
```

## 7. Snapshot the onboarded state

Take every stage snapshot with the container stopped, each step under a time limit, and wait for SSH before you carry on. A snapshot of a running container hung twice on the workstation; a stopped container has nothing to freeze.

```bash
timeout 120 incus stop deb13
timeout 120 incus snapshot create deb13 10-onboarded
timeout 120 incus start deb13
ansible -i inventories/onboard/dev deb13 -m ansible.builtin.wait_for_connection
```

Check that the host disk has room before snapshotting. A full root filesystem stops the Incus storage pool from growing:

```bash
df -h /
```

## 8. Normalize

```bash
ansible-playbook -i inventories/raw -i inventories/onboard/dev -i inventories/normalized/dev \
  converge/playbooks/20_normalize.yml -l deb13 \
  -e onboard_inventory=inventories/onboard/dev \
  -e normalized_inventory=inventories/normalized/dev
```

Output example:

```bash
PLAY RECAP ********************************************************************************
deb13                      : ok=51   changed=6    unreachable=0    failed=0    skipped=60   rescued=0    ignored=0   


TASKS RECAP *******************************************************************************
Friday 13 November 2026  01:31:34 -0500 (0:00:00.343)       0:00:16.619 ******* 
=============================================================================== 
robertdebock.rsyslog : Install rsyslog --------------------------------------------- 5.08s
uc_firewall : Allow each rule ------------------------------------------------------ 1.02s
Gathering Facts -------------------------------------------------------------------- 0.72s
robertdebock.sysctl : Install requirements ----------------------------------------- 0.70s
uc_firewall : Install ufw ---------------------------------------------------------- 0.65s
robertdebock.rsyslog : Configuring default rsyslog --------------------------------- 0.63s
robertdebock.hostname : Install requirements --------------------------------------- 0.60s
uc_firewall : Enable ufw ----------------------------------------------------------- 0.58s
robertdebock.hostname : Set hostname ----------------------------------------------- 0.56s
robertdebock.rsyslog : Start and enable rsyslog service ---------------------------- 0.52s
uc_firewall : Remove conflicting firewall software --------------------------------- 0.47s
robertdebock.rsyslog : Uninstall conflicting systemd-logger ------------------------ 0.45s
robertdebock.rsyslog : Restart rsyslog --------------------------------------------- 0.40s
uc_firewall : Start ufw at boot ---------------------------------------------------- 0.34s
move each normalized host to the normalized inventory ------------------------------ 0.34s
uc_firewall : Allow outgoing by default -------------------------------------------- 0.34s
robertdebock.rsyslog : Make configuration directory -------------------------------- 0.33s
uc_firewall : Deny incoming by default --------------------------------------------- 0.32s
confirm reachability --------------------------------------------------------------- 0.27s
robertdebock.auditd : assert | Test item.filters in auditd_rules ------------------- 0.07s
```

Normalize validates the node, applies the compliance baseline (sysctl, hostname, rsyslog and the normalize firewall rules; SELinux and auditd are skipped on a Debian container), and moves the entry from `inventories/onboard/dev/hosts.yml` to `inventories/normalized/dev/hosts.yml`. The `webservers` membership moves with it. Review the change:

```bash
git diff inventories/onboard/dev/hosts.yml inventories/normalized/dev/hosts.yml
```

Output example:

```yaml
 normalized:
-  hosts: {}
+  hosts:
+    deb13:
+      uc_origin: plugin
+      ansible_connection: ssh
+      ansible_user: initial
+      ansible_ssh_common_args: -o IdentitiesOnly=yes
+      ansible_host: 10.119.134.49
+      ansible_ssh_private_key_file: ~/.ssh/gradus-raw-initial-id_ed25519
+webservers:
+  hosts:
+    deb13: null
```

The `robertdebock.hostname` role reboots the node if it changes the hostname. That is expected and the run waits for it.

```bash
incus exec deb13 -- ufw status
```

Output example:

```bash
Status: active

To                         Action      From
--                         ------      ----
22/tcp                     ALLOW       Anywhere                   # allow-ssh
9100/tcp                   ALLOW       10.0.0.0/24                # allow-monitoring
22/tcp (v6)                ALLOW       Anywhere (v6)              # allow-ssh

```

Then snapshot, stopped, as before:

```bash
timeout 120 incus stop deb13
timeout 120 incus snapshot create deb13 20-normalized
timeout 120 incus start deb13
ansible -i inventories/normalized/dev deb13 -m ansible.builtin.wait_for_connection
```

Output example:

```bash
deb13 | SUCCESS => 
    changed: false
    elapsed: 0
```

and

```bash
incus snapshot list deb13
```

```bash
┌───────────────┬──────────────────────┬────────────┬──────────┐
│     NAME      │       TAKEN AT       │ EXPIRES AT │ STATEFUL │
├───────────────┼──────────────────────┼────────────┼──────────┤
│ raw           │ 2026/11/12 23:33 EST │            │ NO       │
├───────────────┼──────────────────────┼────────────┼──────────┤
│ pristine      │ 2026/11/12 23:39 EST │            │ NO       │
├───────────────┼──────────────────────┼────────────┼──────────┤
│ 10-onboarded  │ 2026/11/13 01:30 EST │            │ NO       │
├───────────────┼──────────────────────┼────────────┼──────────┤
│ 20-normalized │ 2026/11/13 01:35 EST │            │ NO       │
└───────────────┴──────────────────────┴────────────┴──────────┘
```

The list should now show `raw`, `pristine`, `10-onboarded` and `20-normalized`. The node is ready for `30_specialize.yml`.

## Going back

Restoring a snapshot changes the container only. Move the inventory entry back to the matching stage and flush the cached facts, or the next run reaches the node at a stale address.

To onboard again from scratch:

```bash
incus snapshot restore deb13 raw
python3 scripts/demote_node.py --from inventories/normalized/dev --to inventories/raw --host deb13 --no-commit
CACHE="$(ansible-config dump | awk -F' = ' '/^CACHE_PLUGIN_CONNECTION/{print $2}')"; CACHE="${CACHE/#\~/$HOME}"
find "$CACHE" -maxdepth 1 \( -name deb13 -o -name '*_deb13' \) -delete
```

To normalize again from the onboarded state:

```bash
incus snapshot restore deb13 10-onboarded
python3 scripts/demote_node.py --from inventories/normalized/dev --to inventories/onboard/dev --host deb13 --no-commit
CACHE="$(ansible-config dump | awk -F' = ' '/^CACHE_PLUGIN_CONNECTION/{print $2}')"; CACHE="${CACHE/#\~/$HOME}"
find "$CACHE" -maxdepth 1 \( -name deb13 -o -name '*_deb13' \) -delete
```

Demoting from normalized to onboard keeps the connection settings and the `webservers` membership.

## Troubleshooting

**`Could not match supplied host pattern`.** The container is stopped, so the plugin leaves it out, or the name in `-l` does not match. Run `incus list` and the `--graph` command from step 3.

**The onboard run reports the host as already onboarded and does nothing.** The `initial` user exists, so the node was onboarded before. Restore `raw` and demote the entry, as in [Going back](#going-back).

**`Connection refused` or `Too many authentication failures` on port 22.** See the troubleshooting section of [Onboarding a Raw Dev Node](../onboarding-a-raw-dev-node.md#troubleshooting), which covers sshd, fail2ban, `IdentitiesOnly` and agent problems.

**A snapshot hangs.** Interrupt it, check `df -h /`, and retake it with the container stopped as in step 7.
