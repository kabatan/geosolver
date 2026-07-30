#!/usr/bin/env python3
"""Aggregate-only dynamic gate CLI for charged observation pools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Mapping

from candidate import dynamic_gate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pool", type=Path, action="append", required=True)
    arguments = parser.parse_args()
    records = []
    for path in arguments.pool:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise SystemExit("pool is not an object")
        records.append(value)
    print(json.dumps(dynamic_gate(records), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
