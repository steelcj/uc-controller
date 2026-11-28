# Changelog

## 0.1.2 (2026-11-22)

Documentation only, no change to the role's behaviour.

- Added the Molecule testing guide, `en/docs/guides/manual-testing/molecule-incus-testing-v0.1.0.md`, and a session record of the role's design and testing, `en/docs/sessions/2026-11-22--16-40-00-foomuuri-role-session-v0.1.0.md`.
- README: removed the claim that the example is tested on each push, pull request and release, since there is no CI yet. Linked the testing guide and the roadmap, and added a table of test results, starting with the passing run of 0.1.1 on Incus `images:debian/13`.
- ROADMAP: added a Next section, with a converge case for `ssh saddr …` on port 22, Foomuuri's full list of conflicting firewalls, an empty cleanup playbook, publishing and tagging, and a LICENSE file. Added CI to If needed.

## 0.1.1 (2026-11-22)

- A public zone given no interfaces gets `foomuuri_public_interfaces`, calculated from the installed version: the catch-all `*` on Foomuuri 0.33 or later, and `eth* en* wl*` before that. Foomuuri before 0.33 passes `*` to nftables as a literal name, which nftables refuses, as on Debian 13.
- The verify step checks that the public zone matches the installed version.

## 0.1.0 (2026-11-22)

- First version: installs Foomuuri, removes ufw and firewalld, masks `nftables.service`, and writes one fragment calculated from `foomuuri_ssh_port`, `foomuuri_ssh_sources`, `foomuuri_services`, `foomuuri_base_services` and `foomuuri_outgoing`, with advanced settings for further fragments, purging, the `foomuuri` section, zones, raw rules, macros, iplists, templates and extra files.
- Runs `foomuuri check` before any change is loaded.
- Molecule scenario against an Incus `images:debian/13` system container.
