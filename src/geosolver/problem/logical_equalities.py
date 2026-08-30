"""Lower pure equality formulae to signed, branch-selected residual vectors.

The selected conjunction minimizes its maximum absolute residual. Thus the
vector vanishes iff at least one conjunction holds. No branch is deleted, and
the original logical guard remains a final check.
"""

from dataclasses import replace
from functools import lru_cache
from itertools import product


def _clauses(guard):
    if guard.kind == "compare" and guard.operator == "==":
        return ((f"({guard.lhs_expr})-({guard.rhs_expr})",),)
    if guard.kind not in {"logical_and", "logical_or"} or not guard.children:
        return None
    children = [_clauses(child) for child in guard.children]
    if any(child is None for child in children):
        return None
    if guard.kind == "logical_or":
        result = tuple(clause for child in children for clause in child)
    else:
        size = 1
        for child in children:
            size *= len(child)
        if size > 32:
            return None
        result = tuple(
            tuple(expr for clause in combination for expr in clause)
            for combination in product(*children)
        )
    return result if len(result) <= 32 and max(map(len, result), default=0) <= 16 else None


@lru_cache(maxsize=1024)
def residual_sources(guards):
    from geosolver.engine.standard.interpreter.guards.compile import compile_guards

    expressions = []
    for guard in compile_guards(guards):
        clauses = _clauses(guard)
        if not clauses:
            continue
        scores = [
            "abs(" + c[0] + ")"
            if len(c) == 1
            else "max(" + ",".join("abs(" + r + ")" for r in c) + ")"
            for c in clauses
        ]
        for column in range(max(map(len, clauses))):
            choices = [clause[column] if column < len(clause) else "0" for clause in clauses]
            expression = choices[-1]
            for i in reversed(range(len(clauses) - 1)):
                condition = " and ".join(f"({scores[i]})<=({s})" for s in scores[i + 1 :])
                expression = f"({choices[i]}) if ({condition}) else ({expression})"
            expressions.append(expression)
    return tuple(expressions)


def lower_logical_equalities(spec):
    extra = residual_sources(tuple(spec.guards))
    if not extra:
        return spec
    return replace(
        spec,
        constraints=[*spec.constraints, *extra],
        v=[*(spec.v or [0] * len(spec.constraints)), *([0] * len(extra))],
        m=None,
    )
