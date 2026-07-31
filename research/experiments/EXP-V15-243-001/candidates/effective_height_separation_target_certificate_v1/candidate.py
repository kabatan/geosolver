"""D0 effective-height zero certificate for an exact local source root.

The kernel proves ``p(raw_target) = 0`` without ideal membership.  Exact
coordinate minimal polynomials bound the joint field degree and Weil heights.
If the value were nonzero, elementary height inequalities give a positive
lower bound; a strictly smaller rigorous interval upper bound is therefore a
zero certificate.  Final source replay remains mandatory.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from math import prod
from typing import Any, Mapping, Sequence

import sympy as sp


SCHEMA = "geotarget.effective-height-target-zero-certificate/v1"


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def _q(value: object, label: str) -> sp.Rational:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{label} is not an exact rational")
    parsed = Fraction(value)
    return sp.Rational(parsed.numerator, parsed.denominator)


Interval = tuple[sp.Rational, sp.Rational]


def _interval(value: object, label: str) -> Interval:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{label} is not an interval")
    lo, hi = _q(value[0], f"{label}.lo"), _q(value[1], f"{label}.hi")
    if lo > hi:
        raise ValueError(f"{label} is reversed")
    return lo, hi


def _mul(left: Interval, right: Interval) -> Interval:
    values = [a * b for a in left for b in right]
    return min(values), max(values)


def _pow(value: Interval, exponent: int) -> Interval:
    if exponent < 0:
        raise ValueError("negative interval power")
    if exponent == 0:
        return sp.Rational(1), sp.Rational(1)
    if exponent & 1:
        return value[0] ** exponent, value[1] ** exponent
    values = [value[0] ** exponent, value[1] ** exponent]
    if value[0] <= 0 <= value[1]:
        values.append(sp.Rational(0))
    return min(values), max(values)


def _eval_interval(expression: sp.Expr, boxes: Mapping[sp.Symbol, Interval]) -> Interval:
    if expression.is_Rational:
        value = sp.Rational(expression)
        return value, value
    if expression.is_Symbol and expression in boxes:
        return boxes[expression]
    if expression.is_Add:
        parts = [_eval_interval(item, boxes) for item in expression.args]
        return sum(item[0] for item in parts), sum(item[1] for item in parts)
    if expression.is_Mul:
        answer = (sp.Rational(1), sp.Rational(1))
        for item in expression.args:
            answer = _mul(answer, _eval_interval(item, boxes))
        return answer
    if expression.is_Pow and expression.exp.is_Integer:
        return _pow(_eval_interval(expression.base, boxes), int(expression.exp))
    raise ValueError(f"unsupported interval expression {expression}")


def _primitive_irreducible(coefficients: Sequence[int], symbol: sp.Symbol) -> sp.Poly:
    if (
        not isinstance(coefficients, (list, tuple))
        or len(coefficients) < 2
        or any(not isinstance(value, int) or isinstance(value, bool) for value in coefficients)
        or coefficients[0] <= 0
    ):
        raise ValueError("polynomial coefficients are malformed")
    polynomial = sp.Poly.from_list(list(coefficients), symbol, domain=sp.ZZ)
    content, primitive = polynomial.primitive()
    if content != 1 or primitive != polynomial:
        raise ValueError("polynomial is not positive primitive")
    if sp.gcd(polynomial, polynomial.diff()).degree() != 0:
        raise ValueError("polynomial is not square-free")
    factors = sp.factor_list(polynomial.as_expr(), symbol)[1]
    if len(factors) != 1 or factors[0][1] != 1:
        raise ValueError("polynomial is not irreducible over Q")
    return polynomial


def _root_ordinal(polynomial: sp.Poly, interval: Interval) -> int:
    lo, hi = interval
    point_root = lo == hi
    if lo == hi:
        if polynomial.eval(lo) != 0:
            raise ValueError("point isolator is not an exact rational root")
    else:
        if polynomial.eval(lo) == 0 or polynomial.eval(hi) == 0:
            raise ValueError("root lies on an isolator boundary")
        if polynomial.count_roots(lo, hi) != 1:
            raise ValueError("isolator does not contain one real root")
    cauchy = sp.Rational(2 + max(abs(int(value)) for value in polynomial.all_coeffs()))
    if lo <= -cauchy:
        return 0
    count = int(polynomial.count_roots(-cauchy, lo))
    return count - int(point_root)


def _coordinate_fact(
    fact: Mapping[str, Any], symbol: sp.Symbol
) -> tuple[sp.Poly, Interval, str]:
    expected = fact.get("fact_sha256")
    if not isinstance(expected, str) or canonical_sha256(
        {key: value for key, value in fact.items() if key != "fact_sha256"}
    ) != expected:
        raise ValueError("coordinate fact self-digest mismatch")
    if fact.get("variable") != symbol.name or fact.get("independent_proposal_provenance") is not True:
        raise ValueError("coordinate fact binding/provenance is absent")
    qqbar = fact.get("serialized_qqbar")
    if not isinstance(qqbar, dict) or canonical_sha256(qqbar) != fact.get("serialized_qqbar_sha256"):
        raise ValueError("serialized QQBar binding mismatch")
    polynomial = _primitive_irreducible(fact.get("coefficients_high_to_low"), symbol)
    l1 = sum(abs(int(value)) for value in polynomial.all_coeffs())
    if fact.get("recomputed_l1_height") != l1:
        raise ValueError("coordinate height metadata is underestimated or stale")
    isolator = _interval(fact.get("isolating_interval"), f"{symbol}.isolator")
    ordinal = _root_ordinal(polynomial, isolator)
    if fact.get("real_root_ordinal") != ordinal:
        raise ValueError("coordinate root ordinal mismatch")
    return polynomial, isolator, expected


def _not_proved(reason: str) -> dict[str, Any]:
    body = {
        "schema_version": SCHEMA,
        "status": "NOT_PROVED",
        "reason": reason,
        "authority": False,
        "target_release": False,
        "canonical_source_replay_required": True,
        "truth_used": False,
        "coverage": "UNKNOWN",
    }
    body["artifact_sha256"] = canonical_sha256(body)
    return body


def prove(
    *, job: dict[str, Any], source_root_certificate: dict[str, Any], descriptor: dict[str, Any]
) -> dict[str, Any]:
    try:
        if canonical_sha256({k: v for k, v in job.items() if k != "job_sha256"}) != job.get(
            "job_sha256"
        ):
            raise ValueError("job self-digest mismatch")
        if canonical_sha256(
            {k: v for k, v in source_root_certificate.items() if k != "artifact_sha256"}
        ) != source_root_certificate.get("artifact_sha256"):
            raise ValueError("source-root certificate self-digest mismatch")
        if source_root_certificate.get("status") != "VERIFIED":
            raise ValueError("source-root certificate is not VERIFIED")
        for key in (
            "job_sha256",
            "source_sha256",
            "endpoint_float64_sha256",
            "system_sha256",
            "obligation_ledger_sha256",
            "lineage_sha256",
        ):
            if source_root_certificate.get(key) != job.get(key):
                raise ValueError(f"source-root certificate {key} mismatch")
        for flag in (
            "same_endpoint_source_root_unique",
            "all_source_equations_exact",
            "all_guards_exact",
            "all_branches_exact",
            "all_coordinate_facts_same_root",
        ):
            if source_root_certificate.get(flag) is not True:
                raise ValueError(f"source-root certificate lacks {flag}")

        statement = job.get("source_statement")
        if not isinstance(statement, dict) or canonical_sha256(statement) != job.get("system_sha256"):
            raise ValueError("source statement binding mismatch")
        names = statement.get("variables")
        target_text = statement.get("raw_target")
        if not isinstance(names, list) or not isinstance(target_text, str) or len(set(names)) != len(names):
            raise ValueError("source statement is malformed")
        symbols = {name: sp.Symbol(name, real=True) for name in names}
        raw_target = sp.cancel(sp.sympify(target_text, locals=symbols))
        target_num, target_den = sp.fraction(raw_target)
        if target_den.free_symbols or not target_num.free_symbols <= set(symbols.values()):
            raise ValueError("raw target is not a rational polynomial")
        sp.Poly(target_num, *symbols.values(), domain=sp.QQ)

        facts = job.get("coordinate_facts")
        if not isinstance(facts, list) or len(facts) != len(names):
            raise ValueError("coordinate fact count mismatch")
        by_name = {str(item.get("variable")): item for item in facts if isinstance(item, dict)}
        if set(by_name) != set(names):
            raise ValueError("coordinate fact variables mismatch")
        polynomials: list[sp.Poly] = []
        boxes: dict[sp.Symbol, Interval] = {}
        fact_hashes: list[str] = []
        for name in names:
            polynomial, isolator, digest = _coordinate_fact(by_name[name], symbols[name])
            polynomials.append(polynomial)
            boxes[symbols[name]] = isolator
            fact_hashes.append(digest)
        if source_root_certificate.get("coordinate_fact_sha256") != fact_hashes:
            raise ValueError("source-root certificate coordinate-fact join mismatch")

        target_symbol = sp.Symbol("__target", real=True)
        candidate = _primitive_irreducible(
            descriptor.get("coefficients_high_to_low"), target_symbol
        )
        target_selection = _interval(descriptor.get("isolating_interval"), "target isolator")
        target_ordinal = _root_ordinal(candidate, target_selection)
        if descriptor.get("real_root_ordinal") != target_ordinal:
            raise ValueError("target root ordinal mismatch")
        target_box = _eval_interval(raw_target, boxes)
        if not target_selection[0] <= target_box[0] or not target_box[1] <= target_selection[1]:
            raise ValueError("raw target box is not inside descriptor isolator")

        value = sp.cancel(candidate.as_expr().subs(target_symbol, raw_target))
        numerator, denominator = sp.fraction(value)
        denominator_q = sp.Rational(denominator)
        if denominator_q == 0 or not denominator_q.is_Rational:
            raise ValueError("target polynomial value has a nonconstant denominator")
        if denominator_q < 0:
            numerator, denominator_q = -numerator, -denominator_q
        numerator_poly = sp.Poly(numerator, *symbols.values(), domain=sp.QQ)
        common_denominator = sp.ilcm(
            *[int(term.q) for term in numerator_poly.coeffs()], int(denominator_q.q)
        )
        integer_numerator = sp.Poly(
            sp.expand(numerator * common_denominator), *symbols.values(), domain=sp.ZZ
        )
        total_denominator = int(denominator_q * common_denominator)
        if total_denominator <= 0:
            raise ValueError("target value denominator normalization failed")

        coordinate_l1 = [sum(abs(int(c)) for c in p.all_coeffs()) for p in polynomials]
        terms = integer_numerator.terms()
        if not terms:
            raise ValueError("symbolic zero is outside the separation experiment")
        height_product = 1 << max(0, len(terms) - 1)
        for exponents, coefficient in terms:
            term_height = max(1, abs(int(coefficient)))
            for exponent, coordinate_height in zip(exponents, coordinate_l1, strict=True):
                term_height *= coordinate_height ** int(exponent)
            height_product *= term_height
        height_product *= total_denominator
        joint_degree_bound = prod(polynomial.degree() for polynomial in polynomials)
        nonzero_lower_bound = sp.Rational(1, height_product**joint_degree_bound)
        enclosure = _eval_interval(value, boxes)
        zero_upper_bound = max(abs(enclosure[0]), abs(enclosure[1]))
        if not zero_upper_bound < nonzero_lower_bound:
            return _not_proved("interval-upper-not-below-effective-nonzero-lower-bound")

        body: dict[str, Any] = {
            "schema_version": SCHEMA,
            "status": "VERIFIED_PROPOSAL",
            "proof_method": "WEIL_HEIGHT_LIOUVILLE_NONZERO_SEPARATION",
            "target_polynomial_value_exactly_zero": True,
            "joint_field_degree_upper_bound": joint_degree_bound,
            "multiplicative_height_upper_bound": str(height_product),
            "effective_nonzero_lower_bound": str(nonzero_lower_bound),
            "rigorous_value_interval": [str(enclosure[0]), str(enclosure[1])],
            "rigorous_zero_upper_bound": str(zero_upper_bound),
            "strict_separation_verified": True,
            "source_root_certificate_sha256": source_root_certificate["artifact_sha256"],
            "coordinate_fact_sha256": fact_hashes,
            "descriptor_sha256": canonical_sha256(descriptor),
            "numeric_proximity_used_as_equality": False,
            "authority": False,
            "target_release": False,
            "canonical_source_replay_required": True,
            "truth_used": False,
            "coverage": "UNKNOWN",
        }
        body["artifact_sha256"] = canonical_sha256(body)
        return body
    except (ValueError, TypeError, KeyError, sp.SympifyError, sp.PolynomialError) as error:
        return _not_proved(f"{type(error).__name__}:{error}")


__all__ = ["canonical_sha256", "prove"]
