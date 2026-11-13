# uc_firewall

Project role, not vendored. Applies the accumulated `firewall_rules` list that the lifecycle plays build from the stage-namespaced `firewall_rules_<stage>` lists.

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
