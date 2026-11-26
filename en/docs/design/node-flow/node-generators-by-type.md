# Node Generators by Type

This document looks at how the node generator controller talks to each kind of node generator, and how each one can be made to produce a node that meets the raw node contract. It covers creation only. Finding nodes that already exist (scans, DHCP leases, inventory plugins) belongs to the naming step that follows, and is covered here only where a source in the taxonomy turns out to be that kind of thing.

It draws on the raw node source taxonomy, the source connection matrix, the bounded complexity note, and the Option A migration analysis.

## What Every Generator Must Deliver

Whatever the generator, the node generator controller is done with a node when two things are true.

### The Node Meets the Contract

The node has an initial user with sudo (the name is a variable, `initial` by default), the fleet controller's SSH public key authorized for that user, the batch passphrase set, SSH open, a hostname, and the confirmation file.

### The Controller Can Name It

The node generator controller can write a candidates file entry for it: address, ED25519 host key fingerprint and batch. How the controller learns the address and fingerprint differs by type, and it decides how strong the handoff is. A fingerprint read through the generator's own trusted channel is as good as one read at a console. A node with no such channel falls back to an operator at the console, or to trust on first use.

## Three Ways to Put the Contract on a Node

Every generator in the taxonomy uses one of three patterns, or a mix of them.

### Seed at Creation

The generator passes a configuration to the node when it is created, and the node applies it on first boot. This is cloud-init in almost every case: user-data from a cloud provider's metadata service, an Incus or LXD `cloud-init.user-data` key, a Proxmox cloud-init drive, or a NoCloud seed image for libvirt. The node meets the contract on first boot with no further work from the controller. It needs an image with cloud-init installed.

### Answer the Installer

The operating system is installed fresh, and an answer file sets the contract: Debian preseed, Ubuntu autoinstall, or kickstart. uc-ventoy works this way, and so does PXE. The node meets the contract when the installer finishes.

### Converge Through the Generator's Channel

The node is created bare, and the controller reaches it through the generator's own channel to install SSH, Python and the initial user: `incus exec`, `lxc exec`, `docker exec`, or a hypervisor's guest agent. This is the bootstrap and transition pattern in the bounded complexity note.

In the two-controller design this pattern moves entirely to the node generator controller. The fleet controller never sees an `incus exec` connection, so the five-play onboarding with its connection transition becomes a pre-contract concern. It also removes the cause of Gap 1 in the Option A analysis, where the raw Incus group variables leaked into converge runs, because the fleet controller no longer loads source inventories at all.

## Containers

| Generator | How the controller talks to it | Ansible support | Contract pattern | Address and fingerprint |
| --- | --- | --- | --- | --- |
| Incus | `incus` CLI, or its REST API over the local socket or HTTPS | Connection and inventory plugins in community.general; no instance module there | Seed (cloud-init images) or converge over `incus exec` | `incus list` for the address; `incus exec <name> -- ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub` for the fingerprint |
| LXD | `lxc` CLI, or its REST API | `community.general.lxd_container` module, plus connection and inventory plugins | Seed or converge over `lxc exec` | Same approach as Incus |
| Docker | Docker Engine API | `community.docker.docker_container` module and `community.docker.docker` connection | Converge over `docker exec` | `docker inspect` for the address; `docker exec` for the fingerprint |

Incus has the strongest handoff of any type: the controller holds a trusted channel into the node, so it can read the fingerprint directly and write a console-grade candidates entry with no operator involved.

Creating Incus instances from Ansible is less settled than connecting to them. community.general provides a connection plugin that runs tasks through the Incus CLI <a id="cite-incus-connection"></a>([Ansible project contributors, n.d.-a](#ref-incus-connection)), but no module for creating instances. Third-party collections fill the gap, among them kmpm.incus, which aims to be merged into community.general eventually <a id="cite-kmpm-incus"></a>([kmpm, n.d.](#ref-kmpm-incus)). The Incus maintainers have suggested the LXD module should work against Incus, though users have reported errors doing so <a id="cite-lxc-forum"></a>([Linux Containers Forum, 2024](#ref-lxc-forum)). Calling the `incus` CLI from `ansible.builtin.command` is the dependable option for now.

Docker is a poor fit for raw nodes. An application container normally runs one process with no init system or SSH server, and the contract assumes both. It belongs in the taxonomy only if system-style containers are wanted. Otherwise it is better left out, or treated as a workload the fleet controller runs on nodes rather than a source of nodes.

## Hypervisors

| Generator | How the controller talks to it | Ansible support | Contract pattern | Address and fingerprint |
| --- | --- | --- | --- | --- |
| libvirt | `virsh` and `virt-install`, or the libvirt API | `community.libvirt.virt` module, plus connection and inventory plugins | Seed with a NoCloud image, or install with an answer file | `virsh domifaddr` for the address; the QEMU guest agent or the serial console for the fingerprint |
| Proxmox | Proxmox VE REST API | community.proxmox collection | Seed with Proxmox's built-in cloud-init support, or clone a prepared template | The API reports addresses through the guest agent; the fingerprint comes from the guest agent or the console |
| VMware | vSphere API | community.vmware collection, for example `vmware_guest` | Clone a template, then guest customization or cloud-init through guestinfo | The API reports addresses through VMware Tools; the fingerprint comes from the console |

The Proxmox modules have moved out of community.general into their own collection, and the old names now only forward to community.proxmox with a deprecation warning <a id="cite-proxmox-redirect"></a>([Ansible project contributors, n.d.-b](#ref-proxmox-redirect)).

Hypervisors sit between containers and cloud. The controller has an API and usually a guest agent, so it can learn the address without a scan. Reading the fingerprint through the guest agent is possible, but depends on the agent being installed and allowed to run commands.

## Cloud

| Generator | How the controller talks to it | Ansible support | Contract pattern | Address and fingerprint |
| --- | --- | --- | --- | --- |
| AWS | EC2 API | `amazon.aws.ec2_instance` | Seed with user-data | The API returns the address; the console output carries the fingerprints |
| Google Cloud | Compute Engine API | `google.cloud.gcp_compute_instance` | Seed with user-data in metadata | The API returns the address; the serial port output carries the fingerprints |
| Azure | Azure Resource Manager API | `azure.azcollection.azure_rm_virtualmachine` | Seed with custom data | The API returns the address; boot diagnostics carry the fingerprints |
| DigitalOcean | DigitalOcean API | `community.digitalocean.digital_ocean_droplet` | Seed with user-data | The API returns the address; the fingerprint is otherwise only at first use |

Cloud is the simplest type to bring to the contract, because every provider takes cloud-init user-data at creation. The initial user, the fleet controller's key and the batch passphrase hash all go in the user-data. Provider defaults such as `ec2-user`, `ubuntu` or root logins should be switched off there too, so the node offers only what the contract promises.

The fingerprint is the weak point. cloud-init writes the host key fingerprints to the instance's console when it generates the keys, and most providers let the API read that console output. Reading it through the API gives a fingerprint from a channel the provider vouches for, which is far better than trusting the first SSH connection.

The cloud credentials stay on the node generator controller. This is the clearest case for two controllers: the fleet controller never holds a key that can create or destroy machines.

## Bare Metal

| Generator | How the controller talks to it | Ansible support | Contract pattern | Address and fingerprint |
| --- | --- | --- | --- | --- |
| Ventoy | None while installing: a prepared USB stick | None; uc-ventoy builds the stick | Answer the installer | Read at the console by the operator |
| PXE | DHCP and TFTP or HTTP boot services the controller runs | Roles that configure dnsmasq or similar | Answer the installer | DHCP leases give the address; the console gives the fingerprint |
| IPMI and BMC | IPMI or Redfish on the management network | `community.general.ipmi_power`, `ipmi_boot` and `redfish_command` | None by itself | None by itself; a BMC with a remote console lets the operator read the fingerprint without being in the room |

IPMI and BMC are not generators in their own right. They switch a machine on and choose what it boots from. Paired with PXE they make bare metal fully remote: the BMC sets a network boot, PXE serves the installer and the answer file, and the node meets the contract when the install finishes.

Ventoy is the least automated path, and the most self-contained. It needs no network services on the controller's side and works on machines with no BMC, which suits small sites, older hardware and low bandwidth. The cost is that a person is at each machine, which is also what makes the console fingerprint easy to get.

## Not Generators

Two families in the taxonomy do not create nodes.

### Network

An nmap scan, a DHCP lease table and an ARP cache all find machines that already exist. They belong to the naming step: they produce candidate addresses for the fleet controller to admit, with no fingerprint, so their nodes are trusted on first use. The DHCP lease table is the exception within this family when the controller runs the DHCP server for PXE, because then it pairs a known MAC address with each lease.

### External

A CMDB, a custom API or manual entry holds records about machines, or requests for them. None of them builds anything. A CMDB entry or an API call might trigger a generator, and manual entry is an operator who has built a node some other way. In the two-controller design these are inputs to the node generator controller (what to build) or to the naming step (what was built), not sources in their own right.

## Summary by Type

| Type | Channel the controller holds | Usual contract pattern | Best fingerprint source | Credentials held |
| --- | --- | --- | --- | --- |
| Container | Exec into the node | Seed or converge | Exec, directly | Access to the container host |
| Hypervisor | Hypervisor API and guest agent | Seed or template | Guest agent or console | Hypervisor API account |
| Cloud | Provider API | Seed | Console output through the API | Provider API keys |
| Bare metal | None, or a BMC | Answer the installer | Console, local or through the BMC | BMC passwords, if any |
| Network | None | None | None, first use only | None |
| External | Varies | None | Depends on what built the node | Varies |

The pattern is clear. The more the controller can reach into a node through the generator, the more of the handoff it can do on its own, and the less a person or trust on first use has to supply.

## Corrections to the Connection Matrix

Two entries in the source connection matrix name connection plugins that are not where it says.

- Docker's connection plugin is `community.docker.docker`, not `community.general.docker`.
- libvirt's connection plugins are `community.libvirt.libvirt_qemu` and `community.libvirt.libvirt_lxc`. There is no plugin named `community.libvirt.libvirt`.

The matrix also mixes generators with discovery methods: the nmap scan, CMDB and manual rows describe how a node is found or recorded, not how it is made. A future version could split it into a generator matrix and a discovery matrix, matching the two controllers.

## Open Questions

- Should Docker stay in the taxonomy, or be treated as a workload rather than a source of nodes?
- For Incus, which creation method should the first shim use: the CLI from Ansible, a third-party collection, or OpenTofu?
- Should the contract require cloud-init on images where the generator supports it, so that seeding at creation becomes the default pattern and converging through the generator's channel the exception?
- For cloud, is reading the console output through the provider's API acceptable as a console-grade fingerprint source, or should cloud nodes be marked as weaker in the handoff?

## References

<a id="ref-incus-connection"></a>
[Return to citation](#cite-incus-connection)
Ansible project contributors. (n.d.-a). *community.general.incus connection: Run tasks in Incus instances using the Incus CLI*. Ansible Community Documentation. Retrieved November 18, 2026, from https://docs.ansible.com/ansible/devel/collections/community/general/incus_connection.html

<a id="ref-proxmox-redirect"></a>
[Return to citation](#cite-proxmox-redirect)
Ansible project contributors. (n.d.-b). *community.general.proxmox_kvm module*. Ansible Community Documentation. Retrieved November 18, 2026, from https://docs.ansible.com/ansible/latest/modules/proxmox_kvm_module.html

<a id="ref-kmpm-incus"></a>
[Return to citation](#cite-kmpm-incus)
kmpm. (n.d.). *ansible-collection-incus* [Computer software]. GitHub. Retrieved November 18, 2026, from https://github.com/kmpm/ansible-collection-incus

<a id="ref-lxc-forum"></a>
[Return to citation](#cite-lxc-forum)
Linux Containers Forum. (2024). *Creating container with Ansible* [Online forum thread]. Retrieved November 18, 2026, from https://discuss.linuxcontainers.org/t/creating-container-with-ansible/20050
