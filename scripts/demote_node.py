#!/usr/bin/env python3
"""Roll a host back to an earlier inventory stage.

Inverse of promote_node.py: same interface, opposite direction. A host
leaving the onboard stage has its connection contract (ansible_host,
ansible_connection, ansible_user, ansible_ssh_private_key_file) removed, so
it is reached through the raw inventory again. Demote a node before
onboarding it a second time, for example after a snapshot reset.
"""
import sys

from promote_node import main

if __name__ == "__main__":
    sys.exit(main("demote"))
