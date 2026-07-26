"""Run a suffix of the frozen 256-start proposal packet without regenerating it."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from dataclasses import replace
from pathlib import Path


def _load(path: Path):
    specification = importlib.util.spec_from_file_location(
        "geotarget_product_resumed_frozen_search", path
    )
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--seconds", type=float, required=True)
    parser.add_argument("--start-offset", type=int, required=True)
    parser.add_argument("--callbacks-remaining", type=int, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if not 0 <= arguments.start_offset < 256 or not 0 < arguments.seconds <= 146:
        raise SystemExit("invalid frozen search suffix")

    search = _load(arguments.worker.resolve())
    base = search.BASE
    original_prefix = base.build_literal_prefix

    def suffix_prefix(*args, **kwargs):
        prefix = original_prefix(*args, **kwargs)
        return replace(prefix, points=prefix.points[arguments.start_offset :])

    base.build_literal_prefix = suffix_prefix
    base.PROCESS_STARTED = time.monotonic()
    sys.argv = [
        str(arguments.worker),
        "--case",
        str(arguments.source.resolve()),
        "--case-sha256",
        arguments.source_sha256,
        "--arm",
        "precision_isolated_retained_then_strict_nearroot_restart_direct_broyden_ruiz_tr_lm",
        "--seconds",
        str(arguments.seconds),
        "--starts",
        "256",
        "--callbacks-per-start",
        "600",
        "--aggregate-callback-cap",
        str(arguments.callbacks_remaining),
        "--seed",
        str(arguments.seed),
        "--output",
        str(arguments.output.resolve()),
    ]
    base.main()

    artifact = json.loads(arguments.output.read_text(encoding="utf-8"))
    for endpoint in artifact.get("endpoints", []):
        if isinstance(endpoint, dict) and isinstance(endpoint.get("lane"), int):
            endpoint["lane"] += arguments.start_offset
    for key in ("validated_endpoint_lanes", "safe_endpoint_lanes"):
        values = artifact.get(key)
        if isinstance(values, list):
            artifact[key] = [value + arguments.start_offset for value in values]
    artifact["resume"] = {
        "start_offset": arguments.start_offset,
        "proposal_packet_regenerated_from_frozen_seed": True,
        "proposal_prefix_skipped": arguments.start_offset,
        "new_starts": int(artifact.get("work", {}).get("lanes_started", 0)),
    }
    arguments.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
