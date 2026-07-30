from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
import copy
import os
import unittest

import sympy as sp

from candidate import (
    LINE_ANGLE,
    POINT_ANGLE,
    ReplayLedger,
    compile_operand,
    prove_direct_relation,
    repair_or_current_exact_fallback,
    typed_semantic_equal,
)


ORIGINAL = b'{ "status": "EXACT_TARGET_AUTHORITY_REJECTED", "authority_pass": false }\n'


def R(numerator, denominator=1):
    return {"op": "rational", "numerator": numerator, "denominator": denominator}


def Q(value):
    return {"op": "qbar", "value": value}


def PI():
    return {"op": "pi"}


def A(cosine, sine, domain=POINT_ANGLE, *, direct=True, unit="radian"):
    return {"op": "angle", "cosine": cosine, "sine": sine, "unit": unit, "domain": domain, "direct": direct}


def B(op, left, right):
    return {"op": op, "left": left, "right": right}


def E(left, right, op="equal"):
    return {"op": op, "left": left, "right": right}


def ledger(failure="value is not exact rational"):
    return ReplayLedger(original_failure=failure)


def output(relation, replay=None):
    return repair_or_current_exact_fallback(ORIGINAL, relation=relation, ledger=replay or ledger())


class TypedSemanticEqualTests(unittest.TestCase):
    def assert_repaired(self, relation, replay=None):
        result = prove_direct_relation(relation, replay or ledger())
        self.assertTrue(result["authority_pass"], result)
        self.assertNotEqual(output(relation, replay), ORIGINAL)

    def assert_fallback(self, relation, replay=None):
        result = output(relation, replay)
        self.assertIs(result, ORIGINAL)

    def test_positive_closed_dispatch_rational(self):
        self.assert_repaired(E(R(1, 2), R(2, 4)))

    def test_positive_closed_dispatch_qbar(self):
        self.assert_repaired(E(Q(sp.sqrt(8) / 2), Q(sp.sqrt(2))))

    def test_positive_closed_dispatch_pi_multiple(self):
        left = B("mul", PI(), R(1, 2))
        right = B("div", PI(), R(2))
        self.assert_repaired(E(left, right))

    def test_positive_closed_dispatch_direct_angle(self):
        left = A(sp.Rational(3, 5), sp.Rational(4, 5))
        right = A(sp.sqrt(sp.Rational(9, 25)), sp.sqrt(sp.Rational(16, 25)))
        self.assert_repaired(E(left, right), ledger("scalar is not an exact angle expression"))

    def test_positive_qbar_pi_affine_with_algebraic_coefficient(self):
        left = B("add", B("mul", Q(sp.sqrt(2)), PI()), Q(sp.sqrt(3)))
        right = B("add", Q(sp.sqrt(3)), B("mul", PI(), Q(sp.sqrt(2))))
        self.assert_repaired(E(left, right))
        result = prove_direct_relation(E(left, right), ledger())
        self.assertTrue(result["qbar_pi_affine_coefficientwise"])

    def test_positive_affine_distribution(self):
        left = B("mul", B("add", PI(), Q(sp.sqrt(2))), Q(sp.sqrt(3)))
        right = B("add", B("mul", Q(sp.sqrt(3)), PI()), Q(sp.sqrt(6)))
        self.assert_repaired(E(left, right))

    def test_metamorphic_side_swap_commutation_and_exact_rewrite(self):
        first = B("add", B("mul", Q(sp.sqrt(8) / 2), PI()), Q(sp.sqrt(12) / 2))
        second = B("add", Q(sp.sqrt(3)), B("mul", PI(), Q(sp.sqrt(2))))
        self.assert_repaired(E(first, second))
        self.assert_repaired(E(second, first))

    def test_only_canonical_rational_into_qbar_equality_embedding(self):
        self.assert_repaired(E(R(1), Q(sp.Integer(1))))
        self.assert_repaired(E(Q(sp.Rational(2, 3)), R(2, 3)))
        self.assert_fallback(E(R(2), Q(sp.Integer(1))))
        self.assert_fallback(E(PI(), B("add", PI(), R(0))))
        self.assert_fallback(E(A(1, 0), PI()), ledger("scalar is not an exact angle expression"))

    def test_rational_embedding_is_not_available_to_arithmetic_or_mutation(self):
        self.assert_fallback(E(B("add", Q(sp.Integer(1)), R(1)), Q(sp.Integer(2))))
        mutated = R(1)
        mutated["embedding"] = "approximate"
        self.assert_fallback(E(Q(sp.Integer(1)), mutated))
        self.assert_fallback(E(Q(sp.pi), R(3)))

    def test_angle_domain_unit_and_provenance_are_closed(self):
        point = A(sp.Rational(3, 5), sp.Rational(4, 5))
        self.assert_fallback(E(point, A(sp.Rational(3, 5), sp.Rational(4, 5), LINE_ANGLE)))
        self.assert_fallback(E(point, A(sp.Rational(3, 5), sp.Rational(4, 5), unit="degree")))
        self.assert_fallback(E(point, A(sp.Rational(3, 5), sp.Rational(4, 5), direct=False)))

    def test_supplementary_and_affine_coefficient_offset_mismatches_are_not_equal(self):
        self.assert_fallback(E(A(sp.Rational(3, 5), sp.Rational(4, 5)), A(sp.Rational(-3, 5), sp.Rational(4, 5))))
        affine = B("add", B("mul", Q(sp.sqrt(2)), PI()), Q(sp.sqrt(3)))
        wrong_coefficient = B("add", B("mul", Q(sp.sqrt(3)), PI()), Q(sp.sqrt(3)))
        wrong_offset = B("add", B("mul", Q(sp.sqrt(2)), PI()), Q(sp.sqrt(5)))
        self.assert_fallback(E(affine, wrong_coefficient))
        self.assert_fallback(E(affine, wrong_offset))

    def test_nonlinear_nested_unknown_and_order_operations_fall_back(self):
        self.assert_fallback(E(B("mul", PI(), PI()), PI()))
        self.assert_fallback(E({"op": "sin", "arg": PI()}, R(0)))
        self.assert_fallback(E({"op": "pow", "left": PI(), "right": R(2)}, PI()))
        self.assert_fallback(E(R(1), R(1), op="lt"))
        self.assert_fallback(E(E(R(1), R(1)), R(1)))
        self.assert_fallback(E({"op": "mystery"}, {"op": "mystery"}))

    def test_approximate_nonreal_and_oversized_affine_fall_back(self):
        self.assert_fallback(E(Q(sp.Float("1.0")), Q(sp.Integer(1))))
        self.assert_fallback(E(Q(sp.I), Q(sp.I)))
        oversized = PI()
        for _ in range(7):
            oversized = B("add", oversized, R(1))
        self.assert_fallback(E(oversized, oversized))

    def test_replay_ledger_is_exact_and_failure_specific(self):
        relation = E(B("mul", PI(), Q(sp.sqrt(2))), B("mul", Q(sp.sqrt(2)), PI()))
        self.assert_fallback(relation, ledger("some other failure"))
        self.assert_fallback(relation, replace(ledger(), raw_target_exact=False))
        self.assert_fallback(relation, replace(ledger(), order_or_sign_requested=True))
        self.assert_fallback(relation, replace(ledger(), routing_used=True))

    def test_relation_unknown_metadata_is_rejected(self):
        relation = E(R(1), R(1))
        relation["extra"] = "routing-metadata"
        self.assert_fallback(relation)

    def test_exact_typed_values_are_symmetric(self):
        nodes = [
            R(2, 3),
            Q(sp.sqrt(2)),
            B("mul", PI(), R(2, 3)),
            A(sp.Rational(3, 5), sp.Rational(4, 5)),
            B("add", B("mul", PI(), Q(sp.sqrt(2))), Q(sp.sqrt(3))),
        ]
        for node in nodes:
            value, _ = compile_operand(node)
            self.assertTrue(typed_semantic_equal(value, value))

    def test_single_campaign_cpu_only(self):
        self.assertEqual(os.sched_getaffinity(0), {14})


if __name__ == "__main__":
    unittest.main()
