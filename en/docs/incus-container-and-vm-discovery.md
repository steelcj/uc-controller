## incus-container-and-vm-discovery

The `community.general` collection that came with your ansible 14.6.0 install has an Incus inventory source. Containers and virtual machines are both pulled straight from the Incus manager, and the plugin first shipped in community.general 12.0.0. A minimal `inventories/raw/incus.yml`:

```yaml
plugin: community.general.incus
filters:
  - status=running
```

Check it with `ansible-inventory -i inventories/raw/incus.yml --graph`.

Output example:

```bash
ansible-inventory -i inventories/raw/incus.yml --graph
@all:
  |--@ungrouped:
  |--@incus:
  |  |--@incus_local:
  |  |  |--@incus_local_default:
  |  |  |  |--ex2-test.default.local
  |  |  |  |--mint223.default.local
```



- **Host names:** by default they come out in INSTANCE.PROJECT.REMOTE form; set `host_fqdn: false` if you want bare instance names.
- **The `raw` group:** `10_onboard.yml` targets `hosts: raw`, so the instances need to land in that group. I have not checked this plugin's grouping options, so confirm with `ansible-doc -t inventory community.general.incus`.

Manual `hosts.yml` entries still make sense for nodes Incus doesn't know about (bare metal, a VPS). The nmap scan suits those, since it finds addresses but can't tell you the OOB user.

## Bootstrapping without OOB SSH

Your plan (root over SSH with a key, then create `initial`) has a chicken-and-egg problem on Incus: most images ship with no root password, no authorized key, and often no sshd. The same collection has a connection plugin for this. With it, tasks run inside the instance through the Incus CLI, which is `incus exec` as root, so no network, key or sshd is needed.

So for Incus nodes the raw stage sets:

```yaml
# inventories/raw/group_vars/raw.yml
ansible_connection: community.general.incus
ansible_user: root
```

The onboard play then does what you listed, over that connection:

1. Install and enable `openssh-server`.
2. Create the `initial` user with your public key and passwordless sudo.
3. Open port 22 in the firewall (your `firewall_rules_onboard` already does this).
4. Harden sshd (no root login, no passwords).

After that, the onboard and normalized inventories use `ansible_connection: ssh`, `ansible_user: initial` and the instance's IP. The OOB method stays a raw-stage variable, so a bare-metal node with root SSH and an Incus node with `incus exec` go through the same onboard play.

One thing to verify on your VMs: `incus exec` needs the Incus agent running in the guest. The `images:` VM images include it; a VM installed from an ISO may not.

## An alternative for throwaway test nodes

Use the `/cloud` image variants with an Incus profile carrying cloud-init user-data that creates `initial` with your key at launch. Instances are then SSH-ready on first boot and can skip straight to onboarded. It is faster, but it doesn't exercise your onboard stage, which is probably what you want to test.

## A gap in the current design doc

`10_onboard.yml` promotes hosts with `add_host`, copying only `ansible_host`. Nothing switches the connection from root to `initial` afterwards, so the "converge onboard baseline" play would keep running as the OOB user. That switch needs to be explicit, either in the `add_host` task or in the onboard inventory's group vars.

Want me to draft the Incus inventory file, the raw group vars and a revised `10_onboard.yml` with the bootstrap tasks and the user switch?

Sources:

- [community.general.incus inventory (devel)](https://docs.ansible.com/ansible/devel/collections/community/general/incus_inventory.html)
- [community.general.incus inventory (Ansible 13)](https://docs.ansible.com/projects/ansible/13/collections/community/general/incus_inventory.html)
- [community.general.incus connection (Ansible 13)](https://docs.ansible.com/projects/ansible/13/collections/community/general/incus_connection.html)