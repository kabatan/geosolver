#!/usr/bin/env python3.12
"""Generated D0 plus an aggregate-only pass over the frozen 108-case panel."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Iterable, Mapping

import sympy as sp

import candidate
import generated_d0
from exact_connector import rational_coordinate_descriptor


FROZEN_GENERATED = candidate.OLD_PATH.parent / "generated_cases.py"
FROZEN_GENERATED_SHA256 = "41b5fab2f941e87119ca05beda535cdb4a6b3d4c7b283c0cffcc525bb373ef84"
FROZEN_VERIFIER_BRIDGE = candidate.OLD_PATH.parent / "verifier_bridge.py"
FROZEN_VERIFIER_BRIDGE_SHA256 = "5e874298618eb273e2c81f795cdd22a507b72920aedec7cd26a88b3ba4e05f74"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sum_work(values: Iterable[Mapping[str, int]]) -> dict[str, int]:
    total: Counter[str] = Counter()
    for value in values:
        total.update({str(key): int(count) for key, count in value.items()})
    return dict(sorted(total.items()))


def _coordinates(batch) -> tuple[tuple[sp.Rational, ...], ...]:
    return tuple(
        sorted(
            tuple(sp.Rational(sp.sympify(text)) for text in item.exact_coordinates)
            for item in batch.candidates
        )
    )


def _envelope(document):
    return candidate.canonical_proposal_envelope(generated_d0.source_projection(document))


def _load_frozen_generated():
    if _sha(FROZEN_GENERATED) != FROZEN_GENERATED_SHA256:
        raise RuntimeError("frozen 108-case generated panel changed")
    if _sha(FROZEN_VERIFIER_BRIDGE) != FROZEN_VERIFIER_BRIDGE_SHA256:
        raise RuntimeError("frozen generated-panel verifier bridge changed")
    saved = sys.modules.get("candidate")
    saved_bridge = sys.modules.get("verifier_bridge")
    frozen_directory = str(FROZEN_GENERATED.parent)
    sys.modules["candidate"] = candidate.OLD
    sys.path.insert(0, frozen_directory)
    try:
        specification = importlib.util.spec_from_file_location(
            "geotarget_single_prime_hensel_frozen_generated", FROZEN_GENERATED
        )
        if specification is None or specification.loader is None:
            raise RuntimeError("cannot load frozen 108-case generated panel")
        module = importlib.util.module_from_spec(specification)
        sys.modules[specification.name] = module
        specification.loader.exec_module(module)
        bridge = sys.modules.get("verifier_bridge")
        if (
            bridge is None
            or Path(bridge.__file__).resolve() != FROZEN_VERIFIER_BRIDGE.resolve()
            or _sha(Path(bridge.__file__)) != FROZEN_VERIFIER_BRIDGE_SHA256
        ):
            raise RuntimeError("generated-panel verifier bridge identity changed")
        return module
    finally:
        if not sys.path or sys.path[0] != frozen_directory:
            raise RuntimeError("frozen generated-panel import path changed")
        del sys.path[0]
        if saved is None:
            del sys.modules["candidate"]
        else:
            sys.modules["candidate"] = saved
        if saved_bridge is None:
            sys.modules.pop("verifier_bridge", None)
        else:
            sys.modules["verifier_bridge"] = saved_bridge


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise SystemExit("refusing existing D0 output")

    records = []
    new_work = []
    old_work = []
    new_cpu = 0.0
    old_cpu = 0.0
    for case in generated_d0.cases():
        envelope = _envelope(case.document)
        sp.core.cache.clear_cache()
        new = candidate.propose(envelope)
        sp.core.cache.clear_cache()
        old = candidate.OLD.propose(envelope, "padic_hensel_proposal")
        observed = _coordinates(new)
        expected = tuple(sorted(case.expected))
        passed = observed == expected
        records.append(
            {
                "name": case.name,
                "category": case.category,
                "expected_candidate_count": len(expected),
                "candidate_count": len(observed),
                "pass": passed,
                "selected_prime_count": int(new.work.get("selected_prime_count", 0)),
                "tuple_stability_pass_count": int(new.work.get("tuple_stability_pass_count", 0)),
                "exact_substitution_pass_count": int(new.work.get("exact_substitution_pass_count", 0)),
                "proposal_authority": new.proposal_authority,
                "release": new.release,
            }
        )
        new_work.append(new.work)
        old_work.append(old.work)
        new_cpu += new.elapsed_cpu_seconds
        old_cpu += old.elapsed_cpu_seconds

    base = candidate.propose(_envelope(generated_d0.cases()[2].document))
    reversed_batch = candidate.propose(_envelope(generated_d0.reversed_pair_document()))
    permuted = candidate.propose(_envelope(generated_d0.permuted_pair_document()))
    base_values = _coordinates(base)
    reversed_values = _coordinates(reversed_batch)
    permuted_back = tuple(sorted(tuple(reversed(values)) for values in _coordinates(permuted)))
    metamorphic = {
        "constraint_permutation": base_values == reversed_values,
        "variable_permutation": base_values == permuted_back,
    }

    frozen_generated = _load_frozen_generated()
    census_work = []
    census_candidate_count = 0
    good_prime_count = 0
    stable_tuple_source_count = 0
    exact_substitution_source_count = 0
    census_cpu = 0.0
    frozen_cases = frozen_generated.generated_cases()
    for case in frozen_cases:
        sp.core.cache.clear_cache()
        batch = candidate.propose(case.proposal_envelope())
        census_work.append(batch.work)
        census_candidate_count += len(batch.candidates)
        good_prime_count += int(batch.work.get("selected_prime_count", 0) > 0)
        stable_tuple_source_count += int(batch.work.get("tuple_stability_pass_count", 0) > 0)
        exact_substitution_source_count += int(batch.work.get("exact_substitution_pass_count", 0) > 0)
        census_cpu += batch.elapsed_cpu_seconds

    new_totals = _sum_work(new_work)
    old_totals = _sum_work(old_work)
    old_prime_attempts = old_totals.get("cycle1_prime_attempt_count", 0)
    old_lift_steps = old_totals.get("cycle1_hensel_lift_step_count", 0)
    result = {
        "schema_version": "geotarget.single-prime-stable-hensel-coordinates-v2-d0/v1",
        "status": "D0_PASS" if all(item["pass"] for item in records) and all(metamorphic.values()) else "D0_FAIL",
        "mechanism": candidate.boundary_manifest(),
        "generated": {
            "case_count": len(records),
            "positive_count": sum(item["category"] == "positive" for item in records),
            "singular_negative_count": sum(item["category"] == "singular" for item in records),
            "nonrational_negative_count": sum(item["category"] == "nonrational" for item in records),
            "unstable_negative_count": sum(item["category"] == "unstable" for item in records),
            "pass_count": sum(item["pass"] for item in records),
            "false_proposal_authority_count": sum(item["proposal_authority"] for item in records),
            "release_count": sum(item["release"] for item in records),
            "metamorphic": metamorphic,
            "records": records,
        },
        "old_comparison_same_generated_cases": {
            "new_cpu_seconds": new_cpu,
            "old_cpu_seconds": old_cpu,
            "new_to_old_cpu_ratio": new_cpu / old_cpu if old_cpu else None,
            "new_work": new_totals,
            "old_work": old_totals,
            "prime_attempt_reduction_fraction": (
                1.0 - new_totals.get("prime_attempt_count", 0) / old_prime_attempts
                if old_prime_attempts else None
            ),
            "lift_step_reduction_fraction": (
                1.0 - new_totals.get("hensel_digit_step_count", 0) / old_lift_steps
                if old_lift_steps else None
            ),
            "old_cross_prime_branch_pairs": old_totals.get("cycle2_crt_branch_pair_count", 0),
            "new_cross_prime_branch_pairs": new_totals.get("cross_prime_cartesian_pair_count", 0),
            "old_crt_coordinate_reconstructions": old_totals.get(
                "cycle2_rational_reconstruction_attempt_count", 0
            ),
            "new_stable_tuple_reconstruction_pairs": new_totals.get(
                "tuple_reconstruction_pair_count", 0
            ),
        },
        "outcome_blind_frozen_108_census": {
            "panel_sha256": FROZEN_GENERATED_SHA256,
            "source_count": len(frozen_cases),
            "deterministic_good_prime_source_count": good_prime_count,
            "stable_rational_tuple_source_count": stable_tuple_source_count,
            "exact_substitution_source_count": exact_substitution_source_count,
            "proposal_candidate_count": census_candidate_count,
            "cpu_seconds": census_cpu,
            "work": _sum_work(census_work),
            "case_level_output_emitted": False,
            "truth_target_outcome_input": False,
        },
        "linear_coordinate_descriptor_probe": rational_coordinate_descriptor(sp.Rational(-2, 3)),
        "qqbar_terminal_executed": False,
        "target_hp_lanes_supplied_to_hensel_candidate": False,
    }
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "status": result["status"],
        "cpu_ratio": result["old_comparison_same_generated_cases"]["new_to_old_cpu_ratio"],
        "frozen_108": result["outcome_blind_frozen_108_census"],
    }, sort_keys=True))
    return 0 if result["status"] == "D0_PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
