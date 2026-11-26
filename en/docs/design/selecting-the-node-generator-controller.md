# Selecting the Node Generator Controller

Status: proposal

Date: 2026-11-18

## Purpose

This document records the choice of tool for the node generator controller, the pre-contract controller that creates nodes and prepares them to meet the raw node contract. It sets out the problems the controller has to solve, the options considered, and why OpenTofu is proposed. It also states what OpenTofu does not solve, so those gaps are planned for rather than discovered.

## Context

Node handling is split between two controllers, with the raw node contract between them.

The node generator controller creates nodes from many kinds of generator (containers, hypervisors, cloud providers, bare metal) and prepares each one to meet the contract. It speaks whatever each generator requires.

The fleet controller, uc-controller, is built on Ansible. It admits nodes that meet the contract, onboards them, and configures them with distro agnostic methods. It never needs to know where a node came from.

Between the two sits the candidates file: an address, host key fingerprint and batch for each node built. Admission checks every candidate against the contract, whatever produced it.

The generator types and the ways each one can be driven are described in Node Generators by Type. This document picks the tool that drives them.

## The Problems We Are Trying to Solve

### Sprawl Across Generators

Every generator has its own interface: the `incus` CLI, a hypervisor API, a cloud provider's API. Left alone, each source arrives with its own tool, its own collection or library, and its own way of doing things. The number of tools grows with the number of sources, and so does the learning needed to work on any of them. For a small practice, every extra tool is a cost paid again by each new contributor and each client handover.

### Source Logic Leaking into the Fleet Controller

The current repository already shows what happens when node creation and node configuration share a tool and an inventory. The raw Incus group variables, which reach nodes as root over `incus exec`, follow those nodes into converge runs unless every onboarded host overrides them (Gap 1 in the Option A migration analysis). The bounded complexity note contains source diversity in onboarding, but only by adding connection transitions to the fleet controller's own playbooks. The aim is to move all of that out of the fleet controller entirely.

### A Lifecycle, Not a One-Off

Nodes are created, rebuilt and destroyed repeatedly, especially Incus test nodes. The tool needs to show what it will change before it changes it, bring reality back to the declared state, and remove what it created cleanly. Doing that by hand, or with tasks that each check for existence first, is slow to write and easy to get wrong.

### Separating Credentials

The credentials that create and destroy machines (Incus trust, hypervisor accounts, cloud API keys) should live only on the pre-contract side. The fleet controller should be unable to create or destroy anything.

### Producing the Handoff

For each node it builds, the controller has to report what the candidates file needs: the address, the host key fingerprint and the batch. A tool that can return structured outputs after creating something makes this simple; one that cannot leaves it to scripts.

### Agency and Sovereignty

The practice's own principles apply to its tooling. The controller should be open source under a licence that cannot be withdrawn, avoid tying clients to one vendor, work for sites with low or intermittent bandwidth, and be something a client could run or migrate without the practice.

## Requirements

From those problems, the tool should:

- drive containers, hypervisors and cloud providers through one language and one workflow;
- run separately from the fleet controller, with its own credentials;
- plan changes before applying them, and destroy what it created;
- return structured outputs for each node it creates;
- protect any secrets it stores;
- be open source under an OSI-approved licence, with governance not controlled by a single vendor;
- work offline or with limited bandwidth once set up.

## Options Considered

### A Native Tool per Generator

The `incus` CLI for Incus, provider CLIs for cloud, and so on. Each is the most direct route to its own generator, but together they are exactly the sprawl described above.

### Ansible

Ansible is already in the practice's stack, so it adds nothing new to learn. It has creation modules for most generators, through separate collections. Its weaknesses here are uneven creation support (community.general can connect to Incus instances but has no module for creating them), no plan or state, and no built-in destroy. Using Ansible on both sides would also make it easier for source logic to drift back into the fleet controller, because nothing in the tooling marks the boundary.

### Terraform

Terraform has the workflow and the provider ecosystem this controller needs. Its licence rules it out. Terraform 1.5.7 was the final release under the Mozilla Public License 2.0, and later releases ship under the Business Source License 1.1, a source-available licence <a id="cite-spacelift"></a>([Spacelift, n.d.](#ref-spacelift)). That is the kind of dependency the practice exists to avoid.

### OpenTofu

The open source fork of Terraform, described in the next section.

### Image Builders

Distrobuilder and Packer build images rather than instances. They complement whichever tool is chosen, if prepared images are wanted later, but cannot be the controller on their own.

## Why OpenTofu

### One Language for Every Generator with an API

OpenTofu describes infrastructure in one language and applies it with one workflow, whatever the target. Each generator is reached through a provider, and the OpenTofu Registry holds more than 4,000 of them <a id="cite-registry"></a>([OpenTofu, n.d.-a](#ref-registry)). Providers exist for every generator type in the taxonomy that has an API.

| Generator type | Generators | Provider |
| --- | --- | --- |
| Containers | Incus | `lxc/incus`, maintained by the Incus project |
| Containers | Docker | community provider |
| Hypervisors | libvirt, Proxmox, VMware vSphere | community and vendor providers |
| Cloud | AWS, Google Cloud, Azure, DigitalOcean | vendor providers |

Provider names and maintainers should be confirmed in the registry before each is adopted.

The Incus provider is a first-party project. It reached version 1.0 after almost two years of work by 23 contributors, aims at full coverage of the Incus API, and works with both Terraform and OpenTofu <a id="cite-incus-provider"></a>([Linux Containers Forum, n.d.-a](#ref-incus-provider)). The Incus documentation lists it as the way to create projects, profiles, networks, storage volumes and instances <a id="cite-incus-third-party"></a>([Linux Containers, n.d.](#ref-incus-third-party)).

Learning OpenTofu once covers every generator added later. That is the strongest argument for it, and the direct answer to the sprawl problem.

### It Fits the Two-Controller Boundary

OpenTofu builds nodes, Ansible configures them. Because the two controllers use different tools, source-specific logic cannot slip into the fleet controller unnoticed. This split is also a common pattern in the Incus community: one reply on the Linux Containers forum describes preferring Terraform for creating instances and storage, and the Ansible Incus connection plugin for deploying into them <a id="cite-split"></a>([Linux Containers Forum, n.d.-b](#ref-split)).

### A Managed Lifecycle

`tofu plan` shows what will change before anything does, `tofu apply` brings the generators to the declared state, and `tofu destroy` removes what was created. Rebuilding a set of test nodes becomes a matter of changing the declaration, not writing tasks that check for existing instances.

### Structured Outputs for the Handoff

Each OpenTofu configuration can declare outputs, and `tofu output -json` returns them in a form a small script can turn into candidates file entries. The address of each node comes straight from the provider.

### Open Licence and Neutral Governance

OpenTofu is licensed under MPL 2.0 and maintained by the Linux Foundation <a id="cite-wikipedia"></a>([Wikipedia contributors, n.d.](#ref-wikipedia)). It was created by forking the last MPL-licensed Terraform and placing it in the Linux Foundation, on the same model as Linux itself, managed by the foundation under the stewardship of several companies <a id="cite-manifesto"></a>([OpenTofu, n.d.-b](#ref-manifesto)). It has been a CNCF Sandbox project since April 2025 ([Spacelift, n.d.](#ref-spacelift)). No single vendor can change its licence.

### Secrets in State Can Be Encrypted

OpenTofu keeps a state file recording what it created, including the cloud-init user-data and, with it, the batch passphrase hash. OpenTofu can encrypt state and plan files at rest, both locally and in a remote backend <a id="cite-encryption"></a>([OpenTofu, n.d.-c](#ref-encryption)). This is enabled from the start.

### It Can Work Offline

Providers can be copied to a local mirror and installed from there, which suits air-gapped sites <a id="cite-mirror"></a>([Dhandala, 2026](#ref-mirror)). After the first setup, building nodes does not depend on a connection to a public registry, which matters for the low and intermittent bandwidth sites the practice aims to serve.

## What OpenTofu Does Not Solve

### Bare Metal Without an API

Ventoy installs have nothing for OpenTofu to call. uc-ventoy stays the generator for that path, with the operator reading the address and fingerprint at the console. PXE and BMC control could later come from OpenTofu providers or small Ansible tasks, decided when needed.

### The Contract Itself

OpenTofu delivers the contract to each node, usually as cloud-init user-data, but does not define it. The user-data and the confirmation file script should be shared with uc-ventoy wherever possible, so every generator produces the same confirmation and admission never sees two versions that nearly agree.

### The Host Key Fingerprint

Providers return addresses, not SSH host key fingerprints. Each generator needs a small step after `tofu apply` to read the fingerprint through its own channel: `incus exec` for Incus, console output through the API for cloud. That step is part of each shim and is written once per generator type.

### A New Learning Curve

OpenTofu's configuration language is new to the practice. The cost is paid once and then covers every generator, which is the trade this document proposes. The alternative is a smaller cost paid again for each new source.

### The State File

The state file becomes a new artefact that holds secrets and must be backed up. Without the encryption key it cannot be read, so the key needs the same care as the vault passphrases: kept in the password manager, never in the repository.

### Uneven Provider Quality

Outside the major clouds and Incus, many providers are maintained by the community. Each needs checking for activity and fit before it is adopted, the same evaluation the practice applies to any product or service.

## Proposal

Use OpenTofu for the node generator controller, in its own repository, separate from uc-controller. Start with Incus containers and virtual machines, launched from cloud images with the contract delivered as cloud-init user-data. Each Incus shim writes candidates file entries using the address from OpenTofu's outputs and the fingerprint read through `incus exec`. Enable state encryption from the first commit. Add further generators as providers, one shim at a time.

## Open Questions

- What should the repository be called?
- Where is the state kept: locally on the operator's workstation, or in a shared backend?
- Should the cloud-init user-data and confirmation script move into uc-contracts, so uc-ventoy and the OpenTofu shims share one copy?
- Should the step that reads fingerprints and writes the candidates file be an OpenTofu `local-exec` provisioner, or a separate script run after `tofu apply`?

## References

<a id="ref-mirror"></a>
[Return to citation](#cite-mirror)
Dhandala, N. (2026, March 20). *How the OpenTofu provider registry protocol works*. OneUptime. Retrieved November 18, 2026, from https://oneuptime.com/blog/post/2026-03-20-provider-registry-protocol-opentofu/view

<a id="ref-incus-third-party"></a>
[Return to citation](#cite-incus-third-party)
Linux Containers. (n.d.). *Third party tools and integrations*. Incus documentation. Retrieved November 18, 2026, from https://linuxcontainers.org/incus/docs/main/third_party/

<a id="ref-incus-provider"></a>
[Return to citation](#cite-incus-provider)
Linux Containers Forum. (n.d.-a). *Terraform Provider for Incus 1.0 has been released* [Online forum thread]. Retrieved November 18, 2026, from https://discuss.linuxcontainers.org/t/terraform-provider-for-incus-1-0-has-been-released/25034

<a id="ref-split"></a>
[Return to citation](#cite-split)
Linux Containers Forum. (n.d.-b). *Ansible guidance: Receiving errors when using lxd_container plugin* [Online forum thread]. Retrieved November 18, 2026, from https://discuss.linuxcontainers.org/t/ansible-guidance-receiving-errors-when-using-lxd-container-plugin/18734

<a id="ref-registry"></a>
[Return to citation](#cite-registry)
OpenTofu. (n.d.-a). *Building the OpenTofu Registry*. OpenTofu blog. Retrieved November 18, 2026, from https://opentofu.org/blog/building-the-opentofu-registry/

<a id="ref-manifesto"></a>
[Return to citation](#cite-manifesto)
OpenTofu. (n.d.-b). *The OpenTofu manifesto*. Retrieved November 18, 2026, from https://opentofu.org/manifesto

<a id="ref-encryption"></a>
[Return to citation](#cite-encryption)
OpenTofu. (n.d.-c). *State and plan encryption*. OpenTofu documentation. Retrieved November 18, 2026, from https://opentofu.org/docs/main/language/state/encryption/

<a id="ref-spacelift"></a>
[Return to citation](#cite-spacelift)
Spacelift. (n.d.). *Terraform license change*. Spacelift blog. Retrieved November 18, 2026, from https://spacelift.io/blog/terraform-license-change

<a id="ref-wikipedia"></a>
[Return to citation](#cite-wikipedia)
Wikipedia contributors. (n.d.). *OpenTofu*. Wikipedia. Retrieved November 18, 2026, from https://en.wikipedia.org/wiki/OpenTofu
