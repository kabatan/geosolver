#!/usr/bin/env python3.12
"""Deterministic synthetic D0 for source derivative-energy transport."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import resource
import time

import numpy as np
import sympy as sp

from prototype import (
    derivative_energy_certificate,
    directional_energy,
    fixed_quarter_portfolio,
    gaussian_monomial_moment,
    standardized_residuals,
    transport_direction,
    transport_start_or_baseline,
    try_derivative_energy_certificate,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _close(left, right, tolerance=1e-11) -> bool:
    return bool(np.allclose(left, right, atol=tolerance, rtol=tolerance))


def run() -> dict[str, object]:
    started = time.perf_counter()
    x, y = sp.symbols("x y")

    rotated = derivative_energy_certificate([x + y], (x, y))
    baseline = np.array([1.0, 0.0])
    proposal = transport_direction(baseline, rotated.matrix)
    positive = {
        "certificate_verified": rotated.verify(),
        "radius_preserved": bool(
            abs(np.linalg.norm(proposal) - np.linalg.norm(baseline)) < 1e-12
        ),
        "strong_direction_energy_reduced": directional_energy(
            proposal, rotated.matrix
        ) < directional_energy(baseline, rotated.matrix),
    }

    isotropic = derivative_energy_certificate([x, y], (x, y))
    isotropic_proposal = transport_direction(np.array([0.6, -0.8]), isotropic.matrix)
    negative = {
        "isotropic_direction_unchanged": _close(isotropic_proposal, [0.6, -0.8]),
        "opaque_nonpolynomial_falls_back": try_derivative_energy_certificate(
            [sp.sin(x)], (x,)
        )
        is None,
    }

    scaled = derivative_energy_certificate([7 * (x + y)], (x, y))
    permutation = derivative_energy_certificate([y + x], (y, x))
    affine_variables, affine_residuals = standardized_residuals(
        [(x - 12) / 2 + (y + 2) / 4],
        (x, y),
        ((sp.Rational(10), sp.Rational(14)), (sp.Rational(-6), sp.Rational(2))),
    )
    affine = derivative_energy_certificate(affine_residuals, affine_variables)
    metamorphic = {
        "row_scale_invariant": bool(scaled.matrix == rotated.matrix),
        "variable_permutation_equivariant": bool(
            permutation.matrix
            == sp.ImmutableMatrix(
                [
                    [rotated.matrix[1, 1], rotated.matrix[1, 0]],
                    [rotated.matrix[0, 1], rotated.matrix[0, 0]],
                ]
            )
        ),
        "affine_unit_standardization_invariant": bool(
            affine.matrix == rotated.matrix
        ),
    }

    guarded, accepted = transport_start_or_baseline(
        baseline=[0.8, 0.0],
        center=[0.0, 0.0],
        scales=[1.0, 1.0],
        matrix=rotated.matrix,
        accept=lambda candidate: bool(candidate[1] >= 0),
    )
    guard_fallback = not accepted and _close(guarded, [0.8, 0.0])

    baseline_starts = [np.array([1.0, 0.0]) for _ in range(8)]
    portfolio, transported, fallbacks = fixed_quarter_portfolio(
        baseline_starts,
        lambda item: transport_start_or_baseline(
            item,
            center=[0.0, 0.0],
            scales=[1.0, 1.0],
            matrix=rotated.matrix,
            accept=lambda _candidate: True,
        ),
    )
    portfolio_check = {
        "baseline_untouched_count": sum(
            _close(candidate, baseline_starts[index])
            for index, candidate in enumerate(portfolio)
            if index % 4 != 3
        ),
        "transported_count": transported,
        "fallback_count": fallbacks,
        "fixed_75_25": transported == 2 and fallbacks == 0,
    }

    tampered_matrix = sp.MutableDenseMatrix(rotated.matrix)
    tampered_matrix[0, 0] += 1
    tampered = replace(
        rotated, matrix=sp.ImmutableMatrix(tampered_matrix)
    )
    exactness = {
        "gaussian_E_x6_y2": gaussian_monomial_moment((6, 2)) == 15,
        "tampered_certificate_rejected": not tampered.verify(),
    }
    all_checks = [
        *positive.values(),
        *negative.values(),
        *metamorphic.values(),
        guard_fallback,
        portfolio_check["fixed_75_25"],
        *exactness.values(),
    ]
    elapsed = time.perf_counter() - started
    prototype_path = Path(__file__).with_name("prototype.py")
    return {
        "schema_version": "geotarget.source-analytic-derivative-energy-d0/v1",
        "candidate": "SOURCE_ANALYTIC_DERIVATIVE_ENERGY_TRANSPORT_START_V1",
        "aggregate": {
            "check_count": len(all_checks),
            "pass_count": sum(bool(value) for value in all_checks),
            "all_pass": all(bool(value) for value in all_checks),
            "positive": positive,
            "negative": negative,
            "metamorphic": metamorphic,
            "guard_failure_baseline_fallback": guard_fallback,
            "portfolio": portfolio_check,
            "exactness": exactness,
        },
        "mechanism": {
            "baseline_quota": "3/4",
            "transport_quota": "1/4",
            "radius_preserving": True,
            "ridge": "trace(C)/n",
            "target_used": False,
            "score_used": False,
            "feedback_used": False,
        },
        "safety": {
            "false_authority": 0,
            "authority": False,
            "release": False,
        },
        "timing_seconds": elapsed,
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "prototype_sha256": _sha256(prototype_path),
        "cpu_affinity": sorted(os.sched_getaffinity(0)),
    }


def main() -> int:
    result = run()
    output = Path(__file__).with_name("D0_RESULT.json")
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0 if result["aggregate"]["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
