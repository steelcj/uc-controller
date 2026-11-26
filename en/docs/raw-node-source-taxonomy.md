# Raw Node Source Taxonomy

The places a raw node can come from before it is onboarded, grouped by source type, with the access method for each where one applies.

```mermaid
flowchart LR
    root["Raw Node Sources"]

    root --> container["Container"]
    root --> hypervisor["Hypervisor"]
    root --> cloud["Cloud"]
    root --> network["Network"]
    root --> baremetal["Bare Metal"]
    root --> external["External"]

    container --> incus["Incus (incus exec)"]
    container --> lxd["LXD (lxc exec)"]
    container --> docker["Docker (docker exec)"]

    hypervisor --> libvirt["libvirt (virsh)"]
    hypervisor --> proxmox["Proxmox (API)"]
    hypervisor --> vmware["VMware (API)"]

    cloud --> aws["AWS (inventory plugin)"]
    cloud --> gcp["GCP (inventory plugin)"]
    cloud --> azure["Azure (inventory plugin)"]
    cloud --> digitalocean["DigitalOcean (API)"]

    network --> nmap["nmap subnet scan"]
    network --> dhcp["DHCP lease table"]
    network --> arp["ARP cache"]

    baremetal --> pxe["PXE boot"]
    baremetal --> ipmi["IPMI / BMC"]

    external --> cmdb["CMDB / ServiceNow"]
    external --> customapi["Custom API"]
    external --> manual["Manual entry"]

    classDef rootStyle fill:#23233a,stroke:#6366f1,color:#818cf8,stroke-width:2px
    classDef containerStyle fill:#23233a,stroke:#6366f1,color:#818cf8,stroke-width:2px
    classDef hypervisorStyle fill:#1c2b24,stroke:#10b981,color:#34d399,stroke-width:2px
    classDef cloudStyle fill:#352b1c,stroke:#f59e0b,color:#fbbf24,stroke-width:2px
    classDef networkStyle fill:#352020,stroke:#ef4444,color:#f87171,stroke-width:2px
    classDef baremetalStyle fill:#2a2438,stroke:#8b5cf6,color:#a78bfa,stroke-width:2px
    classDef externalStyle fill:#1c2b2e,stroke:#06b6d4,color:#22d3ee,stroke-width:2px

    class root rootStyle
    class container,incus,lxd,docker containerStyle
    class hypervisor,libvirt,proxmox,vmware hypervisorStyle
    class cloud,aws,gcp,azure,digitalocean cloudStyle
    class network,nmap,dhcp,arp networkStyle
    class baremetal,pxe,ipmi baremetalStyle
    class external,cmdb,customapi,manual externalStyle
```

## Sources by type

| Type | Source | Access method |
| --- | --- | --- |
| Container | Incus | `incus exec` |
| Container | LXD | `lxc exec` |
| Container | Docker | `docker exec` |
| Hypervisor | libvirt | `virsh` |
| Hypervisor | Proxmox | API |
| Hypervisor | VMware | API |
| Cloud | AWS | Inventory plugin |
| Cloud | GCP | Inventory plugin |
| Cloud | Azure | Inventory plugin |
| Cloud | DigitalOcean | API |
| Network | nmap subnet scan | |
| Network | DHCP lease table | |
| Network | ARP cache | |
| Bare Metal | PXE boot | |
| Bare Metal | IPMI / BMC | |
| External | CMDB / ServiceNow | |
| External | Custom API | |
| External | Manual entry | |
