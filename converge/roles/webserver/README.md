# webserver

Project role, not vendored. The smallest role that exercises the specialize stage: it installs nginx, enables and starts it, and serves a one-line page that names the host.

## Behaviour

- Debian family (Debian, Ubuntu) and Red Hat family nodes. Any other OS family fails with a clear message.
- The page is `index.html` in the distribution's default document root: `/var/www/html` on the Debian family, `/usr/share/nginx/html` on the Red Hat family. Its content is the inventory name of the host.
- The role does not open any port. HTTP is opened at the specialize layer as inventory data, `firewall_rules_specialize` in `inventories/normalized/<env>/group_vars/webservers.yml`, which `30_specialize.yml` combines with the earlier layers and applies with `uc_firewall`.

No TLS, no virtual hosts, no templated site configuration.

Run it through the specialize stage:

```sh
ansible-playbook -i inventories/raw -i inventories/onboard/dev -i inventories/normalized/dev \
  converge/playbooks/30_specialize.yml -l deb13 -e specialize_role=webserver
```
