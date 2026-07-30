"""Generated source-only D0 for the local-box Krawczyk rescue."""

from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import candidate

TOTAL_WORK = 16
POSITIVE_FAMILIES = (
    "well_conditioned_1d",
    "coupled_2d",
    "nearly_singular_2d",
)


@dataclass(frozen=True)
class GeneratedCase:
    family: str
    source: candidate.TypedLocalSource
    near: candidate.NearRoot
    exact_roots: tuple[tuple[float, ...], ...]
    baseline_root_indices: tuple[int, ...]


def _descriptor(point: tuple[float, ...]) -> str:
    return "R:" + ",".join(f"{value:.12g}" for value in point)


def _case(family: str, replicate: int) -> GeneratedCase:
    if family == "well_conditioned_1d":
        x = candidate.Var(0)
        root = 1.25 + 0.05 * replicate
        roots = ((-root,), (root,))
        return GeneratedCase(
            family,
            candidate.TypedLocalSource((x**2 - root**2,), 1),
            candidate.NearRoot((root + 1.0e-5,), 0.05),
            roots,
            (0,),
        )
    if family == "coupled_2d":
        x, y = candidate.Var(0), candidate.Var(1)
        left = 1.0 + 0.05 * replicate
        right = 2.0 + 0.03 * replicate
        roots = ((left, right), (right, left))
        return GeneratedCase(
            family,
            candidate.TypedLocalSource(
                (x + y - (left + right), x * y - left * right), 2
            ),
            candidate.NearRoot((right + 1.0e-6, left - 1.0e-6), (0.02, 0.02)),
            roots,
            (0,),
        )
    if family == "nearly_singular_2d":
        x, y = candidate.Var(0), candidate.Var(1)
        epsilon = 1.0e-5 * (1 + replicate / 20)
        root = (1.0 + 0.02 * replicate, 2.0 - 0.01 * replicate)
        return GeneratedCase(
            family,
            candidate.TypedLocalSource(
                (
                    x + y - sum(root),
                    x + (1.0 + epsilon) * y - (root[0] + (1.0 + epsilon) * root[1]),
                ),
                2,
            ),
            candidate.NearRoot((root[0] + 1.0e-10, root[1] - 1.0e-10), 1.0e-4),
            (root,),
            (),
        )
    raise ValueError(family)


def _authority(
    roots: tuple[tuple[float, ...], ...],
    *,
    map_back=lambda point: point,
):
    def accept(
        point: tuple[float, ...], enclosure: tuple[tuple[float, float], ...]
    ) -> str | None:
        mapped = tuple(float(value) for value in map_back(point))
        matches = [
            root
            for root in roots
            if len(root) == len(mapped)
            and max(abs(left - right) for left, right in zip(root, mapped, strict=True))
            <= 2.0e-6
        ]
        if len(matches) != 1:
            return None
        # The generated authority stands in for unchanged HP/source/guard/raw
        # target replay. It is not imported by the candidate.
        if len(enclosure) != len(point) or any(
            not lo <= value <= hi
            for value, (lo, hi) in zip(point, enclosure, strict=True)
        ):
            return None
        return _descriptor(matches[0])

    return accept


def _run_case(case: GeneratedCase) -> dict[str, object]:
    baseline = tuple(
        _descriptor(case.exact_roots[index]) for index in case.baseline_root_indices
    )
    payload = json.dumps(baseline, separators=(",", ":")).encode()
    observed = candidate.rescue(
        case.source,
        near_roots=(case.near,),
        baseline_payload=payload,
        baseline_descriptors=baseline,
        total_work=TOTAL_WORK,
        canonical_accept=_authority(case.exact_roots),
    )
    authority = {_descriptor(root) for root in case.exact_roots}
    proposed = set(observed.descriptors)
    return {
        "result": observed,
        "baseline": set(baseline),
        "proposed": proposed,
        "authority": authority,
        "payload_match": observed.baseline_payload == payload,
        "work_match": observed.baseline_work == 12 and observed.side_work == 4,
    }


def _negative_cases() -> tuple[
    tuple[str, candidate.TypedLocalSource, candidate.NearRoot], ...
]:
    x = candidate.Var(0)
    return (
        (
            "singular_midpoint",
            candidate.TypedLocalSource((x**2,), 1),
            candidate.NearRoot((0.0,), 0.05),
        ),
        (
            "strict_guard_boundary",
            candidate.TypedLocalSource(
                (x - 1.0,), 1, strict_guard_state_on_local_box="boundary"
            ),
            candidate.NearRoot((1.0,), 0.05),
        ),
        (
            "unsupported_non_polynomial",
            candidate.TypedLocalSource((candidate.unsupported("sin", x),), 1),
            candidate.NearRoot((0.0,), 0.05),
        ),
        (
            "opaque_fallback",
            candidate.TypedLocalSource((x - 1.0,), 1, opaque_callbacks=True),
            candidate.NearRoot((1.0,), 0.05),
        ),
        (
            "far_from_root",
            candidate.TypedLocalSource((x**2 - 2.0,), 1),
            candidate.NearRoot((0.0,), 0.05),
        ),
    )


def _metamorphic() -> dict[str, object]:
    x, y = candidate.Var(0), candidate.Var(1)
    roots = ((2.0, 1.0), (1.0, 2.0))
    baseline = (_descriptor(roots[0]),)
    payload = b"opaque-baseline\x00"

    def execute(source, near, map_back=lambda point: point):
        result = candidate.rescue(
            source,
            near_roots=(near,),
            baseline_payload=payload,
            baseline_descriptors=baseline,
            total_work=TOTAL_WORK,
            canonical_accept=_authority(roots, map_back=map_back),
        )
        return result.descriptors, result.baseline_payload == payload

    base = execute(
        candidate.TypedLocalSource((x + y - 3.0, x * y - 2.0), 2),
        candidate.NearRoot((1.0, 2.0), 0.02),
    )
    y0, x1 = candidate.Var(0), candidate.Var(1)
    variable_permutation = execute(
        candidate.TypedLocalSource((x1 + y0 - 3.0, x1 * y0 - 2.0), 2),
        candidate.NearRoot((2.0, 1.0), 0.02),
        lambda point: (point[1], point[0]),
    )
    x, y = candidate.Var(0), candidate.Var(1)
    residual_permutation = execute(
        candidate.TypedLocalSource((x * y - 2.0, x + y - 3.0), 2),
        candidate.NearRoot((1.0, 2.0), 0.02),
    )
    residual_scale = execute(
        candidate.TypedLocalSource((-3.0 * (x + y - 3.0), 0.25 * (x * y - 2.0)), 2),
        candidate.NearRoot((1.0, 2.0), 0.02),
    )
    u, v = candidate.Var(0), candidate.Var(1)
    coordinate_scale = execute(
        candidate.TypedLocalSource((2.0 * u + 0.5 * v - 3.0, u * v - 2.0), 2),
        candidate.NearRoot((0.5, 4.0), (0.01, 0.04)),
        lambda point: (2.0 * point[0], 0.5 * point[1]),
    )
    variants = {
        "variable_permutation": variable_permutation,
        "residual_permutation": residual_permutation,
        "residual_scale": residual_scale,
        "coordinate_scale": coordinate_scale,
    }
    mismatches = sum(value[0] != base[0] for value in variants.values())
    payload_mismatches = sum(not value[1] for value in variants.values())
    return {
        "checks": len(variants),
        "descriptor_mismatches": mismatches,
        "payload_mismatches": payload_mismatches,
        "families": list(variants),
    }


def run() -> dict[str, object]:
    aggregate: Counter[str] = Counter()
    families = {name: Counter() for name in POSITIVE_FAMILIES}
    for family in POSITIVE_FAMILIES:
        for replicate in range(10):
            observed = _run_case(_case(family, replicate))
            result = observed["result"]
            gains = observed["proposed"] - observed["baseline"]
            losses = observed["baseline"] - observed["proposed"]
            false = observed["proposed"] - observed["authority"]
            for row in (aggregate, families[family]):
                row["cases"] += 1
                row["activation_cases"] += int(bool(gains))
                row["descriptor_gains"] += len(gains)
                row["descriptor_losses"] += len(losses)
                row["false_or_extra"] += len(false)
                row["certified_boxes"] += result.certified_boxes
                row["canonical_rejections"] += result.canonical_rejections
                row["payload_mismatch"] += int(not observed["payload_match"])
                row["work_split_mismatch"] += int(not observed["work_match"])

    negatives = []
    for label, source, near in _negative_cases():
        result = candidate.rescue(
            source,
            near_roots=(near,),
            baseline_payload=b"baseline\x00",
            baseline_descriptors=("baseline",),
            total_work=TOTAL_WORK,
            canonical_accept=lambda _point, _box: "unexpected",
        )
        negatives.append(
            {
                "label": label,
                "candidate_additions": len(result.descriptors) - 1,
                "baseline_preserved": result.descriptors == ("baseline",),
                "reason": result.reason,
            }
        )

    metamorphic = _metamorphic()
    improved_families = sum(
        families[name]["descriptor_gains"] > 0
        and families[name]["descriptor_losses"] == 0
        for name in POSITIVE_FAMILIES
    )
    passed = all(
        (
            aggregate["descriptor_losses"] == 0,
            aggregate["false_or_extra"] == 0,
            aggregate["payload_mismatch"] == 0,
            aggregate["work_split_mismatch"] == 0,
            improved_families >= 3,
            all(row["candidate_additions"] == 0 for row in negatives),
            all(row["baseline_preserved"] for row in negatives),
            metamorphic["descriptor_mismatches"] == 0,
            metamorphic["payload_mismatches"] == 0,
        )
    )
    return {
        "schema": "geotarget.exp-local-krawczyk-001-generated-d0/v1",
        "formal_run": False,
        "truth_scorer_case_outcome_or_holdout_read": False,
        "policy": {
            "baseline_fraction": candidate.BASELINE_FLOOR,
            "baseline_work": candidate.split_work(TOTAL_WORK)[0],
            "side_work": candidate.split_work(TOTAL_WORK)[1],
            "global_subdivision": False,
            "proposal_authority": False,
            "canonical_source_guard_raw_target_acceptance_unchanged": True,
        },
        "aggregate": dict(aggregate),
        "by_family": {name: dict(row) for name, row in families.items()},
        "negative_and_near_miss": negatives,
        "metamorphic": metamorphic,
        "gate": {"passed": passed, "improved_positive_families": improved_families},
    }


def main() -> None:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["gate"]["passed"] else 1)


if __name__ == "__main__":
    main()
