# uc-controller- adding support for multi-source raw inventory and optimising for speed

## Phase 1: Naming convention v0.1.2 (no dependencies)

This is the smaller change and the naming convention is referenced by the Option A document, so it goes first.

**Changes:**

- Add the scope note about created vs discovered nodes (the paragraph from the multi-source notes about "governs what you name, not what you discover")
- Fix the three citation issues: return links after the reference text, Resources links to internal anchors not raw URLs, anchor IDs to `apa-` prefix
- Bump `dcterms:version` to `0.1.2`, update `dcterms:modified`, add changelog entry
- Rename file to `incus--instance-naming-v0.1.2.md`

**Why first:** The Option A document will cite this document by name and reference its scope note. It needs to exist in its final form before the Option A rewrite points at it.

# 

## Phase 2: Option A structural shell (depends on Phase 1)

Convert the document to full versioned-document format without touching the technical content yet.

**Changes:**

- Add frontmatter (`dc:identifier: "uc-controller--option-a-single-repo-two-concerns"`, version 0.1.4, creator, publisher, rights, the full block)
- Add version block, Abstract, Sources and Acknowledgements, License, Changelog sections
- Remove all em dashes, replace with commas or colons
- Remove horizontal rules (`---` between sections), replace with paragraph breaks
- Add CAP citations for Ansible documentation, Incus documentation, robertdebock roles, RFC 1123
- Rename file to `uc-controller--option-a-single-repo-two-concerns-v0.1.4.md`

**Why before content changes:** Getting the shell right first means the content edits land in the right sections. Doing both at once invites missing one or the other.

# 

## Phase 3: Option A content fixes (depends on Phase 2)

The functional changes from the review notes and the multi-source inventory notes.

**Changes, in order of where they appear in the document:**

1. **Overview** — Add a paragraph linking to the naming convention: instance names follow *Incus: Instance Naming*, the name identifies the OS and never changes, so `-l` limits are stable across the lifecycle. Add the scope note about created vs discovered nodes.
2. **Repository Layout tree** — Update `inventories/raw/` to show the multi-source structure: `group_vars/` with `incus.yml`, `libvirt.yml`, `proxmox.yml`, `aws.yml`, `discovered.yml`; root-level `incus.yml`, `aws.yml`, `discovered.yml` for dynamic inventory configs. Add `discovered.yml` alongside `incus.yml`.
3. **Design Principles** — Add the playbook-number ↔ snapshot-number alignment statement. Add the note about `raw/` having no env split (a raw node has no environment until onboarding assigns one).
4. **ansible.cfg** — Fold in the speed optimizations from the overview document: `forks = 50`, `pipelining = True`, the `[ssh_connection]` block with `ControlMaster` and `ControlPersist`, `strategy = linear` as the default with per-playbook overrides noted. Add the `!requiretty` sudoers note.
5. **00_discover.yml** — Change the `copy` destination from `hosts.yml` to `discovered.yml` so it doesn't overwrite static entries. Add a comment explaining the split: static entries in `hosts.yml`, generated entries in `discovered.yml`, Ansible merges both.
6. **10_onboard.yml** — Replace the negative connection-type checks with the `needs_python_bootstrap` variable pattern. Add a comment or a short paragraph after the playbook documenting the persistence model: `add_host` is in-memory for the current run, `promote_node.py` persists to disk, and `site.yml` Option 2 works because it's a single invocation. Note that separate invocations require `promote_node.py` between them.
7. **20_normalize.yml and 30_specialize.yml** — Add a comment on the `firewall_rules` var naming which file it comes from (`onboard/<env>/group_vars/all.yml`). Add `strategy: free` to both plays per the speed recommendations.
8. **Usage examples** — Replace `ex2-test*` with `deb13*` or `ubu*` per the naming convention. Add an example of the discovered-source workflow.
9. **Tradeoffs table** — Add a row on "Onboarding as the rename boundary" noting that discovered nodes may be renamed to the OS convention during onboarding, the one sanctioned rename.

# 

## Phase 4: Speed optimizations integration (depends on Phase 3)

The speed overview document is currently a standalone reference. Decide whether it stays standalone or gets folded into Option A.

**My recommendation: keep it standalone, reference it.** The speed optimizations are general Ansible knowledge, not specific to the Option A structure. Option A should cite it and apply its recommendations (which Phase 3 step 4 already does for `ansible.cfg`), but the overview document itself shouldn't be absorbed into the controller doc. It serves any Ansible project, not just this one.

**What to do:**

- Bring the speed overview to versioned-document format (frontmatter, version block, etc.) as its own v0.1.3
- Add a citation in Option A pointing to it
- Ensure the `ansible.cfg` block in Option A and the recommendations block in the speed doc agree exactly

# 

## Phase 5: Multi-source inventory notes (depends on Phase 3)

The `multi-source-raw-inventory-structure-impact-and-review-notes.md` is currently a working note. Its content gets absorbed into Option A during Phase 3 (the inventory tree, the scope note, the raw-has-no-env-split explanation). The standalone note can then be retired or kept as an ADR-style record of the decision.

**My recommendation: keep it as a decision record.** Add frontmatter, mark it as `Status: Superseded by uc-controller--option-a-single-repo-two-concerns-v0.1.4`, and leave it in the repo as history. Don't delete it; it shows the reasoning.

# 

## Sequencing summary



```
Phase 1: Naming v0.1.2 ← no dependencies
Phase 2: Option A shell ← depends on Phase 1 (cites naming doc)
Phase 3: Option A content ← depends on Phase 2
Phase 4: Speed doc v0.1.3 ← depends on Phase 3 (ansible.cfg must agree)
Phase 5: Multi-source notes ← depends on Phase 3 (content absorbed)
```

Phases 1 and 2 are mostly mechanical. Phase 3 is where the real work is. Phases 4 and 5 are cleanup.

## One open question before starting

The `incus.yml` at the `raw/` root: is it a dynamic inventory plugin config (pointing at an Incus server) or a static group definition? The answer determines whether the multi-source pattern is "one config file per source at the root" or "one group in `hosts.yml` per source." The Phase 3 inventory tree update depends on this, and I'd rather get it right than guess.