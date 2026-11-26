# uc_firewall

Project role, not vendored, and interim: uc-controller is switching to `steelcj.foomuuri`, the firewall uc-node's nodes arrive with (see `ROADMAP.md`). Applies the accumulated `firewall_rules` list that `shared/vars/uc_firewall_interim.yml` builds from the client inventory's per-stage firewall values: `firewall_onboard_ssh`, `firewall_normalize_services` and `firewall_specialize_services`, already shaped for `steelcj.foomuuri`.

## Rule schema

```yaml
firewall_rules:
  - name: allow-ssh        # required, used as the rule comment
    port: 22               # required
    protocol: tcp          # optional, default tcp
    source: 10.0.0.0/24    # optional; a rule without source is open to all addresses
```

## Behaviour

- Backend per OS family, the same one `robertdebock.firewall` installed: ufw on the Debian family (Debian, Ubuntu), firewalld on the Red Hat family.
- Before anything is enabled, the role asserts that the list contains a TCP rule for the SSH port in use (`uc_firewall_ssh_port`, default `ansible_port` or 22) and fails with a clear message if it does not.
- Allow rules are applied first, then the default policy (deny incoming, allow outgoing), then the firewall is enabled.
- Additive: rules missing from the list are not removed.

Requires `community.general` (ufw) and `ansible.posix` (firewalld), and gathered facts.
