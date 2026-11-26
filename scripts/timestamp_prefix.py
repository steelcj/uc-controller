#!/usr/bin/env python3
"""Print a timestamp prefix such as 2026-11-12--12:45:36- (local time)."""
from datetime import datetime

print(datetime.now().strftime("%Y-%m-%d--%H:%M:%S-"), end="")
