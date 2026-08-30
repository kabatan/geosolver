"""Branch-aware differences and scaled local correction for final verification.

These are numerical error estimates, not interval existence certificates.
The search/refinement Jacobian is intentionally unchanged.
"""

import ast
from dataclasses import dataclass, replace

from mpmath import mp

from geosolver.engine.standard.evaluation.selection_trace import capture_selection_trace
from geosolver.engine.standard.evaluation.verification_sampling import precision_sample
from geosolver.problem.expression_source import source_expression
from geosolver.problem.ir.compiler import extract_names
from geosolver.problem.ir.errors import IRCompileError
from geosolver.runtime.deadline import check_deadline

DIFFERENCE_REFINEMENTS = 8
DIFFERENCE_SHRINK = 100


def _difference_step(scale, precision):
    return scale * mp.power(10, -max(20, precision // 3))


def _unresolved_coordinate_error(scale, precision):
    # Rank failure is not evidence of an exact free parameter. Keep at least
    # the resolution of the smallest probe the differentiator can distinguish.
    # This shrinks with precision and scales with the variable, not the equation.
    return _difference_step(scale, precision) / (2 * DIFFERENCE_SHRINK**DIFFERENCE_REFINEMENTS)


def same_branches(base, shifted):
    if len(base) != len(shifted):
        return False
    for a, b in zip(base, shifted, strict=True):
        if a.call_site_id != b.call_site_id or a.kind != b.kind:
            return False
        if a.candidate_count != b.candidate_count or not a.candidates or not b.candidates:
            return False
        if len(a.candidates) == 1:
            continue
        distances = [[mp.hypot(x - u, y - v) for u, v in b.candidates] for x, y in a.candidates]
        i, j = a.selected_index, b.selected_index
        if distances[i].count(min(distances[i])) != 1:
            return False
        column = [row[j] for row in distances]
        if column.count(min(column)) != 1:
            return False
        if distances[i][j] != min(distances[i]) or distances[i][j] != min(column):
            return False
        x, y = a.candidates[i]
        separation = min(mp.hypot(x - u, y - v) for k, (u, v) in enumerate(a.candidates) if k != i)
        if distances[i][j] >= separation / 4:
            return False
    return True


def differentiate(function, point, index, scale, precision, base=None, *, allow_nonsmooth=False):
    """Return (derivative, error), or None. Never use a branch jump as slope."""
    check_deadline()
    base = function(point) if base is None else base
    value, trace = base[:2]
    base_error = base[2] if len(base) > 2 else mp.eps * abs(value) * 32
    if not mp.isfinite(value):
        return None
    step = _difference_step(max(abs(point[index]), scale), precision)
    if step == 0:
        return None

    def slope(h):
        samples, noises = [], []
        for sign in (1, -1):
            shifted = list(point)
            shifted[index] += sign * h
            try:
                evaluated = function(tuple(shifted))
                sample, branch = evaluated[:2]
                noise = evaluated[2] if len(evaluated) > 2 else mp.eps * abs(sample) * 32
                valid = mp.isfinite(sample) and mp.isfinite(noise) and same_branches(trace, branch)
            except (ValueError, ArithmeticError, TypeError, IRCompileError):
                sample, noise, valid = mp.nan, mp.inf, False
            samples.append(sample if valid else None)
            noises.append(noise if valid else mp.mpf(0))
        plus, minus = samples
        noise = (base_error + sum(noises)) / h
        if plus is not None and minus is not None:
            # A cusp has nonconverging one-sided slopes. A smooth extremum has
            # slopes which approach each other, even when its derivative is zero.
            gap = abs((plus - value) / h - (value - minus) / h)
            return (plus - minus) / (2 * h), noise, gap
        if plus is not None:
            return (plus - value) / h, noise, None
        if minus is not None:
            return (value - minus) / h, noise, None
        return None

    for _ in range(DIFFERENCE_REFINEMENTS + 1):
        check_deadline()
        coarse, fine = slope(step), slope(step / 2)
        if coarse is not None and fine is not None:
            error = abs(coarse[0] - fine[0]) + coarse[1] + fine[1]
            smooth = (
                coarse[2] is None
                or fine[2] is None
                or (fine[2] <= mp.mpf("0.75") * coarse[2] + 4 * (coarse[1] + fine[1]))
            )
            if smooth:
                # An absolute error estimate is useful even if the interval
                # contains zero. Rank selection excludes slopes below that error;
                # boundary propagation may still certify a large positive margin.
                return fine[0], 4 * error
            if allow_nonsmooth and fine[2] <= mp.mpf("1.25") * coarse[2] + 4 * (
                coarse[1] + fine[1]
            ):
                # min/max/abs margins need a bound on local variation, not a
                # unique derivative. Keep both one-sided slopes in the interval.
                # A jump instead grows as 1/h and cannot pass this condition.
                return fine[0], 4 * max(error, coarse[2], fine[2])
        step /= DIFFERENCE_SHRINK
    return None


@dataclass(frozen=True)
class Equation:
    evaluator: object
    names: frozenset[str]
    constant: object
    source: str
    scale_evaluator: object = None

    def evaluate(self, point, precision):
        check_deadline()
        with capture_selection_trace() as trace:
            result = self.evaluator.evaluate_hp_residual(point, precision=precision)
        return (result.residual_vector[0] if result.is_finite else mp.nan, tuple(trace))

    def sample(self, point, precision):
        return precision_sample(lambda p: self.evaluate(p, mp.dps), point, precision)

    def term_scale(self, point, precision):
        if self.scale_evaluator is None:
            return mp.mpf(0)
        result = self.scale_evaluator.evaluate_hp_residual(point, precision=precision)
        return max((abs(v) for v in result.residual_vector), default=mp.mpf(0))


def _additive_terms(source):
    def walk(node):
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add | ast.Sub):
            yield from walk(node.left)
            yield from walk(node.right)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            yield from walk(node.operand)
        else:
            yield source_expression(node, source)

    return list(walk(ast.parse(source, mode="eval").body))


def _smooth_zero_equation(source):
    """Rewrite only zero-preserving outer operations, never arbitrary subterms.

    Area and abs keep their public meanings. This representation is used only
    for an equality whose complete normalized residual must be zero.
    """

    def walk(node):
        if isinstance(node, ast.IfExp):
            return (
                f"({walk(node.body)}) if ({source_expression(node.test, source)}) "
                f"else ({walk(node.orelse)})"
            )
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd | ast.USub):
            return ("-" if isinstance(node.op, ast.USub) else "+") + "(" + walk(node.operand) + ")"
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult | ast.Div):
            # The denominator is not required to be zero and must not be changed.
            left = walk(node.left)
            right = (
                walk(node.right)
                if isinstance(node.op, ast.Mult)
                else source_expression(node.right, source)
            )
            return f"({left}){'*' if isinstance(node.op, ast.Mult) else '/'}({right})"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and not node.keywords:
            if node.func.id in {"abs", "Abs"} and len(node.args) == 1:
                return walk(node.args[0])
            if node.func.id == "Area" and len(node.args) == 3:
                a, b, c = (f"({source_expression(arg, source)})" for arg in node.args)
                return f"(({b}.x-{a}.x)*({c}.y-{a}.y)-({b}.y-{a}.y)*({c}.x-{a}.x))/2"
            if node.func.id == "Distance" and len(node.args) == 2:
                point, line = node.args
                if (
                    isinstance(line, ast.Call)
                    and isinstance(line.func, ast.Name)
                    and line.func.id == "Line"
                    and len(line.args) == 2
                ):
                    p, a, b = (f"({source_expression(arg, source)})" for arg in (point, *line.args))
                    # Retain the line's nondegeneracy domain. A bare cross
                    # product would silently accept coincident endpoints.
                    return (
                        f"(({b}.x-{a}.x)*({p}.y-{a}.y)-"
                        f"({b}.y-{a}.y)*({p}.x-{a}.x))/Distance({a},{b})"
                    )
            if (
                node.func.id == "min"
                and node.args
                and all(
                    isinstance(arg, ast.Call)
                    and isinstance(arg.func, ast.Name)
                    and arg.func.id in {"Distance", "abs", "Abs"}
                    for arg in node.args
                )
            ):
                result = walk(node.args[-1])
                for i in reversed(range(len(node.args) - 1)):
                    condition = " and ".join(
                        f"({source_expression(node.args[i], source)})<="
                        f"({source_expression(other, source)})"
                        for other in node.args[i + 1 :]
                    )
                    result = f"({walk(node.args[i])}) if ({condition}) else ({result})"
                return result
        return source_expression(node, source)

    return walk(ast.parse(source, mode="eval").body)


def prepare_equations(evaluator):
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator

    equations = []
    from geosolver.runtime.symbolic import request

    normalized = request(
        "normalize",
        [
            (source, str(evaluator.bundle.targets[i]))
            for i, source in enumerate(evaluator.bundle.spec.constraints)
        ],
    )
    for index, _source in enumerate(evaluator.bundle.spec.constraints):
        text, constant = normalized[index]
        text = _smooth_zero_equation(text)
        names = set(extract_names(text))
        needed = []
        for item in reversed(evaluator.bundle.spec.construction):
            if item.name in names:
                needed.append(item)
                names.update(extract_names(item.expr))
        spec = replace(
            evaluator.bundle.spec,
            construction=list(reversed(needed)),
            constraints=[text],
            v=[0],
            m=None,
        )
        bundle = replace(evaluator.bundle, spec=spec, targets=(0,))
        terms = _additive_terms(text)
        scale_evaluator = None
        if len(terms) > 1 and constant is None:
            scale_spec = replace(spec, constraints=terms, v=[0] * len(terms))
            scale_evaluator = build_ir_evaluator(
                replace(bundle, spec=scale_spec, targets=(0,) * len(terms))
            )
        equations.append(
            Equation(build_ir_evaluator(bundle), frozenset(names), constant, text, scale_evaluator)
        )
    return tuple(equations)


def linearization(equations, point, names, scales, precision):
    residuals, jacobian, errors, term_scales = [], [], [], []
    for equation in equations:
        base = equation.sample(point, precision)
        residuals.append(base[0])
        term_scales.append(max(equation.term_scale(point, precision), base[2] / mp.eps))
        row, err = [], []
        for j, name in enumerate(names):
            if name not in equation.names:
                derivative = (mp.mpf(0), mp.mpf(0))
            else:
                derivative = differentiate(
                    lambda p, equation=equation: equation.sample(p, precision),
                    point,
                    j,
                    scales[j],
                    precision,
                    base,
                )
            row.append(mp.mpf(0) if derivative is None else derivative[0])
            err.append(mp.inf if derivative is None else derivative[1])
        jacobian.append(row)
        errors.append(err)
        # Two arithmetic precisions can both round a cancelling primitive to
        # zero. Never infer zero coordinate error from that coincidence. The
        # locally resolved sensitivities provide a scale-covariant roundoff
        # floor, including when all explicit additive terms vanished.
        term_scales[-1] = max(
            term_scales[-1],
            mp.fsum(abs(d) * s for d, s, e in zip(row, scales, err, strict=True) if mp.isfinite(e)),
        )
    return residuals, jacobian, errors, term_scales


def correction(
    residuals, jacobian, errors, scales, precision, evaluation_scales=None, active_columns=None
):
    from geosolver.engine.standard.refinement.mpmath_refiner import _select_rank_revealing_subsystem

    row_scales = [
        max([abs(r)] + [abs(d) * s for d, s in zip(row, scales, strict=True)])
        for r, row in zip(residuals, jacobian, strict=True)
    ]
    matrix = [
        [d * s / rs if rs else mp.mpf(0) for d, s in zip(row, scales, strict=True)]
        for row, rs in zip(jacobian, row_scales, strict=True)
    ]
    reliable = []
    for i, (row, err, rs) in enumerate(zip(jacobian, errors, row_scales, strict=True)):
        signal = mp.fsum(abs(d) * s for d, s in zip(row, scales, strict=True))
        noise = mp.fsum(e * s for e, s in zip(err, scales, strict=True))
        if rs and mp.isfinite(noise) and signal > 100 * noise:
            reliable.append(i)
        else:
            matrix[i] = [mp.mpf(0)] * len(scales)
    error_bound = max(
        [mp.eps * 100]
        + [e * s / row_scales[i] for i in reliable for e, s in zip(errors[i], scales, strict=True)]
    )
    # A numerically flat redundant row must neither become an independent
    # equation nor inflate the rank tolerance of otherwise reliable rows.
    chart = _select_rank_revealing_subsystem(
        matrix, dps=precision, relative_tolerance=100 * error_bound
    )
    active = set(range(len(scales))) if active_columns is None else set(active_columns)
    unresolved = [
        _unresolved_coordinate_error(s, precision) if j in active else mp.mpf(0)
        for j, s in enumerate(scales)
    ]
    if chart is None:
        if evaluation_scales is not None and all(
            abs(r) <= mp.eps * s for r, s in zip(residuals, evaluation_scales, strict=True)
        ):
            return tuple(mp.mpf(0) for _ in scales), tuple(unresolved)
        return tuple(mp.mpf(0) for _ in scales), tuple(
            mp.inf if any(residuals) and j in active else unresolved[j] for j in range(len(scales))
        )
    rows, columns = chart
    a = mp.matrix([[matrix[i][j] for j in columns] for i in rows])
    b = mp.matrix([-residuals[i] / row_scales[i] for i in rows])
    try:
        delta = mp.lu_solve(a, b)
        inverse = a**-1
    except (ValueError, ZeroDivisionError):
        return None, None
    change = [mp.mpf(0)] * len(scales)
    uncertainty = unresolved.copy()
    unselected = active.difference(columns)
    for k, j in enumerate(columns):
        change[j] = delta[k] * scales[j]
        propagated = mp.fsum(
            abs(inverse[k, column_index])
            * (
                mp.eps
                * 32
                * (evaluation_scales[i] / row_scales[i] if evaluation_scales is not None else 1)
                + mp.fsum(
                    errors[i][c] * scales[c] / row_scales[i] * abs(delta[q])
                    for q, c in enumerate(columns)
                )
                + mp.fsum(
                    (abs(jacobian[i][c]) + errors[i][c]) * unresolved[c] / row_scales[i]
                    for c in unselected
                )
            )
            for column_index, i in enumerate(rows)
        )
        uncertainty[j] = abs(change[j]) + propagated * scales[j]
    return tuple(change), tuple(uncertainty)


def normalized_error(equations, residuals, jacobian, errors, scales, previous, term_scales):
    result = []
    for i, (eq, residual, row, err) in enumerate(
        zip(equations, residuals, jacobian, errors, strict=True)
    ):
        if eq.constant is not None:
            result.append(mp.mpf(0) if eq.constant == 0 else mp.inf)
            continue
        if residual == 0:
            result.append(mp.mpf(0))
            continue
        if not mp.isfinite(residual) or not mp.isfinite(term_scales[i]):
            result.append(mp.inf)
            continue
        sensitivity = mp.fsum(
            max(0, abs(d) - e) * s
            for d, e, s in zip(row, err, scales, strict=True)
            if mp.isfinite(e)
        )
        # Unknown slopes contribute nothing. Independent term magnitudes remain
        # usable for identities such as Distance(A,D)-p*Distance(A,B). Common
        # arithmetic terms were cancelled first, so a huge shared constant cannot
        # conceal a contradiction here.
        denominator = max(abs(residual), term_scales[i], sensitivity)
        if sensitivity == 0 and previous is not None:
            denominator = max(denominator, abs(previous[i] - residual))
        result.append(abs(residual) / denominator if denominator else mp.inf)
    return max(result, default=mp.mpf(0))
