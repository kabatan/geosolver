"""Evaluate a GeoSolver IR JSON file from the command line."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from geosolver.autosolve import run_ir


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GeoSolver on an IR JSON file.")
    parser.add_argument("ir_file", type=Path, help="Path to an IR JSON file.")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print result metadata when available.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    ir_text = args.ir_file.read_text(encoding="utf-8")
    result = run_ir(ir_text)

    payload = {
        "success": getattr(result, "success", False),
        "status": getattr(getattr(result, "status", None), "value", getattr(result, "status", None)),
        "value": str(getattr(result, "value", "")),
        "metadata": getattr(result, "metadata", {}),
    }
    indent = 2 if args.pretty else None
    print(json.dumps(payload, ensure_ascii=False, indent=indent, default=str))
    return 0 if payload["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
