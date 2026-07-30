#!/usr/bin/env python3
"""Generated, exact-replay D0 for coefficient monodromy proposals."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from fractions import Fraction
import json
from pathlib import Path
import sys
from typing import Iterable

import sympy


HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import candidate  # noqa: E402


POSITIVE_FAMILIES = ("separated", "affine_scaled", "close_roots")
COUNTER_FAMILIES = ("strict_bound", "repeated_root", "complex_sheet")
DEGREES = (2, 4, 6)
REPLICATES = 10
TOTAL_WORK = 64_000


@dataclass(frozen=True)
class GeneratedCase:
    family: str
    degree: int
    replicate: int
    source: candidate.PolynomialSource
    accepted_start: Fraction


def _multiply_linear(
    coefficients: tuple[Fraction, ...], root: Fraction
) -> tuple[Fraction, ...]:
    result = [Fraction(0)] * (len(coefficients) + 1)
    for index, coefficient in enumerate(coefficients):
        result[index] += coefficient
        result[index + 1] -= coefficient * root
    return tuple(result)


def _polynomial_from_roots(roots: Iterable[Fraction]) -> tuple[Fraction, ...]:
    coefficients = (Fraction(1),)
    for root in roots:
        coefficients = _multiply_linear(coefficients, root)
    return coefficients


def _roots(family: str, degree: int, replicate: int) -> tuple[Fraction, ...]:
    shift = Fraction(replicate - 5, 17)
    centered = tuple(Fraction(2 * index - degree + 1) for index in range(degree))
    if family == "separated" or family == "strict_bound":
        return tuple(root + shift for root in centered)
    if family == "affine_scaled":
        scale = Fraction(2 + replicate % 3, 3)
        return tuple(scale * root + shift for root in centered)
    if family == "close_roots":
        return tuple(shift + Fraction(index, 32) for index in range(degree))
    if family == "repeated_root":
        distinct = tuple(shift + Fraction(index) for index in range(degree - 1))
        return (*distinct, distinct[-1])
    raise ValueError(family)


def _case(family: str, degree: int, replicate: int) -> GeneratedCase:
    if family == "complex_sheet":
        real_roots = (Fraction(replicate - 5, 13),)
        coefficients = _polynomial_from_roots(real_roots)
        # Add the exact irreducible factor x^2 + 1.
        expanded = [Fraction(0)] * (len(coefficients) + 2)
        for index, value in enumerate(coefficients):
            expanded[index] += value
            expanded[index + 2] += value
        source = candidate.PolynomialSource(tuple(expanded), True)
        return GeneratedCase(family, 3, replicate, source, real_roots[0])

    roots = _roots(family, degree, replicate)
    lower = None
    upper = None
    if family == "strict_bound":
        lower = roots[0] - 1
        upper = (roots[0] + roots[1]) / 2
    source = candidate.PolynomialSource(
        _polynomial_from_roots(roots),
        family != "repeated_root",
        lower,
        upper,
    )
    return GeneratedCase(family, degree, replicate, source, roots[0])


def _sympy_poly(source: candidate.PolynomialSource) -> sympy.Poly:
    variable = sympy.Symbol("x")
    expression = sum(
        sympy.Rational(value.numerator, value.denominator)
        * variable ** (source.degree - index)
        for index, value in enumerate(source.coefficients_high_to_low)
    )
    return sympy.Poly(expression, variable, domain=sympy.QQ)


def _canonical_rational_roots(
    source: candidate.PolynomialSource,
) -> tuple[Fraction, ...]:
    roots = sympy.polys.polytools.ground_roots(_sympy_poly(source))
    return tuple(
        sorted(
            (
                Fraction(int(root.p), int(root.q))
                for root in roots
                if (
                    (source.lower_bound is None or Fraction(root) > source.lower_bound)
                    and (
                        source.upper_bound is None
                        or Fraction(root) < source.upper_bound
                    )
                )
            )
        )
    )


def _exact_replay(
    source: candidate.PolynomialSource,
    proposal: complex,
    exact_roots: tuple[Fraction, ...],
) -> str | None:
    if abs(proposal.imag) > 1.0e-7:
        return None
    matches = [root for root in exact_roots if abs(float(root) - proposal.real) <= 2.0e-6]
    if len(matches) != 1:
        return None
    root = matches[0]
    value = Fraction(0)
    for coefficient in source.coefficients_high_to_low:
        value = value * root + coefficient
    if value != 0:
        raise AssertionError("exact source replay failed")
    return f"Q:{root.numerator}/{root.denominator}"


def _run_case(case: GeneratedCase) -> dict[str, object]:
    baseline_work, side_work = candidate.split_work(TOTAL_WORK)
    exact_roots = _canonical_rational_roots(case.source)
    start_descriptor = _exact_replay(
        case.source, complex(float(case.accepted_start)), exact_roots
    )
    if start_descriptor is None:
        raise AssertionError("generated baseline start failed canonical replay")
    control_union = frozenset((start_descriptor,))

    route = candidate.discover(
        case.source,
        accepted_start=float(case.accepted_start),
        side_work_cap=side_work,
    )
    proposals = {
        descriptor
        for proposal in route.proposals
        if (descriptor := _exact_replay(case.source, proposal, exact_roots))
        is not None
    }
    candidate_union = control_union.union(proposals)
    if not control_union <= candidate_union:
        raise AssertionError("candidate suppressed baseline descriptor")

    # Both arms are charged the identical total. Unused monodromy work is
    # deterministic source-evaluation filler and has no proposal authority.
    candidate_filler = side_work - route.charged_work
    if candidate_filler < 0:
        raise AssertionError("side route exceeded its work cap")
    control_work = baseline_work + side_work
    candidate_work = baseline_work + route.charged_work + candidate_filler
    authority = frozenset(f"Q:{root.numerator}/{root.denominator}" for root in exact_roots)
    return {
        "control": control_union,
        "candidate": candidate_union,
        "authority": authority,
        "eligible": route.eligible,
        "reason": route.reason,
        "loops_attempted": route.loops_attempted,
        "loops_completed": route.loops_completed,
        "tracker_failures": route.tracker_failures,
        "control_work": control_work,
        "candidate_work": candidate_work,
        "canonical_replay_rejections": len(route.proposals) - len(proposals),
    }


def _scaled_source(source: candidate.PolynomialSource) -> candidate.PolynomialSource:
    scale = Fraction(-7, 3)
    return candidate.PolynomialSource(
        tuple(scale * value for value in source.coefficients_high_to_low),
        source.square_free_certificate,
        source.lower_bound,
        source.upper_bound,
    )


def run() -> dict[str, object]:
    aggregate: Counter[str] = Counter()
    family_rows = {
        family: Counter() for family in (*POSITIVE_FAMILIES, *COUNTER_FAMILIES)
    }
    metamorphic_checks = 0

    cases: list[GeneratedCase] = []
    for family in (*POSITIVE_FAMILIES, "strict_bound", "repeated_root"):
        for degree in DEGREES:
            for replicate in range(REPLICATES):
                cases.append(_case(family, degree, replicate))
    for replicate in range(REPLICATES):
        cases.append(_case("complex_sheet", 3, replicate))

    for case in cases:
        observed = _run_case(case)
        control = observed["control"]
        proposed = observed["candidate"]
        authority = observed["authority"]
        if not all(isinstance(value, frozenset) for value in (control, proposed, authority)):
            raise AssertionError("generated set contract changed")
        gained = proposed - control
        lost = control - proposed
        false_or_extra = proposed - authority
        for row in (aggregate, family_rows[case.family]):
            row["cases"] += 1
            row["eligible_cases"] += int(bool(observed["eligible"]))
            row["activation_cases"] += int(bool(gained))
            row["descriptor_gains"] += len(gained)
            row["descriptor_losses"] += len(lost)
            row["strict_gain_cases"] += int(bool(gained))
            row["loss_cases"] += int(bool(lost))
            row["control_complete_sets"] += int(control == authority)
            row["candidate_complete_sets"] += int(proposed == authority)
            row["false_or_extra"] += len(false_or_extra)
            row["canonical_replay_rejections"] += int(
                observed["canonical_replay_rejections"]
            )
            row["loops_attempted"] += int(observed["loops_attempted"])
            row["loops_completed"] += int(observed["loops_completed"])
            row["tracker_failures"] += int(observed["tracker_failures"])
            row["work_mismatch"] += int(
                observed["control_work"] != observed["candidate_work"]
            )

        if case.family in POSITIVE_FAMILIES:
            transformed = GeneratedCase(
                case.family,
                case.degree,
                case.replicate,
                _scaled_source(case.source),
                case.accepted_start,
            )
            scaled = _run_case(transformed)
            if scaled["candidate"] != proposed:
                raise AssertionError("equation scaling changed canonical proposal set")
            metamorphic_checks += 1

    improved_families = sum(
        family_rows[family]["descriptor_gains"] > 0
        and family_rows[family]["descriptor_losses"] == 0
        for family in POSITIVE_FAMILIES
    )
    result: dict[str, object] = {
        "schema": "geotarget.exp-coefficient-monodromy-001-generated-d0/v1",
        "formal_run": False,
        "formal_truth_used": False,
        "truth_source": "generated_exact_replay_only",
        "holdout_used": False,
        "case_results_persisted": False,
        "policy": {
            "id": candidate.POLICY_ID,
            "route": "exact rational square-free univariate degree 2..8",
            "baseline_fraction": candidate.BASELINE_FLOOR,
            "total_work_per_arm_case": TOTAL_WORK,
            "baseline_work": candidate.split_work(TOTAL_WORK)[0],
            "side_work": candidate.split_work(TOTAL_WORK)[1],
            "proposal_authority": False,
            "canonical_exact_source_replay_required": True,
            "completeness_claim": False,
        },
        "generated_panel": {
            "positive_families": list(POSITIVE_FAMILIES),
            "counter_families": list(COUNTER_FAMILIES),
            "degrees": list(DEGREES),
            "replicates": REPLICATES,
        },
        "aggregate": dict(aggregate),
        "by_family": {
            family: dict(family_rows[family]) for family in family_rows
        },
        "metamorphic": {
            "checks": metamorphic_checks,
            "failures": 0,
            "transform": "nonzero rational equation scaling",
        },
    }
    result["gate"] = {
        "passed": all(
            (
                aggregate["descriptor_losses"] == 0,
                aggregate["false_or_extra"] == 0,
                aggregate["work_mismatch"] == 0,
                aggregate["descriptor_gains"] > 0,
                improved_families >= 2,
                metamorphic_checks
                == len(POSITIVE_FAMILIES) * len(DEGREES) * REPLICATES,
            )
        ),
        "improved_positive_families": improved_families,
        "status": candidate.UNKNOWN_STATUS,
    }
    return result


def main() -> None:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["gate"]["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
