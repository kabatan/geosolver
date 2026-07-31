"""Disposable exact finite-target-image proposal via Morse/polar charts."""

from __future__ import annotations

from dataclasses import dataclass
import itertools
from typing import Sequence

import sympy as sp


MAX_BASE_VARIABLES = 4
MAX_CHART_VARIABLES = 7
MAX_COMPONENTS = 4
MAX_TOTAL_DEGREE = 6
MAX_TERMS = 96
MAX_LOCALIZATIONS = 32


class CertificateRejected(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class Component:
    equations: tuple[sp.Expr, ...]


@dataclass(frozen=True, slots=True)
class Source:
    variables: tuple[sp.Symbol, ...]
    equations: tuple[sp.Expr, ...]
    components: tuple[Component, ...]
    target: sp.Expr
    strict_positive: tuple[sp.Expr, ...] = ()
    disequalities: tuple[sp.Expr, ...] = ()
    strict_slacks: tuple[sp.Symbol, ...] = ()
    disequality_slacks: tuple[sp.Symbol, ...] = ()


@dataclass(frozen=True, order=True, slots=True)
class TargetDescriptor:
    minpoly_coefficients_high_to_low: tuple[int, ...]
    real_root_ordinal: int
    isolator_left: str
    isolator_right: str


@dataclass(frozen=True, slots=True)
class Certificate:
    status: str
    descriptors: tuple[TargetDescriptor, ...]
    component_count: int
    smooth_localization_count: int
    proper_critical_ideal_count: int
    singular_recursion_count: int
    exact_chart_equation_count: int
    proposal_authority: bool = False
    release: bool = False
    existing_canonical_source_guard_branch_raw_target_replay_required: bool = True


def _poly(expression: sp.Expr, variables: Sequence[sp.Symbol]) -> sp.Poly:
    try:
        polynomial = sp.Poly(sp.expand(expression), *variables, domain=sp.QQ)
    except Exception as error:
        raise CertificateRejected("UNSUPPORTED_NONPOLYNOMIAL_SOURCE") from error
    if polynomial.total_degree() > MAX_TOTAL_DEGREE or len(polynomial.terms()) > MAX_TERMS:
        raise CertificateRejected("POLYNOMIAL_SCOPE_CAP")
    return polynomial


def _groebner(equations: Sequence[sp.Expr], variables: Sequence[sp.Symbol]) -> sp.GroebnerBasis:
    if not equations:
        return sp.groebner((sp.Integer(0),), *variables, order="lex", domain=sp.QQ)
    for equation in equations:
        _poly(equation, variables)
    try:
        return sp.groebner(tuple(equations), *variables, order="lex", domain=sp.QQ)
    except Exception as error:
        raise CertificateRejected("GROEBNER_FAILED_CLOSED") from error


def _unit(groebner: sp.GroebnerBasis) -> bool:
    return any(poly.as_expr() == 1 for poly in groebner.polys)


def _zero_mod(expression: sp.Expr, groebner: sp.GroebnerBasis) -> bool:
    return sp.expand(groebner.reduce(sp.expand(expression))[1]) == 0


def _ideals_equal(
    left: Sequence[sp.Expr], right: Sequence[sp.Expr], variables: Sequence[sp.Symbol]
) -> bool:
    gl = _groebner(left, variables)
    gr = _groebner(right, variables)
    return all(_zero_mod(poly.as_expr(), gr) for poly in gl.polys) and all(
        _zero_mod(poly.as_expr(), gl) for poly in gr.polys
    )


def ideal_intersection(
    ideals: Sequence[Sequence[sp.Expr]], variables: Sequence[sp.Symbol]
) -> tuple[sp.Expr, ...]:
    if not ideals:
        raise CertificateRejected("NO_COMPONENTS")
    current = tuple(ideals[0])
    for ordinal, other in enumerate(ideals[1:]):
        auxiliary = sp.Symbol(f"__intersection_{ordinal}")
        if auxiliary in variables:
            raise CertificateRejected("AUXILIARY_NAME_COLLISION")
        equations = tuple(auxiliary * item for item in current) + tuple(
            (1 - auxiliary) * item for item in other
        )
        basis = _groebner(equations, (auxiliary, *variables))
        current = tuple(
            sp.expand(poly.as_expr())
            for poly in basis.polys
            if auxiliary not in poly.as_expr().free_symbols
        )
        if not current:
            current = (sp.Integer(0),)
    return current


def _component_dimension(component: Component, variables: Sequence[sp.Symbol]) -> int:
    equations = tuple(sp.expand(item) for item in component.equations if sp.expand(item) != 0)
    if not equations:
        return len(variables)
    polynomials = tuple(_poly(item, variables) for item in equations)
    if len(polynomials) == 1:
        polynomial = polynomials[0]
        if (
            polynomial.total_degree() < 1
            or polynomial.monic() != polynomial.sqf_part().monic()
        ):
            raise CertificateRejected("NONRADICAL_COMPONENT")
        return len(variables) - 1
    if all(polynomial.total_degree() <= 1 for polynomial in polynomials):
        coefficient_rows = []
        for polynomial in polynomials:
            coefficient_rows.append([polynomial.coeff_monomial(variable) for variable in variables])
        rank = int(sp.Matrix(coefficient_rows).rank())
        basis = _groebner(equations, variables)
        if _unit(basis) or rank == 0:
            raise CertificateRejected("EMPTY_OR_MALFORMED_LINEAR_COMPONENT")
        return len(variables) - rank
    raise CertificateRejected("RADICAL_EQUIDIMENSIONAL_PROOF_UNSUPPORTED")


def _minors(matrix: sp.Matrix, order: int) -> tuple[sp.Expr, ...]:
    if order == 0:
        return (sp.Integer(1),)
    if order > matrix.rows or order > matrix.cols:
        return ()
    values = {
        sp.expand(matrix.extract(rows, columns).det())
        for rows in itertools.combinations(range(matrix.rows), order)
        for columns in itertools.combinations(range(matrix.cols), order)
    }
    return tuple(sorted(values, key=sp.srepr))


def _proper_quadratics(variables: Sequence[sp.Symbol]) -> tuple[sp.Expr, ...]:
    # A fixed, source-independent finite Morse schedule.  Every member is a
    # positive-definite rational quadratic and therefore proper on R^n.
    centers = (
        tuple(sp.Rational(index + 1, index + 2) for index in range(len(variables))),
        tuple(sp.Integer(0) for _ in variables),
        tuple(sp.Rational((-1) ** index, index + 2) for index in range(len(variables))),
    )
    return tuple(
        sp.expand(
            sum(
                sp.Rational(index + 1) * (variable - center[index]) ** 2
                for index, variable in enumerate(variables)
            )
        )
        for center in centers
    )


def _real_targets_from_zero_dimensional(
    equations: Sequence[sp.Expr],
    variables: Sequence[sp.Symbol],
    target: sp.Expr,
) -> tuple[sp.Expr, ...]:
    basis = _groebner(equations, variables)
    if _unit(basis):
        return ()
    if not basis.is_zero_dimensional:
        raise CertificateRejected("CRITICAL_IDEAL_NOT_ZERO_DIMENSIONAL")
    try:
        solutions = sp.solve_poly_system(tuple(equations), *variables)
    except Exception as error:
        raise CertificateRejected("EXACT_CRITICAL_SOLVE_FAILED") from error
    if solutions is None:
        raise CertificateRejected("EXACT_CRITICAL_SOLVE_INCOMPLETE")
    values: list[sp.Expr] = []
    for solution in solutions:
        if len(solution) != len(variables):
            raise CertificateRejected("EXACT_CRITICAL_SOLVE_DIMENSION_MISMATCH")
        real_status = []
        for value in solution:
            imaginary_zero = sp.im(value).equals(0)
            if value.is_real is True or imaginary_zero is True:
                real_status.append(True)
            elif value.is_real is False or imaginary_zero is False:
                real_status.append(False)
            else:
                raise CertificateRejected("EXACT_CRITICAL_REALITY_UNDECIDED")
        if not all(real_status):
            continue
        value = sp.simplify(target.subs(dict(zip(variables, solution, strict=True))))
        if value.is_real is not True and sp.im(value).equals(0) is not True:
            raise CertificateRejected("EXACT_TARGET_REALITY_UNDECIDED")
        if not any(sp.simplify(value - old) == 0 for old in values):
            values.append(value)
    return tuple(values)


def _descriptor(value: sp.Expr) -> TargetDescriptor:
    symbol = sp.Symbol("__target_value")
    try:
        polynomial = sp.Poly(sp.minpoly(value, symbol), symbol, domain=sp.QQ)
    except Exception as error:
        raise CertificateRejected("TARGET_MINPOLY_FAILED") from error
    primitive = polynomial.clear_denoms(convert=True)[1].primitive()[1]
    if primitive.LC() < 0:
        primitive = -primitive
    intervals = primitive.intervals(eps=sp.Rational(1, 10**24))
    approximation = sp.N(value, 90)
    chosen = None
    real_ordinal = 0
    for interval, multiplicity in intervals:
        left, right = interval
        if multiplicity != 1:
            raise CertificateRejected("TARGET_MINPOLY_NOT_SQUARE_FREE")
        inside = bool(sp.N(left, 90) <= approximation <= sp.N(right, 90))
        if inside:
            chosen = (left, right, real_ordinal)
            break
        real_ordinal += 1
    if chosen is None:
        raise CertificateRejected("TARGET_ROOT_ISOLATOR_NOT_FOUND")
    left, right, ordinal = chosen
    return TargetDescriptor(
        tuple(int(item) for item in primitive.all_coeffs()),
        ordinal,
        str(left),
        str(right),
    )


def _certify_chart_stratum(
    equations: Sequence[sp.Expr],
    variables: Sequence[sp.Symbol],
    dimension: int,
    target: sp.Expr,
    component_ordinal: int,
) -> tuple[tuple[sp.Expr, ...], int, int, int]:
    """Return exact real critical targets and work counts for one chart."""

    basis = _groebner(equations, variables)
    if _unit(basis):
        return (), 0, 0, 0
    if dimension == 0:
        return _real_targets_from_zero_dimensional(equations, variables, target), 0, 0, 0

    codimension = len(variables) - dimension
    jacobian = sp.Matrix(tuple(equations)).jacobian(tuple(variables))
    rank_minors = tuple(
        minor for minor in _minors(jacobian, codimension) if not _zero_mod(minor, basis)
    )
    if not rank_minors:
        raise CertificateRejected("NO_SMOOTH_JACOBIAN_MINOR_COVER")
    if len(rank_minors) > MAX_LOCALIZATIONS:
        raise CertificateRejected("LOCALIZATION_SCOPE_CAP")

    target_row = sp.Matrix([[sp.diff(target, variable) for variable in variables]])
    augmented_target = jacobian.col_join(target_row)
    target_minors = _minors(augmented_target, codimension + 1)
    targets: list[sp.Expr] = []
    for localization_ordinal, rank_minor in enumerate(rank_minors):
        inverse = sp.Symbol(f"__minor_inverse_{component_ordinal}_{localization_ordinal}")
        if inverse in variables:
            raise CertificateRejected("AUXILIARY_NAME_COLLISION")
        localized_variables = (*variables, inverse)
        localized_equations = (*equations, sp.expand(rank_minor * inverse - 1))
        localized_basis = _groebner(localized_equations, localized_variables)
        if any(not _zero_mod(minor, localized_basis) for minor in target_minors):
            # Finite critical values are not enough: dT must vanish everywhere
            # on this smooth localization.  Circle with T=x fails here.
            raise CertificateRejected("TARGET_DIFFERENTIAL_NONZERO_ON_SMOOTH_STRATUM")

    # The localization loop proves dT=0 on a cover of the smooth stratum.
    # A single global proper-polar ideal then samples every real connected
    # component; solving the same critical points once per minor is needless.
    selected_critical = False
    for quadratic in _proper_quadratics(variables):
        quadratic_row = sp.Matrix(
            [[sp.diff(quadratic, variable) for variable in variables]]
        )
        polar_minors = _minors(
            jacobian.col_join(quadratic_row), codimension + 1
        )
        critical_equations = (*equations, *polar_minors)
        critical_basis = _groebner(critical_equations, variables)
        if _unit(critical_basis) or not critical_basis.is_zero_dimensional:
            continue
        values = _real_targets_from_zero_dimensional(
            critical_equations, variables, target
        )
        if not values:
            # A nonempty real chart would have a real minimum of this proper
            # quadratic.  Try the next fixed quadratic when SymPy cannot
            # materialize that exact critical point set.
            continue
        for value in values:
            if not any(sp.simplify(value - old) == 0 for old in targets):
                targets.append(value)
        selected_critical = True
        break
    if not selected_critical:
        raise CertificateRejected("PROPER_CRITICAL_IDEAL_EXACT_REAL_SOLVE_FAILED")

    singular_equations = (*equations, *_minors(jacobian, codimension))
    singular_basis = _groebner(singular_equations, variables)
    singular_recursion = 0
    if not _unit(singular_basis):
        if not singular_basis.is_zero_dimensional:
            raise CertificateRejected("POSITIVE_DIMENSIONAL_SINGULAR_RECURSION_UNSUPPORTED")
        singular_recursion = 1
        for value in _real_targets_from_zero_dimensional(
            singular_equations, variables, target
        ):
            if not any(sp.simplify(value - old) == 0 for old in targets):
                targets.append(value)
    return tuple(targets), len(rank_minors), 1, singular_recursion


def certify(source: Source) -> Certificate:
    variables = source.variables
    if not 1 <= len(variables) <= MAX_BASE_VARIABLES or len(set(variables)) != len(variables):
        raise CertificateRejected("BASE_VARIABLE_SCOPE")
    if not 1 <= len(source.components) <= MAX_COMPONENTS:
        raise CertificateRejected("COMPONENT_SCOPE")
    if len(source.strict_slacks) != len(source.strict_positive) or len(
        source.disequality_slacks
    ) != len(source.disequalities):
        raise CertificateRejected("INCOMPLETE_EXACT_CHARTS")
    slacks = (*source.strict_slacks, *source.disequality_slacks)
    if len(set(slacks)) != len(slacks) or set(slacks) & set(variables):
        raise CertificateRejected("MALFORMED_EXACT_CHART_SLACKS")
    chart_variables = (*variables, *slacks)
    if len(chart_variables) > MAX_CHART_VARIABLES:
        raise CertificateRejected("CHART_VARIABLE_SCOPE")
    _poly(source.target, variables)
    for expression in (*source.equations, *source.strict_positive, *source.disequalities):
        _poly(expression, variables)

    component_ideals = tuple(component.equations for component in source.components)
    intersection = ideal_intersection(component_ideals, variables)
    if not _ideals_equal(source.equations, intersection, variables):
        raise CertificateRejected("INCOMPLETE_OR_INCORRECT_COMPONENT_COVER")

    chart_equations = tuple(
        sp.expand(guard * slack**2 - 1)
        for guard, slack in zip(source.strict_positive, source.strict_slacks, strict=True)
    ) + tuple(
        sp.expand(expression * slack - 1)
        for expression, slack in zip(
            source.disequalities, source.disequality_slacks, strict=True
        )
    )
    all_targets: list[sp.Expr] = []
    smooth_count = critical_count = singular_count = 0
    for ordinal, component in enumerate(source.components):
        dimension = _component_dimension(component, variables)
        equations = (*component.equations, *chart_equations)
        targets, smooth, critical, singular = _certify_chart_stratum(
            equations, chart_variables, dimension, source.target, ordinal
        )
        smooth_count += smooth
        critical_count += critical
        singular_count += singular
        for value in targets:
            if not any(sp.simplify(value - old) == 0 for old in all_targets):
                all_targets.append(value)
    if not all_targets:
        raise CertificateRejected("NO_REAL_TARGET_IMAGE_WITNESS")
    descriptors = tuple(sorted((_descriptor(value) for value in all_targets)))
    return Certificate(
        "EXACT_FINITE_TARGET_IMAGE_PROPOSAL",
        descriptors,
        len(source.components),
        smooth_count,
        critical_count,
        singular_count,
        len(chart_equations),
    )


def boundary_manifest() -> dict[str, object]:
    return {
        "exact_strict_chart": "g*s^2-1",
        "exact_disequality_chart": "h*u-1",
        "source_ideal_component_intersection_checked": True,
        "radical_equidimensional_scope_checked": True,
        "localized_augmented_jacobian_minors_prove_dT_zero": True,
        "proper_rational_quadratic_polar_ideals_zero_dimensional": True,
        "zero_dimensional_singular_locus_recursion": True,
        "exact_real_critical_target_union": True,
        "finite_critical_values_alone_sufficient": False,
        "proposal_authority": False,
        "release": False,
        "canonical_replay_required": True,
        "truth_or_outcome_input": False,
        "case_or_family_routing": False,
    }


__all__ = [
    "Certificate",
    "CertificateRejected",
    "Component",
    "Source",
    "TargetDescriptor",
    "boundary_manifest",
    "certify",
    "ideal_intersection",
]
