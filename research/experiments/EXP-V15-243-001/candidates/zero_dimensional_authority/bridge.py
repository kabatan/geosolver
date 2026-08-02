#!/usr/bin/env python3
"""Diagnostic HP dispatcher: direct replay for [], unchanged H1 otherwise.

The dispatcher reads only the endpoint arity.  The frozen direct bridge then
checks that the unchanged source also has dimension zero.  A mismatch is
rejected before any HP child is started.

Important: the direct bridge's numerical PSLQ descriptor is not exact
authority for this candidate.  Formal zero-dimensional success must call
``candidate.run_zero_dimensional_authority`` and use only its source-exact
descriptor.  This dispatcher remains solely for stored replay diagnostics.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
DIRECT_BRIDGE = (
    ROOT
    / "research/experiments/EXP-REAL61-008/"
    "hp_endpoint_bridge_v10/run_one_endpoint.py"
)
H1_BRIDGE = (
    HERE.parents[1] / "champion_v1/approved_hp_bridge.py"
)
CANDIDATE = HERE / "candidate.py"
CANDIDATE_SHA256_ENV = "GEOTARGET_ZERO_DIMENSIONAL_CANDIDATE_SHA256"


def route_endpoint_text(text: str) -> str:
    try:
        endpoint = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("endpoint must be a JSON array") from error
    if not isinstance(endpoint, list):
        raise ValueError("endpoint must be a JSON array")
    if any(
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
        for value in endpoint
    ):
        raise ValueError("endpoint coordinates must be finite numbers")
    return "ZERO_DIMENSIONAL_DIRECT" if not endpoint else "UNCHANGED_H1"


def _load_main(name: str, path: Path):
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module.main


def _zero_dimensional_preflight(
    source: Path, expected_source_sha256: str
) -> tuple[str, ...]:
    specification = importlib.util.spec_from_file_location(
        "geotarget_exp_v15_243_zero_dimensional_bridge_candidate",
        CANDIDATE,
    )
    if specification is None or specification.loader is None:
        return ("CANDIDATE_MODULE_UNAVAILABLE",)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    try:
        payload = source.read_bytes()
    except OSError:
        return ("SOURCE_UNREADABLE",)
    if hashlib.sha256(payload).hexdigest() != expected_source_sha256:
        return ("SOURCE_DIGEST_MISMATCH",)
    return module.preflight_zero_dimensional_source(
        payload, expected_source_sha256
    )


def _candidate_digest_failure(expected: str | None) -> str | None:
    if not isinstance(expected, str) or len(expected) != 64:
        return "CANDIDATE_DIGEST_AUTHORITY_MISSING"
    try:
        int(expected, 16)
    except ValueError:
        return "CANDIDATE_DIGEST_AUTHORITY_MALFORMED"
    observed = hashlib.sha256(CANDIDATE.read_bytes()).hexdigest()
    if observed != expected:
        return "CANDIDATE_DIGEST_MISMATCH"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    arguments, _ = parser.parse_known_args()
    try:
        route = route_endpoint_text(arguments.endpoint)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if route == "ZERO_DIMENSIONAL_DIRECT":
        digest_failure = _candidate_digest_failure(
            os.environ.get(CANDIDATE_SHA256_ENV)
        )
        if digest_failure is not None:
            raise SystemExit(
                "zero-dimensional preflight rejected: " + digest_failure
            )
        failures = _zero_dimensional_preflight(
            arguments.source, arguments.source_sha256
        )
        if failures:
            raise SystemExit("zero-dimensional preflight rejected: " + ",".join(failures))
        implementation = DIRECT_BRIDGE
        name = "geotarget_exp_v15_243_zero_dimensional_direct_bridge"
    else:
        implementation = H1_BRIDGE
        name = "geotarget_exp_v15_243_zero_dimensional_unchanged_h1_bridge"
    _load_main(name, implementation)()


if __name__ == "__main__":
    main()
