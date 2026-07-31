from __future__ import annotations

from dataclasses import replace
import unittest

import numpy as np
import sympy as sp

from prototype import (
    derivative_energy_certificate,
    directional_energy,
    fixed_quarter_portfolio,
    gaussian_expectation,
    gaussian_monomial_moment,
    standardized_residuals,
    transport_direction,
    transport_start_or_baseline,
    try_derivative_energy_certificate,
)


class SourceDerivativeEnergyTest(unittest.TestCase):
    def test_exact_gaussian_moments_and_tamper(self) -> None:
        x, y = sp.symbols("x y")
        polynomial = sp.Poly(x**4 * y**2 + 3 * x**2, x, y, domain=sp.QQ)
        self.assertEqual(gaussian_monomial_moment((6, 2)), 15)
        self.assertEqual(gaussian_expectation(polynomial), 6)
        certificate = derivative_energy_certificate([x + y], (x, y))
        self.assertTrue(certificate.verify())
        changed = sp.MutableDenseMatrix(certificate.matrix)
        changed[0, 0] += 1
        self.assertFalse(replace(certificate, matrix=sp.ImmutableMatrix(changed)).verify())

    def test_rotated_positive_and_isotropic_negative(self) -> None:
        x, y = sp.symbols("x y")
        rotated = derivative_energy_certificate([x + y], (x, y))
        baseline = np.array([1.0, 0.0])
        proposal = transport_direction(baseline, rotated.matrix)
        self.assertAlmostEqual(np.linalg.norm(proposal), np.linalg.norm(baseline))
        self.assertLess(
            directional_energy(proposal, rotated.matrix),
            directional_energy(baseline, rotated.matrix),
        )
        isotropic = derivative_energy_certificate([x, y], (x, y))
        baseline = np.array([0.6, -0.8])
        np.testing.assert_allclose(transport_direction(baseline, isotropic.matrix), baseline)

    def test_negative_fallbacks_and_fixed_quarter(self) -> None:
        x, y = sp.symbols("x y")
        self.assertIsNone(try_derivative_energy_certificate([sp.sin(x)], (x,)))
        matrix = derivative_energy_certificate([x + y], (x, y)).matrix
        baseline = np.array([0.8, 0.0])
        guarded, accepted = transport_start_or_baseline(
            baseline,
            center=[0.0, 0.0],
            scales=[1.0, 1.0],
            matrix=matrix,
            accept=lambda candidate: bool(candidate[1] >= 0),
        )
        self.assertFalse(accepted)
        np.testing.assert_array_equal(guarded, baseline)
        starts = [np.array([1.0, 0.0]) for _ in range(8)]
        result, transported, fallbacks = fixed_quarter_portfolio(
            starts,
            lambda item: transport_start_or_baseline(
                item, [0, 0], [1, 1], matrix, lambda _candidate: True
            ),
        )
        self.assertEqual((transported, fallbacks), (2, 0))
        for index in (0, 1, 2, 4, 5, 6):
            np.testing.assert_array_equal(result[index], starts[index])

    def test_metamorphic_scale_permutation_and_affine_units(self) -> None:
        x, y = sp.symbols("x y")
        base = derivative_energy_certificate([x + y], (x, y))
        scaled = derivative_energy_certificate([7 * (x + y)], (x, y))
        self.assertEqual(base.matrix, scaled.matrix)
        permuted = derivative_energy_certificate([y + x], (y, x))
        permutation = sp.Matrix([[0, 1], [1, 0]])
        self.assertEqual(permuted.matrix, permutation * base.matrix * permutation.T)
        z, residuals = standardized_residuals(
            [(x - 12) / 2 + (y + 2) / 4],
            (x, y),
            ((sp.Rational(10), sp.Rational(14)), (sp.Rational(-6), sp.Rational(2))),
        )
        affine = derivative_energy_certificate(residuals, z)
        self.assertEqual(base.matrix, affine.matrix)


if __name__ == "__main__":
    unittest.main()
