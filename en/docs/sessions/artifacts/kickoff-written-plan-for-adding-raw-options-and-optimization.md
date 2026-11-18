# kickoff-written-plan-for-adding-raw-options-and-optimization

I'd do it as four small branches after `option-a` is merged, inventory first and speed last, because the speed settings should be measured against a workflow that has stopped changing. I haven't read the repo for this, so step 0 is checking the notes against what is actually on `main`.

## 0. Baseline

- Merge `option-a`, then confirm which review items are still open. The persistence model for `add_host` / `promote_node.py` may already be closed by the promotion work, and the two High items have no write-up in the notes, so they need re-deriving from the code.
- Answer the structural question: is `raw/incus.yml` a plugin config or a static group?
- Enable `ansible.posix.profile_tasks` and record one full run (restore `raw` snapshots, run 10 to 30) as the timing baseline.

## 1. Inventory structure

- Add the source groups to `raw/hosts.yml` and split `raw/group_vars/` per source, but only for sources that have a node today (Incus, discovered). Add libvirt, Proxmox and AWS when the first node of each exists.
- Keep root-level files for dynamic inventory configs only. Plugin configs have filename rules (the AWS one must end in `aws_ec2.yml`), so `aws.yml` won't work as named.
- Add the scope note to the naming document and a short "raw has no env split, and why" note next to the inventory.

## 2. Playbook fixes from the review

- **Discovery overwriting `hosts.yml` (High):** discovery writes only to its own file (`raw/discovered.yml`) and never touches the static one.
- **Connection checks:** use `needs_python_bootstrap`, defaulting to false in `raw/group_vars/all.yml` and set true in `incus.yml`. The notes put the default in `raw/group_vars/raw.yml`, but the layout has no `raw` group.
- **Discovered hostnames:** I'd mark them provisional (for example `disc-192-168-1-10`) and rename once at onboarding, when the OS is confirmed. Probing the OS during discovery is more than a discovery step should do.
- **`firewall_rules_onboard`:** define it in `onboard/<env>/group_vars/all.yml` and comment the dependency in both converge playbooks.
- **Snapshot numbering:** state the playbook-to-snapshot alignment in the docs.

## 3. Speed settings

Apply in this order, re-profiling after each: pipelining, fact caching, forks, then `strategy: free` on 20 and 30. I'd change these parts of the document as written:

- **requiretty:** your management user is `initial`, not `ansible`, so the drop-in is `Defaults:initial !requiretty`, installed by the onboard role with `validate: visudo -cf %s`.
- **Fact cache:** move it out of `/tmp` to somewhere like `~/.ansible/fact_cache`. Flush it whenever you restore a snapshot, otherwise a node rolled back to `raw` keeps its cached facts for up to an hour.
- **`stdout_callback = yaml`:** that callback has been removed from recent community.general. Use `stdout_callback = default` with `result_format = yaml`.
- **Loops vs `include_tasks`:** this section is backwards. A looped include is slower than a looped module, so I'd drop it.
- **Forks:** 50 is harmless, but with a handful of Incus nodes it won't show in the numbers. The 5-10x claim only applies at fleet scale.
- **Mitogen:** leave it out for now. It lags ansible-core releases and you are on a current one.
- **`host_key_checking = False`:** fine in the dev phase, but flag it for revisiting before any real node.

## 4. Verify and document

For each branch: restore `raw` snapshots, run the full sequence, compare against the baseline, then update the versioned docs.

If you want, I can read the repo and turn this into a Claude Code kickoff prompt with exact file paths.