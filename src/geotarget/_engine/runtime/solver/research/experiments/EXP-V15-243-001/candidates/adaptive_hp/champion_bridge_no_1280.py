#!/usr/bin/env python3
"""Authenticated adaptive-HP bridge with the fresh 1280 lane removed."""

from __future__ import annotations

from bridge_contract import run_bridge
from transitive_manifest import ARM_NO_1280


if __name__ == "__main__":
    run_bridge(ARM_NO_1280)
