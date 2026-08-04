#!/usr/bin/env python3
"""Backward-compatible entry point for the exhaustive audit.

The original seven-row smoke audit is intentionally no longer used.  Keep
this filename because it was referenced in the first artifact, but delegate
to ``manual_scope_audit.py`` so rerunning an old command cannot restore the
incorrect total of seven.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in rows), encoding="utf-8")


def main() -> None:
    from manual_scope_audit import main as exhaustive_main
    exhaustive_main()


if __name__ == "__main__":
    main()
