#!/usr/bin/env python3
"""Generated D0/adversary for the proper Morse/polar image certificate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import sympy as sp

from candidate import (
    CertificateRejected,
    Component,
    Source,
    boundary_manifest,
    certify,
    ideal_intersection,
)


HERE = Path(__file__).resolve().parent
x, y = sp.symbols("x y", real=True)


def descriptor_polynomials(certificate):
    return {item.minpoly_coefficients_high_to_low for item in certificate.descriptors}


def plural_lines():
    equation = x**2 - 1
    return Source((x, y), (equation,), (Component((equation,)),), x)


def isolated_plus_circle(*, reverse=False):
    circle = Component((x**2 + y**2 - 1,))
    isolated = Component((x, y))
    components = (isolated, circle) if reverse else (circle, isolated)
    equations = ideal_intersection(tuple(item.equations for item in components), (x, y))
    return Source((x, y), equations, components, x**2 + y**2)


def strict_open_constant(*, complete=True):
    s = sp.Symbol("s", real=True)
    return Source(
        (x,), (), (Component(()),), sp.Integer(7),
        strict_positive=(x,), strict_slacks=(s,) if complete else (),
    )


def disequality_open_constant(*, complete=True):
    u = sp.Symbol("u", real=True)
    return Source(
        (x,), (), (Component(()),), sp.Integer(3),
        disequalities=(x,), disequality_slacks=(u,) if complete else (),
    )


def nodal_constant():
    equation = y**2 - x**2 * (x + 1)
    return Source((x, y), (equation,), (Component((equation,)),), sp.Integer(0))


def rejection_reason(source):
    try:
        certify(source)
    except CertificateRejected as error:
        return str(error)
    return "ACCEPTED"


def run():
    checks = []
    records = {}

    plural = certify(plural_lines())
    records["plural"] = {
        "descriptor_polynomials": sorted(map(list, descriptor_polynomials(plural))),
        "smooth_localizations": plural.smooth_localization_count,
    }
    checks.append((
        "positive-plural-finite-image",
        descriptor_polynomials(plural) == {(1, -1), (1, 1)},
    ))

    union = certify(isolated_plus_circle())
    union_permuted = certify(isolated_plus_circle(reverse=True))
    records["isolated_plus_circle"] = {
        "descriptor_polynomials": sorted(map(list, descriptor_polynomials(union))),
        "component_count": union.component_count,
        "singular_recursions": union.singular_recursion_count,
    }
    checks.append((
        "positive-singular-isolated-plus-circle",
        descriptor_polynomials(union) == {(1, 0), (1, -1)},
    ))
    checks.append((
        "metamorphic-component-order",
        union.descriptors == union_permuted.descriptors,
    ))

    opened = certify(strict_open_constant())
    records["strict_open"] = {
        "descriptor_polynomials": sorted(map(list, descriptor_polynomials(opened))),
        "chart_equations": opened.exact_chart_equation_count,
    }
    checks.append((
        "positive-strict-open-constant-target",
        descriptor_polynomials(opened) == {(1, -7)} and opened.exact_chart_equation_count == 1,
    ))

    disequality = certify(disequality_open_constant())
    records["disequality_open"] = {
        "descriptor_polynomials": sorted(map(list, descriptor_polynomials(disequality))),
        "chart_equations": disequality.exact_chart_equation_count,
    }
    checks.append((
        "positive-disequality-inverse-slack-constant-target",
        descriptor_polynomials(disequality) == {(1, -3)}
        and disequality.exact_chart_equation_count == 1,
    ))

    node = certify(nodal_constant())
    records["nodal"] = {
        "descriptor_polynomials": sorted(map(list, descriptor_polynomials(node))),
        "singular_recursions": node.singular_recursion_count,
    }
    checks.append((
        "positive-recursive-zero-dimensional-singular-locus",
        descriptor_polynomials(node) == {(1, 0)} and node.singular_recursion_count == 1,
    ))

    circle = x**2 + y**2 - 1
    circle_x_reason = rejection_reason(
        Source((x, y), (circle,), (Component((circle,)),), x)
    )
    records["circle_target_x_rejection"] = circle_x_reason
    checks.append((
        "mandatory-negative-circle-target-x",
        circle_x_reason == "TARGET_DIFFERENTIAL_NONZERO_ON_SMOOTH_STRATUM",
    ))

    nonradical_reason = rejection_reason(
        Source((x,), (x**2,), (Component((x**2,)),), sp.Integer(0))
    )
    checks.append(("negative-nonradical", nonradical_reason == "NONRADICAL_COMPONENT"))

    unsupported_reason = rejection_reason(
        Source((x,), (), (Component(()),), sp.sin(x))
    )
    checks.append((
        "negative-unsupported-expression",
        unsupported_reason == "UNSUPPORTED_NONPOLYNOMIAL_SOURCE",
    ))

    incomplete_chart_reason = rejection_reason(strict_open_constant(complete=False))
    checks.append((
        "negative-incomplete-strict-chart",
        incomplete_chart_reason == "INCOMPLETE_EXACT_CHARTS",
    ))

    incomplete_disequality_reason = rejection_reason(
        disequality_open_constant(complete=False)
    )
    checks.append((
        "negative-incomplete-disequality-chart",
        incomplete_disequality_reason == "INCOMPLETE_EXACT_CHARTS",
    ))

    union_source = isolated_plus_circle()
    incomplete_cover_reason = rejection_reason(
        Source(
            union_source.variables,
            union_source.equations,
            union_source.components[:1],
            union_source.target,
        )
    )
    checks.append((
        "negative-incomplete-component-cover",
        incomplete_cover_reason == "INCOMPLETE_OR_INCORRECT_COMPONENT_COVER",
    ))

    checks.append((
        "authority-boundary",
        not plural.proposal_authority
        and not plural.release
        and plural.existing_canonical_source_guard_branch_raw_target_replay_required,
    ))
    return {
        "schema_version": "geotarget.proper-morse-polar-target-image-d0/v1",
        "candidate_sha256": hashlib.sha256((HERE / "candidate.py").read_bytes()).hexdigest(),
        "passed": sum(int(ok) for _name, ok in checks),
        "total": len(checks),
        "checks": [{"name": name, "passed": ok} for name, ok in checks],
        "records": records,
        "boundary": boundary_manifest(),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
