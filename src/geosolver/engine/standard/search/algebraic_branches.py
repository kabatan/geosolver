"""Exact finite branch discovery for small rational Cartesian systems.

The polynomial system is a conservative relaxation: denominators are cleared
and a single radical may be squared. Original domain and residual checks are
mandatory. Unsupported or non-finite systems keep the ordinary search path.
"""

import ast
import math
import signal
import threading
import time
from contextlib import contextmanager

_SUPPORTED_CALLS = {
    "Angle",
    "sin",
    "cos",
    "tan",
    "abs",
    "AreConcyclic",
    "Intersect",
    "Circumcircle",
    "OnLine",
    "Parallel",
    "Point",
    "Perpendicular",
    "IntersectLines",
    "Reflect",
    "Collinear",
    "Centroid",
    "OnCircle",
    "PointOnSegment",
    "PerpendicularBisector",
    "Dot",
    "Line",
    "ParallelLine",
    "CircleThroughThreePoints",
    "Circumcenter",
    "Center",
    "Orthocenter",
    "Midpoint",
    "sqrt",
    "PerpendicularLine",
    "Circle",
    "Abs",
    "FootOfPerpendicular",
    "Distance",
    "OnSegment",
    "IsTangent",
    "Vector",
    "Radius",
    "Area",
}


def _eligible(bundle):
    if bundle is None:
        return False
    spec = bundle.spec
    if not 1 <= len(bundle.var_names) <= 12 or not spec.constraints or spec.logical_plans:
        return False
    definitions = {item.name: item.expr for item in spec.construction}
    visited = set()

    def supported(source):
        tree = ast.parse(str(source), mode="eval")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and (
                not isinstance(node.func, ast.Name)
                or node.func.id not in _SUPPORTED_CALLS
                or node.keywords
            ):
                return False
            if isinstance(node, ast.Name) and node.id in definitions and node.id not in visited:
                visited.add(node.id)
                if not supported(definitions[node.id]):
                    return False
            if isinstance(node, ast.Compare | ast.BoolOp | ast.Subscript | ast.IfExp):
                return False
        return True

    return all(supported(source) for source in (*spec.constraints, *bundle.targets))


def affine_polynomial_consequences(equations, variables):
    """Return affine rows and their exact constant row-combination receipts.

    Nonlinear monomials precede affine monomials. Row reduction of [M|I]
    records an invertible constant change of equation rows; any reduced row
    with zero nonlinear coefficients is therefore an affine consequence.
    Original equations are retained by the caller. This is an optional bounded
    reduction, never a division by a variable or a geometric normalization.
    """
    import sympy as sp

    if not 2 <= len(equations) <= 32 or not any(p.total_degree() > 1 for p in equations):
        return ()
    if any(
        p.gens != tuple(variables) or not (p.domain.is_QQ or p.domain.is_AlgebraicField)
        for p in equations
    ):
        return ()
    monomials = sorted(
        {monomial for poly in equations for monomial, _ in poly.terms()},
        key=lambda monomial: (sum(monomial), monomial),
        reverse=True,
    )
    if len(monomials) > 96:
        return ()
    coefficients = [[poly.coeff_monomial(monomial) for monomial in monomials] for poly in equations]
    if any(
        max(abs(int(atom.p)).bit_length(), int(atom.q).bit_length()) > 4096
        for row in coefficients
        for coefficient in row
        for atom in coefficient.atoms(sp.Rational)
    ):
        return ()
    domain = equations[0].domain
    for poly in equations[1:]:
        domain = domain.unify(poly.domain)
    matrix = sp.Matrix(coefficients).row_join(sp.eye(len(equations)))
    # Exact field arithmetic decides zero coefficients; no symbolic or numeric
    # pivot assumptions are permitted in a row-combination proof.
    reduced = matrix.to_DM(domain=domain).rref()[0].to_Matrix()
    nonlinear = sum(sum(monomial) > 1 for monomial in monomials)
    consequences = []
    for row in range(reduced.rows):
        if any(reduced[row, column] != 0 for column in range(nonlinear)):
            continue
        expression = sum(
            reduced[row, column]
            * sp.prod(v**power for v, power in zip(variables, monomial, strict=True))
            for column, monomial in enumerate(monomials)
            if column >= nonlinear
        )
        if expression == 0:
            continue
        poly = sp.Poly(expression, *variables, domain=domain)
        weights = tuple(reduced[row, len(monomials) + column] for column in range(len(equations)))
        consequences.append((poly, weights))
    return tuple(consequences)


class AlgebraicWorkLimit(RuntimeError):
    """Optional symbolic work timed out; not a geometry-domain failure."""


@contextmanager
def _bounded_symbolic_work(seconds):
    """Bound actual worker CPU, while the parent retains its wall deadline.

    Scheduler contention must not consume an optional algebraic work budget.
    The request still has an independent 1.5 second wall limit in its parent.
    """
    available = (
        hasattr(signal, "setitimer")
        and hasattr(signal, "ITIMER_PROF")
        and threading.current_thread() is threading.main_thread()
    )
    if not available:
        yield False
        return
    previous_handler = signal.getsignal(signal.SIGPROF)
    previous_timer = signal.getitimer(signal.ITIMER_PROF)
    if previous_timer[0] > 0:
        # An enclosing operation or profiler owns this timer. Decline optional
        # discovery instead of replacing its handler or extending its budget.
        yield False
        return

    def interrupt(_signum, _frame):
        raise AlgebraicWorkLimit("algebraic discovery work limit")

    signal.signal(signal.SIGPROF, interrupt)
    signal.setitimer(signal.ITIMER_PROF, seconds)
    try:
        yield True
    finally:
        signal.setitimer(signal.ITIMER_PROF, 0)
        signal.signal(signal.SIGPROF, previous_handler)
        signal.setitimer(signal.ITIMER_PROF, *previous_timer)


class _DiscoveryWork:
    """Observe optional work without changing its arithmetic or limits."""

    def __init__(self):
        self.current = None
        self.started_wall = time.monotonic()
        self.started_cpu = time.process_time()
        self.phases = {}
        self.stop_reason = None
        self.interrupted_phase = None

    def mark(self, name):
        wall, cpu = time.monotonic(), time.process_time()
        if self.current is not None:
            values = self.phases.setdefault(self.current, {"wall_seconds": 0.0, "cpu_seconds": 0.0})
            values["wall_seconds"] += wall - self.started_wall
            values["cpu_seconds"] += cpu - self.started_cpu
        self.current = name
        self.started_wall, self.started_cpu = wall, cpu

    def snapshot(self):
        self.mark(None)
        return {
            "phases": self.phases,
            "stop_reason": self.stop_reason,
            "interrupted_phase": self.interrupted_phase,
            "inner_cpu_budget_seconds": 0.5,
        }


def discover_polynomial_branches(payload):
    work = _DiscoveryWork()
    result = _discover_polynomial_branches(payload, work)
    if payload.get("report_work"):
        return {"result": result, "work_telemetry": work.snapshot()}
    return result


def _discover_polynomial_branches(payload, work):
    """Return every real branch of a proved finite polynomial relaxation.

    A lexicographic basis in shape position provides rational functions of one
    scalar parameter. Coprimality excludes division by zero on every root, so
    back-substitution cannot silently remove singular branches. Rational real
    root isolation includes repeated roots and does not use floating signs.
    """
    work.mark("imports")
    import sympy as sp

    from geosolver.engine.standard.search.cartesian_polynomials import (
        CartesianPolynomials,
        exact_guard_value,
    )
    from geosolver.engine.standard.search.polynomial_zero_consequences import (
        quadratic_sos_zero_consequences,
        squarefree_zero_consequences,
    )

    consequence_counts = {"squarefree": 0, "sos": 0}
    from geosolver.engine.standard.search.algebraic_sign_ledger import (
        NormSignCondition,
        proved_norm_sign_violation,
    )

    norm_sign_conditions = []

    def augment_zero_rows(rows, variables):
        # These exact consequences preserve every original real solution.
        # Every original row remains present; no quotient by a variable occurs.
        additions = []
        for row, _, _ in squarefree_zero_consequences(rows, variables):
            if row not in rows and row not in additions:
                additions.append(row)
                consequence_counts["squarefree"] += 1
        for _, _, terms in quadratic_sos_zero_consequences(rows, variables):
            for _, row in terms:
                if not row.is_zero and row not in rows and row not in additions:
                    if len(additions) >= 32:
                        break
                    additions.append(row)
                    consequence_counts["sos"] += 1
        return [*rows, *additions]

    def exact_poly(expression, variables):
        poly = sp.Poly(expression, *variables, extension=True, field=True)
        if not (poly.domain.is_QQ or poly.domain.is_AlgebraicField):
            raise ValueError("non-algebraic polynomial coefficient")
        return poly

    def polynomial(expression, variables, constraint_index):
        from .angle_equations import necessary_angle_equation

        expression = necessary_angle_equation(expression)
        # A quadratic norm eliminates a square root or absolute value without
        # selecting its sign: a+b*r=0 and r**2=c imply a**2-b**2*c=0.
        # Repetition handles products and sums of distinct radicals. Every
        # operation gives a necessary equality, so original verification is
        # still mandatory. Denominator clearing may add invalid-domain roots.
        for step in range(4):
            numerator = sp.together(expression).as_numer_denom()[0]
            if isinstance(numerator, sp.Abs):
                numerator = numerator.args[0]
            try:
                return exact_poly(numerator, variables)
            except sp.PolynomialError:
                if step == 3 or sp.count_ops(numerator) > 250:
                    raise ValueError("unsupported algebraic equation") from None
                atoms = [
                    atom
                    for atom in numerator.atoms(sp.Pow)
                    if atom.exp == sp.Rational(1, 2) and atom.has(*variables)
                ] + [atom for atom in numerator.atoms(sp.Abs) if atom.has(*variables)]
                if not atoms:
                    raise ValueError("unsupported algebraic equation") from None
                # Eliminate outer radicals first; their radicands can contain
                # inner radicals which the following norm will then remove.
                radical = max(
                    atoms, key=lambda atom: (sp.count_ops(atom), sp.default_sort_key(atom))
                )
                temporary = sp.Dummy("radical")
                lifted = sp.Poly(numerator.xreplace({radical: temporary}), temporary)
                if lifted.degree() > 4:
                    raise ValueError("unsupported radical degree") from None
                radicand = radical.args[0] ** 2 if isinstance(radical, sp.Abs) else radical.base
                relation = sp.Poly(temporary**2 - radicand, temporary)
                lifted = lifted.rem(relation)
                a, b = lifted.nth(0), lifted.nth(1)
                # The original real radical/absolute value is nonnegative.
                # Record the necessary sign before taking its quadratic norm;
                # root filtering still proves each coefficient's real domain.
                norm_sign_conditions.append(
                    NormSignCondition(
                        constraint_index,
                        step,
                        a,
                        b,
                        radical.args[0] if isinstance(radical, sp.Abs) else radicand,
                        isinstance(radical, sp.Abs),
                    )
                )
                if len(norm_sign_conditions) > 96:
                    raise ValueError("norm sign ledger limit") from None
                expression = sp.expand(a * a - b * b * radicand)
                if sp.count_ops(expression) > 250:
                    raise ValueError("algebraic norm expression too large") from None
        raise ValueError("unsupported algebraic equation")

    def equation_components(rows, active):
        supports = [p.as_expr().free_symbols for p in rows]
        remaining = set(active)
        components = []
        while remaining:
            component = {next(v for v in active if v in remaining)}
            while True:
                grown = component | set().union(
                    *(support for support in supports if support & component)
                )
                if grown == component:
                    break
                component = grown
            remaining -= component
            components.append([v for v in active if v in component])
        return components

    def component_product(rows, components):
        assignments = [{}]
        for component in components:
            selected = [p for p in rows if p.as_expr().free_symbols & set(component)]
            roots = finite_component(selected, component)
            if roots is None or not roots:
                return roots
            if len(assignments) * len(roots) > 16:
                return None
            assignments = [previous | root for previous in assignments for root in roots]
        return assignments

    def finite_component(reduced, active):
        """Enumerate one entire finite component, or decline the optimization."""
        if not reduced:
            # An unconstrained coordinate is not an invitation to fix a gauge.
            return None
        if len(active) > 1:
            if len(active) > 7 or any(p.total_degree() > 4 for p in reduced):
                return None
            basis = sp.groebner(reduced, *active, order="lex", extension=True)
            if basis == sp.groebner([1], *active):
                return []
            augmented = augment_zero_rows(list(basis.polys), active)
            if len(augmented) > len(basis.polys):
                basis = sp.groebner(augmented, *active, order="lex", extension=True)
                if basis == sp.groebner([1], *active):
                    return []
            if not basis.is_zero_dimensional:
                return None
            reduced = list(basis.polys)
            components = equation_components(reduced, active)
            if len(components) > 1:
                # Basis reduction can expose independence hidden in the input
                # equations. Each recursive component strictly loses variables.
                return component_product(reduced, components)
        solutions = shape_solutions(reduced, active)
        if solutions is not None:
            return solutions
        if len(active) < 2:
            return None
        return separating_shape(reduced, active)

    def shape_solutions(reduced, active):
        parameter = active[-1]
        scalar_rows = [
            exact_poly(p.as_expr(), (parameter,))
            for p in reduced
            if p.as_expr().free_symbols <= {parameter}
        ]
        if not scalar_rows:
            return None
        scalar = scalar_rows[0]
        for row in scalar_rows[1:]:
            scalar = sp.gcd(scalar, row)
        if scalar.degree() == 0:
            return []
        scalar = scalar.sqf_part()
        if scalar.degree() > 16:
            return None
        substitutions = {parameter: parameter}
        for variable in reversed(active[:-1]):
            found = None
            for row in reduced:
                # Every replacement depends only on the unchanged parameter.
                # Simultaneous symbol replacement equals sequential subs here.
                expression = row.as_expr().xreplace(substitutions)
                if not expression.free_symbols <= {variable, parameter}:
                    continue
                trial = sp.Poly(expression, variable)
                if trial.degree() != 1:
                    continue
                coefficient = exact_poly(trial.nth(1), (parameter,))
                if sp.gcd(coefficient, scalar).degree() != 0:
                    continue
                found = sp.cancel(-trial.nth(0) / trial.nth(1))
                break
            if found is None:
                return None
            substitutions[variable] = found
        work.mark("root_isolation")
        roots = scalar.real_roots(radicals=False)
        work.mark("coordinate_reconstruction")
        return [{v: substitutions[v].xreplace({parameter: root}) for v in active} for root in roots]

    def separating_shape(reduced, active):
        """Try bounded separating forms without changing the complex root set.

        Adjoining T=sum(k**i*x_i) bijectively lifts the original variety. Each
        univariate elimination polynomial f(T) vanishes on that lift; replacing
        f by its squarefree part preserves its complete complex zero set. Thus
        adding squarefree(f) removes nilpotent structure, never a geometric
        root. We still require linear coordinate rows with coprime divisors;
        a nonseparating form or remaining nilpotents simply decline this path.
        """
        for weight in (1, 2, 3):
            parameter = sp.Dummy("separating", real=True)
            coordinates = [*active, parameter]
            lift = parameter - sum(weight**i * v for i, v in enumerate(active))
            basis = sp.groebner(
                [*(p.as_expr() for p in reduced), lift],
                *coordinates,
                order="lex",
                extension=True,
            )
            scalar_rows = [
                exact_poly(p.as_expr(), (parameter,))
                for p in basis.polys
                if p.as_expr().free_symbols <= {parameter}
            ]
            if not scalar_rows:
                continue
            scalar = scalar_rows[0]
            for row in scalar_rows[1:]:
                scalar = sp.gcd(scalar, row)
            scalar = scalar.sqf_part()
            if not 1 <= scalar.degree() <= 16:
                continue
            basis = sp.groebner(
                [*(p.as_expr() for p in basis.polys), scalar.as_expr()],
                *coordinates,
                order="lex",
                extension=True,
            )
            if any(len(p.terms()) > 60 or sp.count_ops(p.as_expr()) > 250 for p in basis.polys):
                continue
            solutions = shape_solutions(list(basis.polys), coordinates)
            if solutions is not None:
                return [{v: solution[v] for v in active} for solution in solutions]
        return None

    try:
        with _bounded_symbolic_work(0.5) as interruptible:
            if not interruptible:
                work.stop_reason = "cpu_timer_unavailable"
                return None
            work.mark("polynomial_conversion")
            names = payload["variables"]
            variables = tuple(sp.Symbol(name, real=True) for name in names)
            geometry = CartesianPolynomials(dict(payload["construction"]))
            equations = []
            for constraint_index, (source, target) in enumerate(
                zip(payload["constraints"], payload["targets"], strict=True)
            ):
                target_value = geometry.scalar(geometry.parse(str(target)))
                expression = (
                    geometry.zero_relation(geometry.parse(source)) if target_value == 0 else None
                )
                if expression is None:
                    expression = geometry.scalar(geometry.parse(source)) - target_value
                if sp.count_ops(expression) > 250:
                    return None
                poly = polynomial(expression, variables, constraint_index)
                if poly.total_degree() > 8 or len(poly.terms()) > 60:
                    return None
                if not poly.is_zero:
                    equations.append(poly)
            if not equations:
                return None
            equations = augment_zero_rows(equations, variables)
            # Constant row combinations can reveal affine differences hidden
            # among distance quadratics. Keep every original equation as well.
            work.mark("affine_consequences")
            consequences = affine_polynomial_consequences(equations, variables)
            equations.extend(poly for poly, _ in consequences)
            # First eliminate exact affine rows, even in larger Cartesian models.
            work.mark("affine_elimination")
            linear = [p.as_expr() for p in equations if p.total_degree() <= 1]
            expressions = dict(zip(variables, variables, strict=True))
            active = list(variables)
            if linear:
                matrix, rhs = sp.linear_eq_to_matrix(linear, variables)
                reduced, pivots = matrix.row_join(rhs).rref()
                if len(variables) in pivots:
                    return {"points": [], "method": "inconsistent_affine_relaxation"}
                active = [v for i, v in enumerate(variables) if i not in pivots]
                expressions = {
                    v: reduced[row, -1]
                    - sum(
                        reduced[row, j] * variables[j]
                        for j in range(len(variables))
                        if j not in pivots
                    )
                    for row, i in enumerate(pivots)
                    for v in (variables[i],)
                } | {v: v for v in active}
            if not active:
                if any(p.as_expr().xreplace(expressions) != 0 for p in equations):
                    return {"points": [], "method": "inconsistent_affine_relaxation"}
                solutions = [expressions]
                method = "exact_affine_elimination"
            else:
                reduced = [exact_poly(p.as_expr().xreplace(expressions), active) for p in equations]
                reduced = [p for p in reduced if not p.is_zero]
                if not reduced:
                    return None
                if any(p.total_degree() == 0 for p in reduced):
                    return {"points": [], "method": "inconsistent_polynomial_relaxation"}
                # Disjoint equation-variable incidence components have exactly
                # the Cartesian product of their root sets. Guards and original
                # construction domains can couple components, so no component
                # is admitted separately; full original verification follows.
                work.mark("finite_elimination")
                components = equation_components(reduced, active)
                assignments = component_product(reduced, components)
                if assignments is None:
                    return None
                if not assignments:
                    return {"points": [], "method": "inconsistent_polynomial_relaxation"}
                solutions = [
                    {v: expressions[v].xreplace(assignment) for v in variables}
                    for assignment in assignments
                ]
                method = (
                    "cartesian_component_univariate_isolation"
                    if len(components) > 1
                    else "rational_univariate_isolation"
                )
            work.mark("proof_setup")
            from geosolver.engine.standard.search.algebraic_branch_boxes import (
                certified_branch_boxes,
            )

            points = []
            retained_solutions = []
            retained_root_indices = []
            excluded_roots = []
            norm_exclusion_counts = {}
            exclusion_counts = {}
            for root_index, solution in enumerate(solutions):
                work.mark("exact_guards")
                false_guard = next(
                    (
                        index
                        for index, source in enumerate(payload.get("guards", ()))
                        if exact_guard_value(source, geometry, solution) is False
                    ),
                    None,
                )
                if false_guard is not None:
                    key = str(false_guard)
                    exclusion_counts[key] = exclusion_counts.get(key, 0) + 1
                    excluded_roots.append({"root_index": root_index, "guard_index": false_guard})
                    continue
                work.mark("norm_signs")
                violated_norm = proved_norm_sign_violation(norm_sign_conditions, solution)
                if violated_norm is not None:
                    key = f"{violated_norm.constraint_index}:{violated_norm.step}"
                    norm_exclusion_counts[key] = norm_exclusion_counts.get(key, 0) + 1
                    excluded_roots.append(
                        {
                            "root_index": root_index,
                            "norm_constraint_index": violated_norm.constraint_index,
                            "norm_step": violated_norm.step,
                        }
                    )
                    continue
                work.mark("decimal_coordinates")
                values = [str(sp.N(solution[v], 180)) for v in variables]
                if not all(math.isfinite(float(value)) for value in values):
                    return None
                points.append(values)
                retained_solutions.append([solution[v] for v in variables])
                retained_root_indices.append(root_index)
            # Distinct exact configurations must remain distinct after decimal
            # serialization. Candidate IDs cannot certify coverage if rounding
            # has collapsed two isolated roots onto one HP starting point.
            if len({tuple(point) for point in points}) != len(points):
                return None
            work.mark("branch_boxes")
            boxes = certified_branch_boxes(retained_solutions, points)
            if boxes is None:
                return None
            return {
                "points": points,
                "branch_boxes": boxes,
                "retained_root_indices": retained_root_indices,
                "excluded_roots": excluded_roots,
                "original_root_count": len(solutions),
                "method": method,
                "proved_guard_exclusions": sum(exclusion_counts.values()),
                "false_original_guard_counts": exclusion_counts,
                "affine_consequence_count": len(consequences),
                "squarefree_consequence_count": consequence_counts["squarefree"],
                "sos_consequence_count": consequence_counts["sos"],
                "norm_sign_condition_count": len(norm_sign_conditions),
                "proved_norm_sign_exclusions": sum(norm_exclusion_counts.values()),
                "norm_sign_exclusion_counts": norm_exclusion_counts,
            }
    except (
        AlgebraicWorkLimit,
        ValueError,
        TypeError,
        KeyError,
        ZeroDivisionError,
        sp.polys.polyerrors.BasePolynomialError,
        NotImplementedError,
    ) as exc:
        work.interrupted_phase = work.current
        work.stop_reason = (
            "inner_cpu_timeout" if isinstance(exc, AlgebraicWorkLimit) else type(exc).__name__
        )
        return None


def search_algebraic_branches(*, bundle, evaluator):
    """Create proposals only; the ordinary HP refinement and verifier follow."""
    if not _eligible(bundle):
        return None
    from geosolver.engine.standard.contracts.candidate_record import (
        FloatCandidate,
        SearchBatchResult,
    )
    from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
    from geosolver.runtime.symbolic import OptionalSymbolicTimeout, request

    try:
        data = request(
            "algebraic_branches",
            {
                "variables": bundle.var_names,
                "construction": [(item.name, item.expr) for item in bundle.spec.construction],
                "constraints": bundle.spec.constraints,
                "targets": bundle.targets,
                "guards": bundle.spec.guards,
            },
            timeout_seconds=1.5,
        )
    except OptionalSymbolicTimeout:
        return None
    if data is None or not data["points"]:
        return None
    records = []
    for index, decimal_point in enumerate(data["points"]):
        root_index = data.get("retained_root_indices", range(len(data["points"])))[index]
        point = tuple(map(float, decimal_point))
        evaluation = evaluator.evaluate_float_residual(point)
        if evaluation.evaluation_status is not EvaluationStatus.OK:
            # Float arithmetic may collapse a valid small separation. Keep the
            # normal search path unless every root can be represented safely.
            return None
        guard_ok, violations = evaluator.evaluate_guard(point)
        # Invalid relaxation roots still go to original HP checks. Admission
        # must not depend on a squared equation or rounded branch boundary.
        records.append(
            FloatCandidate(
                x_float=point,
                score=evaluation.residual_norm_float**2,
                residual_norm_float=evaluation.residual_norm_float,
                guard_ok=guard_ok,
                evaluation_status=evaluation.evaluation_status,
                origin_seed=-1,
                origin_start_point_index=root_index,
                candidate_id=900000 + root_index,
                hard_violation_tags=tuple(violations),
                origin_backend="exact_polynomial",
                origin_evaluation_index=root_index,
                initial_point_decimal=tuple(decimal_point),
                originating_branch_box=tuple(
                    tuple(axis)
                    for axis in data.get("branch_boxes", [()] * len(data["points"]))[index]
                ),
            )
        )
    return SearchBatchResult(
        candidates=tuple(records),
        all_records=tuple(records),
        evaluation_count=len(records),
        failure_ratio=0,
        evaluation_failure_count=0,
        search_diagnostics={
            "algebraic_branch_discovery": {
                "method": data["method"],
                "exhaustive_polynomial_relaxation": True,
                "branch_count": len(records),
                "original_root_count": data.get("original_root_count", len(records)),
                "retained_root_indices": data.get(
                    "retained_root_indices", list(range(len(records)))
                ),
                "excluded_roots": data.get("excluded_roots", []),
                "affine_consequence_count": data.get("affine_consequence_count", 0),
                "squarefree_consequence_count": data.get("squarefree_consequence_count", 0),
                "sos_consequence_count": data.get("sos_consequence_count", 0),
                "norm_sign_condition_count": data.get("norm_sign_condition_count", 0),
                "proved_norm_sign_exclusions": data.get("proved_norm_sign_exclusions", 0),
                "norm_sign_exclusion_counts": data.get("norm_sign_exclusion_counts", {}),
                "proved_guard_exclusions": data.get("proved_guard_exclusions", 0),
                "false_original_guard_counts": data.get("false_original_guard_counts", {}),
            }
        },
    )
