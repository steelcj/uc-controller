#!/usr/bin/env python3
"""Roll a host back to an earlier inventory stage.

Inverse of promote_node.py: same interface, opposite direction. Demotion is
inventory bookkeeping: it lets the inventory follow a node after a snapshot
restore, and has nothing to do with making onboarding repeatable.

- Demotion to raw removes the host's entry from the source stage and writes
  nothing under inventories/raw/. The node reappears in raw through its
  source: the Incus plugin lists a running instance, a hand-entered host
  never left raw/hosts.yml, and a scanned host is found by the next scan.
- Demotion from normalized to onboard moves the entry back.
"""
import sys

from promote_node import main

if __name__ == "__main__":
    sys.exit(main("demote"))
