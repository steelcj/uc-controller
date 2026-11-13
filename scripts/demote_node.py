#!/usr/bin/env python3
"""Roll a host back to an earlier inventory stage.

Inverse of promote_node.py: same interface, opposite direction. On demotion
to raw, a host marked uc_origin: plugin or uc_origin: static is removed and
not written back, because raw still supplies it (through its inventory
plugin, or by hand in raw/hosts.yml). Any other host is written to the
generated raw/discovered.yml under the discovered group, keeping
ansible_host, with ansible_connection, ansible_user,
ansible_ssh_private_key_file and ansible_ssh_common_args removed. Demote a
node before onboarding it a second time, for example after a snapshot reset.
"""
import sys

from promote_node import main

if __name__ == "__main__":
    sys.exit(main("demote"))
