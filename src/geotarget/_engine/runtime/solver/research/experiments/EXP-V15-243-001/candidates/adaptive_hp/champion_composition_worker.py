#!/usr/bin/env python3
"""CLI-compatible adaptive HP worker for champion_v0's frozen bridge."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import signal
import struct
import sys
import threading
import time
from typing import Iterator, Mapping, Sequence


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
ADAPTER_PATH = HERE / "adapter.py"
CHAMPION_ADAPTER_PATH = HERE / "champion_adapter.py"
MANIFEST_PATH = HERE / "transitive_manifest.py"
CHAMPION_COMPAT_PATH = (
    ROOT
    / "research/experiments/EXP-V15-243-001/champion_v0/"
    "hp_semantic_compat.py"
)
GEOSOLVER_SOURCE = ROOT.parent / "geosolver/src"
ATOMIC_WRITE_RESERVE_SECONDS = 0.15

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if GEOSOLVER_SOURCE.is_dir() and str(GEOSOLVER_SOURCE) not in sys.path:
    # The frozen endpoint bridge intentionally uses solver/python's interpreter
    # while champion semantic parity lives in the sibling geosolver package.
    sys.path.insert(0, str(GEOSOLVER_SOURCE))

from research.infrastructure.memory_safety.safe_subprocess import (  # noqa: E402
    atomic_write_json,
)


def _load(name: str, path: Path):
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    specification = importlib.util.spec_from_file_location(name, path)
    if specification is None or specification.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _endpoint_sha256(endpoint: Sequence[float]) -> str:
    payload = struct.pack(">I", len(endpoint)) + b"".join(
        struct.pack(">d", float(value)) for value in endpoint
    )
    return hashlib.sha256(payload).hexdigest()


@contextmanager
def _worker_soft_deadline(seconds: float) -> Iterator[None]:
    if seconds <= 0.0 or not math.isfinite(seconds):
        raise TimeoutError("nonpositive worker soft budget")
    if threading.current_thread() is not threading.main_thread():
        raise TimeoutError("worker soft deadline requires the main thread")

    def expire(_signum, _frame):
        raise TimeoutError("adaptive HP worker soft deadline exceeded")

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, expire)
    previous_timer = signal.setitimer(signal.ITIMER_REAL, seconds)
    started = time.monotonic()
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0.0)
        signal.signal(signal.SIGALRM, previous_handler)
        previous_delay, previous_interval = previous_timer
        if previous_delay > 0.0:
            elapsed = time.monotonic() - started
            signal.setitimer(
                signal.ITIMER_REAL,
                max(1.0e-6, previous_delay - elapsed),
                previous_interval,
            )


def _minimal_fail_closed(
    *,
    source_sha256: str,
    endpoint: Sequence[float],
    deadline_seconds: float,
    primary_cap_seconds: float,
    elapsed_seconds: float,
    reason: str,
    arm: str | None,
    expected_closure: str | None,
    observed_closure: str | None,
) -> dict[str, object]:
    endpoint_sha256 = _endpoint_sha256(endpoint)
    final = {
        "status": "ADAPTIVE_HP_FAIL_CLOSED",
        "authority_pass": False,
        "failure_reasons": [reason],
        "source_raw_sha256": source_sha256,
        "endpoint_float64_sha256": endpoint_sha256,
        "input_contract": {
            "source_bytes_and_digest": True,
            "bare_float64_endpoint": True,
            "truth": False,
            "known_target_count": False,
            "case_id": False,
            "family": False,
        },
        "problem_transformations": {
            "source_mutated": False,
            "bounds_added": False,
            "coordinate_fixing_or_gauge": False,
            "symmetry_reduction": False,
            "constraint_or_answer_changed": False,
        },
        "authority_scope": {
            "numerical_configuration_512_768": True,
            "target_512_768_1024": True,
            "original_dsl_hp_replay": True,
            "target_only_owned_pslq": True,
            "minimal_polynomial_and_isolator": True,
            "all_coordinate_exactification_required": False,
            "exact_configuration_witness_required": False,
            "target_image_completeness_required": False,
        },
    }
    return {
        "schema_version": "geotarget.exp008-target-first-fallback-composition/v1",
        "status": "ADAPTIVE_HP_FAIL_CLOSED",
        "authority_pass": False,
        "winner": None,
        "final_result": final,
        "attempts": [],
        "fallback_decision": {
            "primary_authority_failed": False,
            "remaining_budget_sufficient": False,
            "fallback_eligible": False,
            "fallback_enabled": False,
            "case_identity_read": False,
            "family_read": False,
            "truth_read": False,
            "known_target_count_read": False,
            "failure_status_subtype_read": False,
        },
        "input_contract": {
            "same_source_bytes_both_attempts": True,
            "same_float64_endpoint_both_attempts": True,
            "source_or_problem_modified": False,
            "bounds_added": False,
            "gauge_or_symmetry_reduction": False,
        },
        "deadline_seconds": float(deadline_seconds),
        "primary_cap_seconds": float(primary_cap_seconds),
        "elapsed_seconds": elapsed_seconds,
        "adaptive_hp_bridge": {
            "failure_reason": reason,
            "case_family_truth_or_known_target_count_routing": False,
            "transitive_manifest_verification": {
                "arm": arm,
                "closure_sha256": observed_closure,
                "expected_closure_sha256": expected_closure,
                "verified_before_backend_load": False,
                "verified_before_artifact_write": False,
            },
        },
    }


def _parse_endpoint(text: str) -> list[float]:
    value = json.loads(text)
    if not isinstance(value, list):
        raise argparse.ArgumentTypeError("endpoint must be a JSON array")
    endpoint: list[float] = []
    for coordinate in value:
        if isinstance(coordinate, bool) or not isinstance(
            coordinate, (int, float)
        ):
            raise argparse.ArgumentTypeError(
                "endpoint coordinates must be numeric"
            )
        converted = float(coordinate)
        if not math.isfinite(converted):
            raise argparse.ArgumentTypeError(
                "endpoint coordinates must be finite"
            )
        endpoint.append(converted)
    if not endpoint:
        raise argparse.ArgumentTypeError("endpoint must be nonempty")
    return endpoint


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--endpoint", type=_parse_endpoint, required=True)
    parser.add_argument("--deadline-seconds", type=float, default=23.0)
    parser.add_argument("--primary-cap-seconds", type=float, default=23.0)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()

    if (
        not math.isfinite(arguments.deadline_seconds)
        or not math.isfinite(arguments.primary_cap_seconds)
        or arguments.deadline_seconds <= 0.0
        or arguments.primary_cap_seconds <= 0.0
        or arguments.primary_cap_seconds > arguments.deadline_seconds
    ):
        raise SystemExit("invalid adaptive HP deadline")

    worker_started = time.monotonic()
    manifest_module = None
    verified_manifest: Mapping[str, object] | None = None
    adapter = None
    config = None
    arm = os.environ.get("GEOTARGET_ADAPTIVE_HP_TRANSITIVE_ARM")
    expected_closure = os.environ.get(
        "GEOTARGET_ADAPTIVE_HP_TRANSITIVE_CLOSURE_SHA256"
    )
    observed_closure = None
    outer_budget = arguments.deadline_seconds - ATOMIC_WRITE_RESERVE_SECONDS
    try:
        with _worker_soft_deadline(outer_budget):
            manifest_module = _load(
                "geotarget_exp_v15_243_adaptive_hp_worker_manifest",
                MANIFEST_PATH,
            )
            verified_manifest = manifest_module.verify_environment(os.environ)
            observed_closure = str(verified_manifest["closure_sha256"])

            adapter = _load(
                "geotarget_exp_v15_243_adaptive_hp_champion_adapter",
                CHAMPION_ADAPTER_PATH,
            )
            config = adapter.BridgeConfig.from_environment(os.environ)
            expected_fresh = (
                arm == manifest_module.ARM_WITH_1280
            )
            if config.enable_fresh_1280 is not expected_fresh:
                raise ValueError("ablation configuration does not match manifest arm")

            implementation = _load(
                "geotarget_exp_v15_243_adaptive_hp_implementation",
                ADAPTER_PATH,
            )
            compatibility = _load(
                "geotarget_exp_v15_243_adaptive_hp_champion_compatibility",
                CHAMPION_COMPAT_PATH,
            )
            compatibility.install_hp_semantic_compatibility()
            prelude_elapsed = time.monotonic() - worker_started
            remaining = arguments.deadline_seconds - prelude_elapsed
            if remaining <= ATOMIC_WRITE_RESERVE_SECONDS:
                raise TimeoutError("HP prelude exhausted the soft deadline")
            result = adapter.run_champion_adapter(
                implementation,
                arguments.source.read_bytes(),
                arguments.source_sha256,
                arguments.endpoint,
                deadline_seconds=remaining,
                primary_cap_seconds=min(
                    arguments.primary_cap_seconds,
                    remaining,
                ),
                config=config,
                enforce_posix_alarm=False,
            )
            post_manifest = manifest_module.build_manifest(str(arm))
            if (
                post_manifest["closure_sha256"]
                != verified_manifest["closure_sha256"]
            ):
                raise manifest_module.ManifestError(
                    "transitive implementation changed during execution"
                )
            result["adaptive_hp_bridge"]["effective_adapter_deadline_seconds"] = (
                result["deadline_seconds"]
            )
            result["adaptive_hp_bridge"]["transitive_implementation_manifest"] = (
                verified_manifest
            )
            result["adaptive_hp_bridge"]["transitive_manifest_verification"] = {
                "arm": arm,
                "closure_sha256": verified_manifest["closure_sha256"],
                "expected_closure_sha256": expected_closure,
                "verified_before_backend_load": True,
                "verified_before_artifact_write": True,
            }
            result["deadline_seconds"] = arguments.deadline_seconds
            result["primary_cap_seconds"] = arguments.primary_cap_seconds
            result["elapsed_seconds"] = time.monotonic() - worker_started
    except Exception as error:
        if isinstance(error, TimeoutError):
            reason = "SOFT_DEADLINE_EXCEEDED"
        elif manifest_module is not None and isinstance(
            error, manifest_module.ManifestError
        ):
            reason = "TRANSITIVE_MANIFEST_MISMATCH"
        elif isinstance(error, ValueError):
            reason = "INVALID_ABLATION_CONFIGURATION"
        else:
            reason = f"WORKER_EXCEPTION_{type(error).__name__.upper()}"

        post_verified = False
        if manifest_module is not None and verified_manifest is not None:
            try:
                post_manifest = manifest_module.build_manifest(str(arm))
                post_verified = bool(
                    post_manifest["closure_sha256"]
                    == verified_manifest["closure_sha256"]
                )
            except Exception:
                post_verified = False
        if adapter is not None and config is not None:
            result = adapter.fail_closed_composition(
                adapter,
                source_sha256=arguments.source_sha256,
                endpoint=arguments.endpoint,
                elapsed_seconds=time.monotonic() - worker_started,
                deadline_seconds=arguments.deadline_seconds,
                primary_cap_seconds=arguments.primary_cap_seconds,
                config=config,
                reason=reason,
            )
            result["adaptive_hp_bridge"]["transitive_manifest_verification"] = {
                "arm": arm,
                "closure_sha256": observed_closure,
                "expected_closure_sha256": expected_closure,
                "verified_before_backend_load": verified_manifest is not None,
                "verified_before_artifact_write": post_verified,
            }
        else:
            result = _minimal_fail_closed(
                source_sha256=arguments.source_sha256,
                endpoint=arguments.endpoint,
                deadline_seconds=arguments.deadline_seconds,
                primary_cap_seconds=arguments.primary_cap_seconds,
                elapsed_seconds=time.monotonic() - worker_started,
                reason=reason,
                arm=arm,
                expected_closure=expected_closure,
                observed_closure=observed_closure,
            )
            result["adaptive_hp_bridge"]["transitive_manifest_verification"] = {
                "arm": arm,
                "closure_sha256": observed_closure,
                "expected_closure_sha256": expected_closure,
                "verified_before_backend_load": verified_manifest is not None,
                "verified_before_artifact_write": post_verified,
            }
        if verified_manifest is not None:
            result["adaptive_hp_bridge"]["transitive_implementation_manifest"] = (
                verified_manifest
            )

    implementation_sha256 = {
        "portfolio_adapter": _sha256(ADAPTER_PATH),
        "champion_adapter": _sha256(CHAMPION_ADAPTER_PATH),
        "champion_semantic_compatibility": _sha256(CHAMPION_COMPAT_PATH),
        "composition_worker": _sha256(Path(__file__).resolve()),
        "transitive_manifest": _sha256(MANIFEST_PATH),
    }
    result["adaptive_hp_bridge"]["implementation_sha256"] = (
        implementation_sha256
    )
    if manifest_module is not None and verified_manifest is not None:
        try:
            final_manifest = manifest_module.build_manifest(str(arm))
            final_write_verified = bool(
                final_manifest["closure_sha256"]
                == verified_manifest["closure_sha256"]
            )
        except Exception:
            final_write_verified = False
        if not final_write_verified:
            result = _minimal_fail_closed(
                source_sha256=arguments.source_sha256,
                endpoint=arguments.endpoint,
                deadline_seconds=arguments.deadline_seconds,
                primary_cap_seconds=arguments.primary_cap_seconds,
                elapsed_seconds=time.monotonic() - worker_started,
                reason="TRANSITIVE_MANIFEST_MISMATCH",
                arm=arm,
                expected_closure=expected_closure,
                observed_closure=observed_closure,
            )
            result["adaptive_hp_bridge"]["transitive_manifest_verification"] = {
                "arm": arm,
                "closure_sha256": observed_closure,
                "expected_closure_sha256": expected_closure,
                "verified_before_backend_load": True,
                "verified_before_artifact_write": False,
            }
            result["adaptive_hp_bridge"][
                "transitive_implementation_manifest"
            ] = verified_manifest
            result["adaptive_hp_bridge"]["implementation_sha256"] = (
                implementation_sha256
            )
    atomic_write_json(arguments.output, result)


if __name__ == "__main__":
    main()
