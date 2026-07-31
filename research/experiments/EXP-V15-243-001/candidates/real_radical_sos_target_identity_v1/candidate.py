"""Disposable exact real-radical SOS target-identity verifier."""

from __future__ import annotations

from dataclasses import dataclass
import itertools

import sympy as sp


@dataclass(frozen=True)
class Source:
    variables: tuple[sp.Symbol, ...]
    equality_generators: tuple[sp.Expr, ...]
    raw_target: sp.Expr
    target_q: sp.Rational
    equality_only: bool
    external_real_root_certificate: bool
    full_guard_branch_certificate: bool


@dataclass(frozen=True)
class Certificate:
    generators: tuple[sp.Expr, ...]
    cofactors: tuple[sp.Expr, ...]
    m: int
    sos_monomials: tuple[sp.Expr, ...]
    gram: sp.ImmutableMatrix


@dataclass(frozen=True)
class Result:
    identity_ready: bool
    join_ready: bool
    authority_emitted: bool
    status: str
    descriptor: tuple[tuple[int, ...], int] | None
    direct_membership: bool
    square_membership: bool
    join_required: bool


def _zero(expression):
    value = sp.factor(sp.cancel(sp.together(expression)))
    return value == 0 or value.is_zero is True or value.equals(0) is True


def _polynomial(expression, variables):
    try:
        return sp.Poly(expression, *variables, domain=sp.QQ)
    except Exception:
        return None


def _is_monomial(expression, variables):
    polynomial = _polynomial(expression, variables)
    if polynomial is None or len(polynomial.terms()) != 1:
        return False
    (_powers, coefficient), = polynomial.terms()
    return coefficient == 1 and polynomial.total_degree() <= 3


def _gram_psd_exact(matrix):
    if matrix.rows != matrix.cols or matrix != matrix.T:
        return False
    if any(not isinstance(value, sp.Rational) for value in matrix):
        return False
    indices = range(matrix.rows)
    for size in range(1, matrix.rows + 1):
        for subset in itertools.combinations(indices, size):
            principal = matrix.extract(subset, subset).det()
            if principal < 0:
                return False
    return True


def _unit_ideal(basis):
    try:
        return _zero(basis.reduce(sp.Integer(1))[1])
    except Exception:
        return False


def solve(source: Source, certificate: Certificate) -> Result:
    empty = Result(False, False, False, "REJECTED", None, False, False, True)
    if not source.equality_only or not source.equality_generators:
        return empty
    if not isinstance(source.target_q, sp.Rational):
        return empty
    if any(_polynomial(expression, source.variables) is None for expression in (
        *source.equality_generators, source.raw_target
    )):
        return empty
    if len(certificate.generators) != len(source.equality_generators):
        return empty
    if len(certificate.cofactors) != len(source.equality_generators):
        return empty
    if any(
        not _zero(left - right)
        for left, right in zip(certificate.generators, source.equality_generators, strict=True)
    ):
        return empty
    if any(_polynomial(value, source.variables) is None for value in certificate.cofactors):
        return empty
    if certificate.m not in (1, 2):
        return empty
    if not certificate.sos_monomials or not all(
        _is_monomial(value, source.variables) for value in certificate.sos_monomials
    ):
        return empty
    gram = sp.Matrix(certificate.gram)
    if gram.shape != (len(certificate.sos_monomials),) * 2 or not _gram_psd_exact(gram):
        return empty

    try:
        basis = sp.groebner(source.equality_generators, *source.variables, order="grevlex", domain=sp.QQ)
    except Exception:
        return empty
    if _unit_ideal(basis):
        return Result(False, False, False, "UNIT_IDEAL_REJECTED", None, False, False, True)
    h = sp.expand(source.raw_target - source.target_q)
    direct_membership = _zero(basis.reduce(h)[1])
    square_membership = _zero(basis.reduce(sp.expand(h**2))[1])
    monomials = sp.Matrix(certificate.sos_monomials)
    sos = sp.expand((monomials.T * gram * monomials)[0])
    left = sp.expand(h ** (2 * certificate.m) + sos)
    right = sp.expand(sum(
        cofactor * generator
        for cofactor, generator in zip(certificate.cofactors, certificate.generators, strict=True)
    ))
    if not _zero(left - right):
        return Result(False, False, False, "EXACT_IDENTITY_FAILED", None, direct_membership, square_membership, True)
    q = sp.Rational(source.target_q)
    descriptor = ((int(q.q), -int(q.p)), 0)
    join_ready = source.external_real_root_certificate and source.full_guard_branch_certificate
    return Result(
        True,
        bool(join_ready),
        False,
        "JOIN_READY" if join_ready else "IDENTITY_READY_EXISTENCE_OR_REPLAY_REQUIRED",
        descriptor,
        direct_membership,
        square_membership,
        True,
    )


__all__ = ["Certificate", "Result", "Source", "solve"]
