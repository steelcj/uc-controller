Phase 0 and Phase 1 are done and committed. rky9 passes the whole chain, but only after a fix to normalize, and SELinux enforcing breaks the Incus agent on it. That last point needs your decision before I continue. Nothing is pushed or merged.

Phase 0 (docs/post-freeze-housekeeping, 2 commits)

- Stray commit: the first commit puts the two stage inventories back to their empty committed state and untracks resume.txt (now ignored). The live entries stay on disk, uncommitted.
- Port 443 on deb13: I restored 20-normalized and reran specialize (failed=0). ufw now lists only allow-ssh, allow-monitoring and allow-http, and curl returns deb13. 30-webserver was retaken with the instance stopped.
- Design doc: v0.1.6 started; v0.1.5 is untouched.

Phase 1 (test/rky9, 1 commit)

rky9 is a Rocky 9.8 VM with 2 vCPU, 2 GiB RAM and a 20 GiB disk, default variant. It has all four snapshots: raw, 10-onboarded, 20-normalized, 30-webserver.

┌─────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────────┐
│            Check            │                                        Result                                        │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ Onboard                     │ ok=187 changed=37 failed=0, over the Incus connection; nothing in ingress/ changed   │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ Normalize                   │ First run failed; after the fix, ok=98 changed=14 failed=0 from a clean 10-onboarded │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ Specialize                  │ ok=16 changed=4 failed=0                                                             │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ Reruns                      │ Normalize changed=0, no reboot, boot ID and hostname unchanged; specialize changed=0 │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ SELinux                     │ Disabled in the image, Enforcing after one normalize run; boot ID changed            │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ auditd                      │ Active and enabled; auditctl -s shows enabled 1                                      │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ firewalld before specialize │ 22/tcp open to all, 9100 as a rich rule from 10.0.0.0/24, port 80 refused            │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ firewalld after specialize  │ 80 open, SSH works, earlier rules still present                                      │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ webserver                   │ curl returns rky9 with SELinux enforcing                                             │
├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
│ Time sync                   │ Onboarding installed chrony; chronyd is active, enabled and synced                   │
└─────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────────┘

- The normalize failure and fix: the image has no SELinux policy package and no /etc/selinux/config, and robertdebock.selinux only installs the Python bindings. 20_normalize.yml now installs selinux-policy-targeted in a Red Hat-only pre-task. The vendored role is untouched.
- Which Reboot handler runs: the one in robertdebock.hostname. Only the SELinux task notified it (the hostname task reported no change), and the log line reads RUNNING HANDLER [robertdebock.hostname : Reboot]. So hostname_reboot, not selinux_reboot, controls the SELinux reboot.
- Page file: it replaced a symlink to ../../testpage/index.html with a regular file, context unconfined_u:object_r:httpd_sys_content_t:s0.
- Zone defaults: firewalld's public zone also keeps cockpit and dhcpv6-client open, which the role does not remove.
- Root filesystem: it stayed at 3.8 GiB despite the 20 GiB disk; nothing grows the partition.

Needs your decision

SELinux enforcing stops the Incus agent on rky9. After normalize, incus-agent.service fails (audit log: denied creating its vsock socket), so incus exec rky9 and the Incus connection no longer work. SSH, and incus stop, start, snapshot and restore, still work. One side effect: an onboard run without -l would wait on the normalized rky9 in raw and report it failed.

It is recorded as a Known Issue and not fixed. Options:
1. Accept and document (what I've done so far). A normalized Red Hat VM is managed over SSH only. I recommend this for now, since it changes nothing in the frozen design.
2. Local SELinux policy module allowing the socket, applied in normalize. This restores incus exec, but it is new configuration that needs a home (a small project role).
3. Exclude it from raw, for example by filtering the plugin, to remove the onboard side effect. This touches inventories/raw/incus.yml.

Things that went wrong along the way

- Launch: incus launch failed because the image needs an agent:config disk. I added the device and started the instance. The guide documents this as incus init, add the device, then incus start; that exact sequence has not been run.
- Snapshot hang, and my error: the first 20-normalized snapshot timed out (the known hang), and my chained command carried on into specialize instead of stopping to retry. I recovered by restoring rky9 to 10-onboarded and redoing normalize; since then every snapshot step runs on its own.
- Extra restores: in total I restored rky9 to 10-onboarded four times and to 30-webserver once while settling the fix. These were beyond the operations I listed when asking for go-ahead.
- Snapshots predate the final fix: the 20-normalized and 30-webserver snapshots were taken with an earlier variant of the fix that produces the same node state. The final verification rebuilds from raw anyway.

Disk: 57 GB free on / (60 GB at the start). The boundary check and --syntax-check pass on every playbook.

Go-ahead for Phase 2 (launch ubu2404 as a container and run the chain), and which option for the agent issue?