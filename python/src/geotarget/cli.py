"""Command-line entry point for protocol authoring and validation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from geotarget import __version__
from geotarget.canonical import canonical_hash, canonical_json
from geotarget.validation import (
    SCHEMA_FILES,
    ProtocolValidationError,
    load_and_validate,
)


def _validate(args: argparse.Namespace) -> int:
    requested = None if args.schema == "auto" else str(args.schema)
    try:
        document, version = load_and_validate(
            Path(args.path),
            schema=requested,
            schemas=Path(args.schema_dir) if args.schema_dir is not None else None,
        )
    except (OSError, ValueError, ProtocolValidationError) as exc:
        print(f"validation failed: {exc}", file=sys.stderr)
        return 2
    print(
        canonical_json(
            {
                "content_hash": canonical_hash(document),
                "schema_version": version,
                "valid": True,
            }
        )
    )
    return 0


def _build_info(_args: argparse.Namespace) -> int:
    print(
        canonical_json(
            {
                "julia_execution": "unsupported_not_wired",
                "package": "geotarget",
                "schemas": sorted(SCHEMA_FILES),
                "version": __version__,
            }
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="geotarget")
    parser.add_argument("--version", action="version", version=__version__)
    subcommands = parser.add_subparsers(dest="command")

    validate = subcommands.add_parser("validate", help="validate a GeoTarget JSON document")
    validate.add_argument("path")
    validate.add_argument(
        "--schema",
        choices=("auto", "problem", "plugin-manifest", "solve-options", "solve-result"),
        default="auto",
    )
    validate.add_argument("--schema-dir", default=None)
    validate.set_defaults(handler=_validate)

    info = subcommands.add_parser("build-info", help="show protocol/client capabilities")
    info.set_defaults(handler=_build_info)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 0
    return int(handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
