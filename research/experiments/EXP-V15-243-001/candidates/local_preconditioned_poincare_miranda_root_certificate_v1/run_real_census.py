#!/usr/bin/env python3
"""Aggregate-only real readiness census for local Poincare--Miranda."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import itertools
import json
import math
from pathlib import Path
import signal
import subprocess
import sys
import time

import sympy as sp

from candidate import bernstein_range


STAGES = (
    "input_loaded",
    "runtime_built",
    "symbolic_compiled",
    "typed_polynomial",
    "canonical_replay_compiled",
    "square_or_exact_consequence",
    "target_identity",
    "local_box_proposed",
    "pm_faces",
    "canonical_replay_proved",
    "target_range_proved",
    "ready",
)
MAX_DIMENSION = 3
MAX_DEGREE = 6
MAX_FACE_COEFFICIENT_HEIGHT = 4096
ENDPOINT_DENOMINATOR = 4096
PRECONDITIONER_DENOMINATOR = 65536
BOX_FLOOR = sp.Rational(1, 64)
RECORD_SECONDS = 3.0


@contextlib.contextmanager
def _record_deadline():
    previous = signal.getsignal(signal.SIGALRM)

    def timeout(_signum, _frame):
        raise TimeoutError("record static/proof deadline")

    signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, RECORD_SECONDS)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def _zero(expression):
    value = sp.factor(sp.cancel(sp.together(expression)))
    return value == 0 or value.is_zero is True or value.equals(0) is True


def _round_rational(value, denominator):
    rational = sp.Rational(str(float(value)))
    scaled = rational * denominator
    rounded = sp.floor(scaled + sp.Rational(1, 2)) if scaled >= 0 else sp.ceiling(scaled - sp.Rational(1, 2))
    return sp.Rational(rounded, denominator)


def _load_runtime(runtime_root: Path):
    source_root = runtime_root.parents[2]
    geosolver_root = runtime_root / "geosolver" / "src"
    for path in (source_root, geosolver_root):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from geotarget.continuation import _load_frozen

    base = _load_frozen(runtime_root)
    runtime = base._load_module("geotarget_pm_real_census_runtime", base.PRECISION_RUNTIME)
    return runtime


def _build_context(bundle):
    from geosolver.ir.compiler import safe_eval_expr
    from geotarget.lazy_symbolic_geometry import (
        LazyCompilationLimits,
        LazyGeometryState,
        build_lazy_geometry_context,
    )

    limits = LazyCompilationLimits(
        max_ast_nodes=200_000,
        max_dag_nodes=4_096,
        max_expression_input_cost=20_000,
        wall_seconds=1.0,
    )
    state = LazyGeometryState(limits=limits)
    geometry, state = build_lazy_geometry_context(state)
    symbols = tuple(sp.Symbol(name) for name in bundle.var_names)
    context = dict(bundle.base_context)
    context.update(geometry)
    context.update(dict(zip(bundle.var_names, symbols, strict=True)))
    for item in bundle.spec.construction:
        context[item.name] = safe_eval_expr(item.expr, context)
    return context, symbols, state, safe_eval_expr


def _guard_obligations(bundle, context, safe_eval_expr):
    from geosolver._internal.autosolve.guards.compile import compile_guards

    obligations = []

    def evaluate(text):
        value = safe_eval_expr(text, context)
        if not isinstance(value, (sp.Basic, int, float)):
            raise TypeError("guard expression is not scalar")
        return sp.sympify(value)

    def compile_one(guard):
        kind = guard.kind
        if kind == "logical_and":
            for child in guard.children:
                compile_one(child)
            return
        if kind == "compare":
            difference = evaluate(guard.lhs_expr) - evaluate(guard.rhs_expr)
            if guard.operator == "==":
                obligations.append(("zero", difference))
            elif guard.operator == "!=":
                obligations.append(("nonzero", difference))
            elif guard.operator in (">", ">="):
                obligations.append(("positive", difference))
            elif guard.operator in ("<", "<="):
                obligations.append(("positive", -difference))
            else:
                raise ValueError("unsupported compare")
            return
        if kind in ("bound", "bound_open"):
            if guard.lower_expr is None or guard.upper_expr is None:
                raise ValueError("unresolved bound")
            value = evaluate(guard.lhs_expr)
            obligations.append(("positive", value - evaluate(guard.lower_expr)))
            obligations.append(("positive", evaluate(guard.upper_expr) - value))
            return
        if kind == "residual":
            obligations.append(("zero", evaluate(guard.residual_expr)))
            return
        raise ValueError("guard does not have a reversible semialgebraic cover")

    for guard in compile_guards(bundle.spec.guards):
        compile_one(guard)
    return obligations


def _static_compile(document, evaluator):
    from geotarget.lazy_symbolic_geometry import (
        LazyCompilationLimits,
        try_expand_bundle_symbolically,
    )

    bundle = evaluator.bundle
    limits = LazyCompilationLimits(
        max_ast_nodes=200_000,
        max_dag_nodes=4_096,
        max_expression_input_cost=20_000,
        wall_seconds=1.0,
    )
    expansion_result = try_expand_bundle_symbolically(bundle, limits=limits)
    if expansion_result.expansion is None:
        raise ValueError("symbolic expansion rejected")
    expansion = expansion_result.expansion
    context, symbols, guard_state, safe_eval_expr = _build_context(bundle)
    answer = safe_eval_expr(str(document["answer"]), context)
    if not isinstance(answer, (sp.Basic, int, float)):
        raise TypeError("answer is not scalar")
    residuals = tuple(left - right for left, right in expansion.sides)
    obligations = _guard_obligations(bundle, context, safe_eval_expr)
    validations = (*expansion.validations, *guard_state.validations)
    for validation in validations:
        if validation.kind == "nonzero":
            obligations.append(("nonzero", sp.sympify(validation.expression)))
        elif validation.kind == "nonnegative":
            obligations.append(("positive", sp.sympify(validation.expression)))
        elif validation.kind == "nonzero_vector":
            obligations.append(("positive", sum(sp.sympify(value) ** 2 for value in validation.expression)))
        else:
            raise ValueError("unsupported deferred validation")
    if expansion.selectors or guard_state.selectors:
        raise ValueError("selector branch lacks exact full-box cover")
    return symbols, residuals, sp.sympify(answer), tuple(obligations)


def _polynomial_compile(symbols, residuals, answer, obligations):
    normalized = []
    for expression in (*residuals, answer, *(expression for _kind, expression in obligations)):
        polynomial = sp.Poly(expression, *symbols, domain=sp.QQ)
        if polynomial.total_degree() > MAX_DEGREE:
            raise ValueError("degree limit")
        normalized.append(polynomial.as_expr())
    residual_count = len(residuals)
    normalized_residuals = tuple(normalized[:residual_count])
    normalized_answer = normalized[residual_count]
    normalized_obligations = tuple(
        (kind, value)
        for (kind, _expression), value in zip(
            obligations, normalized[residual_count + 1 :], strict=True
        )
    )
    return normalized_residuals, normalized_answer, normalized_obligations


def _runtime_snapshot(runtime_root: Path):
    source_root = runtime_root.parents[2]
    repository = subprocess.run(
        ("git", "-C", str(source_root), "rev-parse", "--show-toplevel"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    commit = subprocess.run(
        ("git", "-C", repository, "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ("git", "-C", repository, "status", "--porcelain=v1", "--untracked-files=all"),
        check=True,
        capture_output=True,
    ).stdout
    digest = hashlib.sha256()
    digest.update(commit.encode() + b"\0" + status + b"\0")
    files = sorted((source_root / "geotarget").rglob("*.py"))
    for path in files:
        relative = path.relative_to(source_root)
        digest.update(str(relative).encode() + b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return {
        "commit": commit,
        "tree_sha256": digest.hexdigest(),
        "file_count": len(files),
    }


def _exact_subset(residuals, symbols, relation, answer, active_indices):
    active = tuple(residuals[index] for index in active_indices)
    basis = sp.groebner(active, *symbols, order="grevlex", domain=sp.QQ)
    omitted = tuple(index for index in range(len(residuals)) if index not in active_indices)
    for index in omitted:
        if not _zero(basis.reduce(residuals[index])[1]):
            return None
    coefficient, constant = map(sp.Integer, relation)
    if coefficient == 0:
        return None
    target_relation = sp.expand(coefficient * answer + constant)
    if not _zero(basis.reduce(target_relation)[1]):
        return None
    return active, -sp.Rational(constant, coefficient)


def _proposal(active, symbols, endpoint):
    center = tuple(_round_rational(value, ENDPOINT_DENOMINATOR) for value in endpoint)
    substitutions = dict(zip(symbols, center, strict=True))
    jacobian = sp.Matrix(active).jacobian(symbols)
    at_center = jacobian.subs(substitutions)
    if _zero(at_center.det()):
        A = sp.eye(len(symbols))
    else:
        exact_inverse = at_center.inv()
        A = exact_inverse.applyfunc(lambda value: _round_rational(value, PRECONDITIONER_DENOMINATOR))
    if _zero(A.det()):
        return None
    residual = sp.Matrix(active).subs(substitutions)
    correction = -A * residual
    radii = tuple(BOX_FLOOR + 2 * abs(sp.Rational(value)) for value in correction)
    box = {
        symbol: (center_value - radius, center_value + radius)
        for symbol, center_value, radius in zip(symbols, center, radii, strict=True)
    }
    return A, box


def _prove(active, symbols, answer, target_root, obligations, A, box):
    G = tuple(sp.expand(value) for value in A * sp.Matrix(active))
    orientations = []
    max_face_height = 0
    for symbol, expression in zip(symbols, G, strict=True):
        other = tuple(value for value in symbols if value != symbol)
        lower, upper = box[symbol]
        low = bernstein_range(expression.subs(symbol, lower), other, box)
        high = bernstein_range(expression.subs(symbol, upper), other, box)
        max_face_height = max(max_face_height, low[2], high[2])
        if max_face_height > MAX_FACE_COEFFICIENT_HEIGHT:
            return None
        if low[1] < 0 and high[0] > 0:
            orientations.append(1)
        elif low[0] > 0 and high[1] < 0:
            orientations.append(-1)
        else:
            return None

    for kind, expression in obligations:
        if kind == "zero":
            if not _zero(expression):
                return None
            continue
        lower, upper, _height = bernstein_range(expression, symbols, box)
        if kind == "positive" and lower <= 0:
            return None
        if kind == "nonzero" and not (lower > 0 or upper < 0):
            return None

    answer_range = bernstein_range(answer, symbols, box)
    isolator = (target_root - 1, target_root + 1)
    if not (isolator[0] < answer_range[0] and answer_range[1] < isolator[1]):
        return None
    signature = (
        len(symbols),
        tuple(sp.Poly(value, *symbols).total_degree() for value in active),
        tuple(orientations),
        len(obligations),
        bool(bernstein_range(sp.Matrix(active).jacobian(symbols).det(), symbols, box)[0] <= 0 <= bernstein_range(sp.Matrix(active).jacobian(symbols).det(), symbols, box)[1]),
    )
    return signature


def _census(manifest_path: Path, runtime_root: Path):
    requests = json.loads(manifest_path.read_text(encoding="utf-8"))
    runtime = _load_runtime(runtime_root)
    counts = {stage: 0 for stage in STAGES}
    signatures = set()

    for request in requests:
        reached = {stage: False for stage in STAGES}
        reached["input_loaded"] = True
        try:
            with _record_deadline():
                source_path = Path(request["source_path"])
                if not source_path.is_absolute():
                    source_path = (manifest_path.parent / source_path).resolve()
                document = json.loads(source_path.read_text(encoding="utf-8"))
                _case, _budget, evaluator = runtime.build_source_case(
                    document,
                    callback_cap=1,
                    deadline=time.monotonic() + RECORD_SECONDS,
                )
                reached["runtime_built"] = True
                symbols, residuals, answer, obligations = _static_compile(document, evaluator)
                reached["symbolic_compiled"] = True
                if not 1 <= len(symbols) <= MAX_DIMENSION or len(residuals) < len(symbols):
                    raise ValueError("dimension")
                residuals, answer, obligations = _polynomial_compile(
                    symbols, residuals, answer, obligations
                )
                reached["typed_polynomial"] = True
                reached["canonical_replay_compiled"] = True
                relation = request["candidate_relation_high_to_low"]
                if len(relation) != 2:
                    raise ValueError("not degree one")
                subset_exact = False
                target_exact = False
                box_proposed = False
                pm_proved = False
                replay_proved = False
                target_proved = False
                ready_signature = None
                for active_indices in itertools.combinations(range(len(residuals)), len(symbols)):
                    exact = _exact_subset(residuals, symbols, relation, answer, active_indices)
                    if exact is None:
                        continue
                    subset_exact = True
                    target_exact = True
                    active, target_root = exact
                    proposal = _proposal(active, symbols, request["endpoint"])
                    if proposal is None:
                        continue
                    box_proposed = True
                    A, box = proposal
                    proof = _prove(active, symbols, answer, target_root, obligations, A, box)
                    if proof is None:
                        continue
                    pm_proved = replay_proved = target_proved = True
                    ready_signature = proof
                    break
                reached["square_or_exact_consequence"] = subset_exact
                reached["target_identity"] = target_exact
                reached["local_box_proposed"] = box_proposed
                reached["pm_faces"] = pm_proved
                reached["canonical_replay_proved"] = replay_proved
                reached["target_range_proved"] = target_proved
                reached["ready"] = ready_signature is not None
                if ready_signature is not None:
                    signatures.add(ready_signature)
        except Exception:
            pass
        for stage in STAGES:
            counts[stage] += int(reached[stage])

    ready = counts["ready"]
    signature_count = len(signatures)
    return {
        "schema": "geotarget.local-pm-real-readiness-census/v1",
        "input_count": len(requests),
        "stage_counts": counts,
        "anonymous_signature_count": signature_count,
        "decision": "REAL_GATE_PASS" if ready >= 4 and signature_count >= 2 else "REAL_GATE_STOP",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    arguments = parser.parse_args()
    runtime_root = arguments.runtime_root.resolve()
    before = _runtime_snapshot(runtime_root)
    result = _census(arguments.manifest.resolve(), runtime_root)
    after = _runtime_snapshot(runtime_root)
    unchanged = before == after
    result["runtime_provenance"] = {
        "commit": before["commit"],
        "pre_sha256": before["tree_sha256"],
        "post_sha256": after["tree_sha256"],
        "file_count": before["file_count"],
        "unchanged": unchanged,
    }
    if not unchanged:
        result["decision"] = "INVALID_RUNTIME_CHANGED"
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
