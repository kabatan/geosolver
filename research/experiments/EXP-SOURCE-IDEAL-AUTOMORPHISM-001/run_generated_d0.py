#!/usr/bin/env python3.12
"""Generated positive/negative/near-miss and metamorphic D0 gate."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import json
import math
import os
from pathlib import Path
from typing import Callable

import sympy as sp

from candidate import ExactSource, Predicate, PROPOSAL_STATUS, augment_baseline


HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "results" / "generated-d0.json"
BASELINE = b'{"baseline":"unchanged"}\n'


@dataclass(frozen=True)
class GeneratedCase:
    label: str
    stratum: str
    source: ExactSource
    endpoint: tuple[float, ...]
    expected: tuple[tuple[float, ...], ...]


def _source_replay(source: ExactSource) -> Callable[[tuple[float, ...]], bool]:
    symbols = tuple(sp.Symbol(name) for name in source.variables)
    equations = tuple(
        sp.sympify(text.replace("^", "**"), locals=dict(zip(source.variables, symbols)))
        for text in source.equations
    )
    predicates = tuple(
        (
            predicate.relation,
            sp.sympify(
                predicate.expression.replace("^", "**"),
                locals=dict(zip(source.variables, symbols)),
            ),
        )
        for predicate in source.predicates
    )
    bounds = source.bounds or tuple((None, None) for _ in symbols)

    def replay(point: tuple[float, ...]) -> bool:
        if len(point) != len(symbols) or any(not math.isfinite(value) for value in point):
            return False
        substitution = dict(zip(symbols, point, strict=True))
        if any(abs(float(expression.evalf(subs=substitution))) > 1.0e-9 for expression in equations):
            return False
        for (lower, upper), value in zip(bounds, point, strict=True):
            if lower is not None and value < float(lower):
                return False
            if upper is not None and value > float(upper):
                return False
        for relation, expression in predicates:
            value = float(expression.evalf(subs=substitution))
            if relation == "gt" and not value > 0.0:
                return False
            if relation == "ge" and not value >= 0.0:
                return False
            if relation == "ne" and not abs(value) > 1.0e-12:
                return False
        return True

    return replay


def _cases() -> tuple[GeneratedCase, ...]:
    symmetric = ((Fraction(-2), Fraction(2)),)
    square = ((Fraction(0), Fraction(3)), (Fraction(0), Fraction(3)))
    return (
        GeneratedCase(
            "even-sign-positive",
            "positive",
            ExactSource(("x",), ("x^2-1",), bounds=symmetric),
            (1.0,),
            ((-1.0,),),
        ),
        GeneratedCase(
            "even-sign-negative",
            "negative",
            ExactSource(("x",), ("x^2+x",), bounds=symmetric),
            (0.0,),
            (),
        ),
        GeneratedCase(
            "even-sign-guard-near-miss",
            "near-miss",
            ExactSource(
                ("x",),
                ("x^2-1",),
                (Predicate("gt", "x"),),
                symmetric,
            ),
            (1.0,),
            (),
        ),
        GeneratedCase(
            "vieta-swap-positive",
            "positive",
            ExactSource(("x", "y"), ("x+y-3", "x*y-2"), bounds=square),
            (1.0, 2.0),
            ((2.0, 1.0),),
        ),
        GeneratedCase(
            "vieta-swap-negative",
            "negative",
            ExactSource(("x", "y"), ("x+2*y-5", "x*y-2"), bounds=square),
            (1.0, 2.0),
            (),
        ),
        GeneratedCase(
            "vieta-swap-bound-near-miss",
            "near-miss",
            ExactSource(
                ("x", "y"),
                ("x+y-3", "x*y-2"),
                bounds=((Fraction(0), Fraction(3)), (Fraction(-3), Fraction(3))),
            ),
            (1.0, 2.0),
            (),
        ),
        GeneratedCase(
            "paired-sign-positive",
            "positive",
            ExactSource(
                ("x", "y"),
                ("x*y-1", "x-y"),
                bounds=(symmetric[0], symmetric[0]),
            ),
            (1.0, 1.0),
            ((-1.0, -1.0),),
        ),
        GeneratedCase(
            "paired-sign-negative",
            "negative",
            ExactSource(
                ("x", "y"),
                ("x-2", "y-1"),
                bounds=(symmetric[0], symmetric[0]),
            ),
            (2.0, 1.0),
            (),
        ),
        GeneratedCase(
            "paired-sign-guard-near-miss",
            "near-miss",
            ExactSource(
                ("x", "y"),
                ("x*y-1", "x-y"),
                (Predicate("gt", "x"),),
                (symmetric[0], symmetric[0]),
            ),
            (1.0, 1.0),
            (),
        ),
    )


def _proposal_set(values):
    return {tuple(float(component) for component in point) for point in values}


def _metamorphic_cases() -> tuple[GeneratedCase, ...]:
    return (
        GeneratedCase(
            "variable-permutation-and-rename",
            "metamorphic",
            ExactSource(
                ("v", "u"),
                ("u+v-3", "u*v-2"),
                bounds=((Fraction(0), Fraction(3)), (Fraction(0), Fraction(3))),
            ),
            (2.0, 1.0),
            ((1.0, 2.0),),
        ),
        GeneratedCase(
            "equation-permutation-and-row-scale",
            "metamorphic",
            ExactSource(
                ("x", "y"),
                ("-3*(x*y-2)", "2*(x+y-3)"),
                bounds=((Fraction(0), Fraction(3)), (Fraction(0), Fraction(3))),
            ),
            (1.0, 2.0),
            ((2.0, 1.0),),
        ),
        GeneratedCase(
            "positive-coordinate-scale",
            "metamorphic",
            ExactSource(
                ("z",),
                ("z^2-4",),
                bounds=((Fraction(-4), Fraction(4)),),
            ),
            (2.0,),
            ((-2.0,),),
        ),
    )


def main() -> int:
    if os.sched_getaffinity(0) != {14}:
        raise SystemExit("generated D0 must run only on CPU14")
    positives = 0
    negative_emissions = 0
    near_miss_emissions = 0
    false_emissions = 0
    fallback_identity = 0
    source_invalid = 0
    for case in _cases():
        replay = _source_replay(case.source)
        result = augment_baseline(
            case.source,
            accepted_endpoint=case.endpoint,
            baseline_payload=BASELINE,
            replay=replay,
        )
        fallback_identity += int(result.baseline_payload is BASELINE)
        source_invalid += result.source_invalid
        observed = _proposal_set(result.proposals)
        expected = _proposal_set(case.expected)
        false_emissions += len(observed - expected)
        if case.stratum == "positive":
            positives += int(result.status == PROPOSAL_STATUS and observed == expected)
        elif case.stratum == "negative":
            negative_emissions += len(observed)
        else:
            near_miss_emissions += len(observed)

    metamorphic_mismatches = 0
    for case in _metamorphic_cases():
        result = augment_baseline(
            case.source,
            accepted_endpoint=case.endpoint,
            baseline_payload=BASELINE,
            replay=_source_replay(case.source),
        )
        metamorphic_mismatches += int(
            result.status != PROPOSAL_STATUS
            or _proposal_set(result.proposals) != _proposal_set(case.expected)
        )

    # Deliberately simulate a compiler/canonical-replay disagreement.  The
    # route must discard the entire orbit rather than leak a partial start.
    disagreement_source = ExactSource(
        ("x",),
        ("x^2-1",),
        bounds=((Fraction(-2), Fraction(2)),),
    )
    disagreement = augment_baseline(
        disagreement_source,
        accepted_endpoint=(1.0,),
        baseline_payload=BASELINE,
        replay=lambda point: point == (1.0,),
    )
    disagreement_fail_closed = int(
        not disagreement.proposals
        and disagreement.source_invalid == 1
        and disagreement.baseline_payload is BASELINE
    )

    decision = "GO_REAL" if (
        positives == 3
        and negative_emissions == 0
        and near_miss_emissions == 0
        and false_emissions == 0
        and fallback_identity == 9
        and source_invalid == 0
        and metamorphic_mismatches == 0
        and disagreement_fail_closed == 1
    ) else "STOP_D0"
    result = {
        "schema_version": "geotarget.source-ideal-signed-automorphism-generated/v1",
        "decision": decision,
        "positive_family_gain_count": positives,
        "negative_emission_count": negative_emissions,
        "near_miss_emission_count": near_miss_emissions,
        "false_emission_count": false_emissions,
        "fallback_byte_identity_count": fallback_identity,
        "unexpected_source_invalid_count": source_invalid,
        "metamorphic_mismatch_count": metamorphic_mismatches,
        "intentional_replay_disagreement_fail_closed_count": disagreement_fail_closed,
        "truth_used_by_candidate": False,
        "case_identity_routing": False,
        "canonical_source_replay_required": True,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if decision == "GO_REAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
