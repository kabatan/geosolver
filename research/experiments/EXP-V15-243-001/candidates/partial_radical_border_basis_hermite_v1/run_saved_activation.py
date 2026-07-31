#!/usr/bin/env python3
"""Truth-blind aggregate exact-activation gate over saved ordinary proposals.

This is disposable candidate-private glue.  It reads immutable source syntax,
ordinary proposal descriptors, and endpoint coordinates only.  It neither
reads nor emits case identity, truth, expected targets, per-case status, or a
formal score.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import struct
import sys
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.optimize import least_squares
import sympy as sp

from candidate import (
    CLUSTER_SEPARATION,
    MAX_EQUATIONS,
    MAX_K,
    MAX_PREDICATES,
    MAX_VARIABLES,
    SCHEMA,
    disposition,
)


CONTROL = Path("/home/kabatan/work/solver-experiment-results/formal-control-development145-180-seed0/artifacts")
TYPED_COVER = Path(
    "/home/kabatan/work/solver-wt/guided-target-ideal-membership-v1/"
    "research/experiments/EXP-V15-243-001/candidates/"
    "guided_target_typed_cover_membership_v1/typed_cover_membership.py"
)
DEDUP_RELATIVE_RADIUS = 2.0**-14
BOX_RELATIVE_HALF_WIDTH = Fraction(1, 1 << 9)
MAX_LIFT_EVALUATIONS = 500
MAX_LIFT_RESIDUAL = 1.0e-8


def _load_cover():
    name = "partial_radical_border_basis_saved_typed_cover"
    specification = importlib.util.spec_from_file_location(name, TYPED_COVER)
    if specification is None or specification.loader is None:
        raise RuntimeError("typed cover unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


COVER = _load_cover()


def _argument(command: Sequence[object], flag: str) -> str:
    values = [str(item) for item in command]
    return values[values.index(flag) + 1]


def _endpoint_sha(endpoint: Sequence[float]) -> str:
    payload = b"".join(struct.pack("<d", float(item)) for item in endpoint)
    return hashlib.sha256(payload).hexdigest()


def _plans(artifact: Path) -> tuple[Path, dict[str, tuple[float, ...]]]:
    source_path = None
    endpoints: dict[str, tuple[float, ...]] = {}
    for path in sorted(artifact.glob("reservoir-batch-*/hp/*/PLAN.json")):
        plan = json.loads(path.read_text(encoding="utf-8"))
        command, endpoint = plan.get("command"), plan.get("endpoint")
        if not isinstance(command, list) or not isinstance(endpoint, list):
            continue
        current = Path(_argument(command, "--source")).resolve()
        if source_path is None:
            source_path = current
        elif source_path != current:
            raise RuntimeError("one artifact crossed source custody")
        values = tuple(float(item) for item in endpoint)
        if not values or not all(math.isfinite(item) for item in values):
            continue
        digest = str(plan.get("endpoint_float64_sha256") or _endpoint_sha(values))
        endpoints[digest] = values
    if source_path is None:
        raise RuntimeError("source plan unavailable")
    return source_path, endpoints


def _descriptor_key(descriptor: Mapping[str, Any]) -> tuple[object, ...] | None:
    coefficients = descriptor.get("minimal_polynomial_high_to_low")
    ordinal = descriptor.get("selected_real_root_index")
    interval = descriptor.get("isolating_interval")
    if (
        not isinstance(coefficients, list)
        or not all(isinstance(item, int) and not isinstance(item, bool) for item in coefficients)
        or not isinstance(ordinal, int)
        or isinstance(ordinal, bool)
        or not isinstance(interval, Mapping)
        or not isinstance(interval.get("left"), str)
        or not isinstance(interval.get("right"), str)
    ):
        return None
    return (tuple(coefficients), ordinal, interval["left"], interval["right"])


def _proposal_groups(result: Mapping[str, Any], endpoints: Mapping[str, tuple[float, ...]]):
    groups: dict[tuple[object, ...], dict[tuple[float, ...], str]] = defaultdict(dict)
    for attempt in result.get("hp_attempts", ()):
        if not isinstance(attempt, Mapping):
            continue
        ordinary = attempt.get("ordinary_hp_proposal")
        descriptor = ordinary.get("descriptor") if isinstance(ordinary, Mapping) else None
        key = _descriptor_key(descriptor) if isinstance(descriptor, Mapping) else None
        digest = ordinary.get("endpoint_float64_sha256") if isinstance(ordinary, Mapping) else None
        if key is None or not isinstance(digest, str) or digest not in endpoints:
            continue
        groups[key][endpoints[digest]] = digest
    return groups


def _deduplicate(points: Sequence[tuple[float, ...]]) -> list[tuple[float, ...]]:
    kept = []
    for point in sorted(set(points)):
        scale = max(1.0, *(abs(item) for item in point))
        if any(
            max(abs(left - right) for left, right in zip(point, previous, strict=True))
            <= DEDUP_RELATIVE_RADIUS * max(scale, max(1.0, *(abs(item) for item in previous)))
            for previous in kept
        ):
            continue
        kept.append(point)
    return kept


def _lift_points(
    document: Mapping[str, Any],
    cover: Mapping[str, Any],
    raw_points: Sequence[tuple[float, ...]],
) -> list[tuple[float, ...]]:
    symbols = tuple(cover["symbols"])
    equations = tuple(cover["equations"])
    raw_names = document.get("variables", {}).get("names")
    if not isinstance(raw_names, list) or not all(name in {item.name for item in symbols} for name in raw_names):
        raise ValueError("raw/cover variable ledger")
    index = {symbol.name: position for position, symbol in enumerate(symbols)}
    function = sp.lambdify(symbols, [item.as_expr() for item in equations], modules="numpy")

    def residual(vector: np.ndarray) -> np.ndarray:
        return np.asarray(function(*vector), dtype=float).reshape(-1)

    lifted = []
    for raw in raw_points:
        if len(raw) != len(raw_names):
            raise ValueError("raw endpoint dimension")
        base = np.zeros(len(symbols), dtype=float)
        for name, value in zip(raw_names, raw, strict=True):
            base[index[name]] = value
        best = None
        for auxiliary_seed in (0.0, 1.0, -1.0):
            seed = base.copy()
            for name, position in index.items():
                if name not in raw_names:
                    seed[position] = auxiliary_seed
            solution = least_squares(
                residual,
                seed,
                max_nfev=MAX_LIFT_EVALUATIONS,
                ftol=1.0e-13,
                xtol=1.0e-13,
                gtol=1.0e-13,
            )
            norm = float(np.max(np.abs(residual(solution.x)), initial=0.0))
            candidate = (norm, tuple(float(item) for item in solution.x))
            if best is None or candidate < best:
                best = candidate
        if best is None or best[0] > MAX_LIFT_RESIDUAL or not all(math.isfinite(item) for item in best[1]):
            raise ValueError("cover lift failed")
        lifted.append(best[1])
    return _deduplicate(lifted)


def _predicate_kind(source: object) -> str:
    text = str(source).lower()
    if any(token in text for token in ("selector", "branch", "arc-")):
        return "branch"
    if any(token in text for token in ("defined", "denominator", "division", "sqrt", "nonzero")):
        return "definedness"
    return "guard"


def _fraction_from_float(value: float) -> Fraction:
    return Fraction.from_float(float(value))


def _problem(
    cover: Mapping[str, Any],
    descriptor_key: tuple[object, ...],
    cluster: Sequence[tuple[float, ...]],
) -> dict[str, Any]:
    coefficients, ordinal, left, right = descriptor_key
    center = cluster[0]
    box = []
    for value in center:
        middle = _fraction_from_float(value)
        width = BOX_RELATIVE_HALF_WIDTH * max(Fraction(1), abs(middle))
        box.append([str(middle - width), str(middle + width)])
    predicates = []
    counts = Counter()
    for item in cover["predicates"]:
        kind = _predicate_kind(item.get("source"))
        counts[kind] += 1
        predicates.append(
            {
                "expression": str(item["expression"]),
                "relation": str(item["relation"]),
                "kind": kind,
                "source": str(item.get("source", "")),
            }
        )
    points = [
        [[format(value, ".17g"), "0"] for value in point]
        for point in cluster
    ]
    return {
        "schema_version": SCHEMA,
        "precision_bits": 53,
        "variables": [symbol.name for symbol in cover["symbols"]],
        "equations": [str(item) for item in cover["equations"]],
        "complete_equality_ledger": True,
        "source_fibre_equality_count": len(cover["equations"]),
        "predicates": predicates,
        "complete_predicate_ledger": True,
        "predicate_ledger_count": len(predicates),
        "guard_predicate_count": counts["guard"],
        "definedness_predicate_count": counts["definedness"],
        "branch_predicate_count": counts["branch"],
        "raw_target": str(cover["target"]),
        "descriptor": {
            "minimal_polynomial_high_to_low": list(coefficients),
            "selected_real_root_index": ordinal,
            "isolating_interval": {"left": left, "right": right},
        },
        "proposal_box": box,
        "approximate_cluster": points,
        "cluster_declared_count": len(points),
        "cluster_padded": False,
        "truth_used": False,
    }


def main() -> int:
    aggregate = Counter()
    signatures = Counter()
    failure_taxonomy = Counter()
    for artifact in sorted(CONTROL.iterdir()):
        try:
            source_path, endpoint_map = _plans(artifact)
            document = json.loads(source_path.read_text(encoding="utf-8"))
            complete = COVER._compile_complete_cover(document)
            if (
                len(complete["symbols"]) > MAX_VARIABLES
                or len(complete["equations"]) > MAX_EQUATIONS
                or len(complete["predicates"]) > MAX_PREDICATES
            ):
                raise ValueError("frozen structural cap")
            result = json.loads((artifact / "RESULT.json").read_text(encoding="utf-8"))
            groups = _proposal_groups(result, endpoint_map)
            aggregate["source_cover_and_caps_ready"] += 1
        except Exception as error:
            failure_taxonomy[f"preflight:{type(error).__name__}"] += 1
            continue
        source_activated = False
        for descriptor_key, group in sorted(groups.items(), key=lambda item: repr(item[0])):
            raw_cluster = _deduplicate(list(group))
            if not 1 <= len(raw_cluster) <= MAX_K:
                failure_taxonomy["cluster-size-cap"] += 1
                continue
            try:
                lifted = _lift_points(document, complete, raw_cluster)
                if len(lifted) != len(raw_cluster):
                    raise ValueError("lift collapsed distinct cluster")
                problem = _problem(complete, descriptor_key, lifted)
                outcome = disposition(problem)
            except Exception as error:
                failure_taxonomy[f"lift-or-build:{type(error).__name__}"] += 1
                continue
            aggregate["exact_reconstruction_attempt"] += 1
            if outcome["authority"] is not True:
                reason = str(outcome.get("reason", "unknown")).split(":", 2)
                failure_taxonomy["exact:" + reason[-1].split("|")[0][:96]] += 1
                continue
            source_activated = True
            signature = json.dumps(outcome["signature"], sort_keys=True, separators=(",", ":"))
            signatures[signature] += 1
            break
        aggregate["exact_source_activation"] += int(source_activated)
    output = {
        "schema_version": "geotarget.partial-radical-border-basis-hermite-saved-activation/v1",
        "aggregate": dict(aggregate),
        "exact_activation_signature_count": len(signatures),
        "exact_activation_signature_histogram": signatures,
        "failure_taxonomy": failure_taxonomy,
        "gate": {
            "minimum_sources": 4,
            "minimum_signatures": 2,
            "pass": aggregate["exact_source_activation"] >= 4 and len(signatures) >= 2,
        },
        "individual_records_emitted": False,
        "case_identity_emitted": False,
        "truth_expected_target_outcome_used": False,
        "formal_scorer_used": False,
        "authority_released": False,
        "target_set_completeness_claim": False,
    }
    destination = Path(__file__).with_name("SAVED_ACTIVATION_RESULT.json")
    destination.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
