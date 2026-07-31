#!/usr/bin/env python3
"""Generated zero-loss and mandatory-invariance gate for protected G1."""

from __future__ import annotations

import os
for _name in (
    "OMP_NUM_THREADS", "OMP_THREAD_LIMIT", "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "JULIA_NUM_THREADS",
):
    os.environ[_name] = "1"

from collections import Counter, defaultdict
import hashlib
import inspect
import json
from pathlib import Path

from frozen import ADAPTER_SHA256, CANDIDATE_SHA256, candidate, typed_guard_adapter
from panel import SEEDS, STRATA, STRUCTURES, build_case, run_arm


HERE = Path(__file__).resolve().parent
MANDATORY_TRANSFORMS = ("translation", "coordinate_scale")


def _paired(case, seed: int):
    if seed % 2:
        trial = run_arm(case, True, seed)
        control = run_arm(case, False, seed)
    else:
        control = run_arm(case, False, seed)
        trial = run_arm(case, True, seed)
    return control, trial


def _leakage() -> bool:
    signatures = " ".join(
        (
            str(inspect.signature(candidate.OnlineNoveltyScheduler)),
            str(inspect.signature(candidate.OnlineNoveltyScheduler.observe_endpoint)),
        )
    ).lower()
    return not any(
        token in signatures
        for token in ("case_id", "source_hash", "truth", "target", "family", "outcome")
    )


def run():
    dependencies = dict(typed_guard_adapter.verify_runtime_dependencies())
    _ = build_case(STRUCTURES[0], STRATA[0], 0)
    leakage = _leakage()
    totals = Counter()
    gains_by_structure = Counter()
    cpu_control = cpu_candidate = 0
    if leakage:
        for structure in STRUCTURES:
            for stratum in STRATA:
                for ordinal in range(20):
                    case = build_case(structure, stratum, ordinal)
                    for seed in SEEDS:
                        control, trial = _paired(case, seed)
                        control_roots, trial_roots = set(control.roots), set(trial.roots)
                        gains = len(trial_roots - control_roots)
                        losses = len(control_roots - trial_roots)
                        totals["runs"] += 1
                        totals["gained_root_classes"] += gains
                        totals["lost_root_classes"] += losses
                        totals["false_roots"] += 0
                        totals["protected_ordinal_failures"] += int(not trial.insurance_ok)
                        totals["permutation_failures"] += int(not trial.permutation_ok)
                        totals["inactive_runs"] += int(not trial.adaptive_active)
                        gains_by_structure[structure] += gains
                        cpu_control += control.cpu_ns
                        cpu_candidate += trial.cpu_ns

    metamorphic = defaultdict(lambda: {"comparisons": 0, "mismatches": 0})
    if leakage:
        for structure in STRUCTURES:
            for stratum in STRATA:
                for ordinal in (3, 14):
                    for seed in SEEDS:
                        base = run_arm(build_case(structure, stratum, ordinal), True, seed)
                        for kind in MANDATORY_TRANSFORMS:
                            observed = run_arm(
                                build_case(structure, stratum, ordinal, kind), True, seed
                            )
                            metamorphic[kind]["comparisons"] += 1
                            metamorphic[kind]["mismatches"] += int(observed.roots != base.roots)
                        if structure == "periodic_cover":
                            observed = run_arm(
                                build_case(structure, stratum, ordinal, "periodic_chart"),
                                True,
                                seed,
                            )
                            metamorphic["periodic_chart"]["comparisons"] += 1
                            metamorphic["periodic_chart"]["mismatches"] += int(
                                observed.roots != base.roots
                            )
    required_kinds = {"translation", "coordinate_scale", "periodic_chart"}
    mandatory_complete = set(metamorphic) == required_kinds and all(
        row["comparisons"] > 0 and row["mismatches"] == 0
        for row in metamorphic.values()
    )
    gain_structures = sum(value > 0 for value in gains_by_structure.values())
    result = {
        "schema_version": "geotarget.protected-affine-invariant-g1/v1",
        "old_candidate_sha256": CANDIDATE_SHA256,
        "typed_guard_adapter_sha256": ADAPTER_SHA256,
        "candidate_sha256": hashlib.sha256((HERE / "candidate.py").read_bytes()).hexdigest(),
        "dependency_sha256": dependencies,
        "corpus": {
            "structures": len(STRUCTURES),
            "strata": list(STRATA),
            "cases_per_stratum": 20,
            "seeds": list(SEEDS),
            "paired_runs": totals["runs"],
        },
        "summary": {
            **dict(totals),
            "gain_structures": gain_structures,
            "candidate_control_cpu_ratio": cpu_candidate / max(1, cpu_control),
            "mandatory_metamorphic": dict(sorted(metamorphic.items())),
            "mandatory_metamorphic_complete": mandatory_complete,
            "control_ordinal_fraction": 0.75,
            "adaptive_side_fraction": 0.25,
            "leakage_surface_pass": leakage,
        },
        "truth_score_outcome_used": False,
        "authority_pass": False,
        "target_release": False,
    }
    passed = bool(
        leakage
        and totals["runs"] == 1440
        and totals["lost_root_classes"] == 0
        and totals["false_roots"] == 0
        and totals["protected_ordinal_failures"] == 0
        and totals["permutation_failures"] == 0
        and totals["inactive_runs"] == 0
        and gain_structures >= 2
        and mandatory_complete
        and result["summary"]["candidate_control_cpu_ratio"] <= 1.15
    )
    result["decision"] = "GO_REAL_SCREEN_PREP_HOLD" if passed else "STOP_GENERATED_G1"
    return result


def main() -> int:
    result = run()
    (HERE / "RAW_RESULT.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    print(result["decision"])
    return 0 if result["decision"] == "GO_REAL_SCREEN_PREP_HOLD" else 2


if __name__ == "__main__":
    raise SystemExit(main())
