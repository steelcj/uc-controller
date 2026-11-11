#!/usr/bin/env python3
"""Roll a host back to an earlier inventory stage.

Inverse of promote_node.py: same interface, opposite direction.
"""
import sys

from promote_node import main

if __name__ == "__main__":
    sys.exit(main("demote"))
