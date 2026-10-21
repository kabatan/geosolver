"""Lower pure equality formulae to signed, branch-selected residual vectors.

The selected conjunction minimizes its maximum absolute residual. Thus the
vector vanishes iff at least one conjunction holds. No branch is deleted, and
the original logical guard remains a final check.
"""

import ast
import hashlib
from dataclasses import dataclass, replace
from functools import cached_property, lru_cache
from itertools import product

LOGICAL_CONTEXT = "_logical_residuals"
SMOOTH_LOGICAL_CONTEXT = "_logical_smooth_residuals"


@dataclass(frozen=True)
class LogicalEqualityPlan:
    """A bounded disjunction, retaining original leaf source and tie order."""

    clauses: tuple[tuple[str, ...], ...]
    context_name: str = LOGICAL_CONTEXT

    @property
    def smooth_context_name(self):
        return self.context_name.replace(LOGICAL_CONTEXT, SMOOTH_LOGICAL_CONTEXT, 1)

    @cached_property
    def identity(self):
        return hashlib.sha256(repr(self.clauses).encode()).hexdigest()[:24]

    @cached_property
    def leaves(self):
        return tuple(dict.fromkeys(source for clause in self.clauses for source in clause))

    @cached_property
    def width(self):
        return max(map(len, self.clauses))

    @cached_property
    def components(self):
        return tuple(f"{self.context_name}[{self.identity!r}][{i}]" for i in range(self.width))


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
def logical_plans(guards, context_name=LOGICAL_CONTEXT, constructions=()):
    from geosolver.engine.standard.interpreter.guards.compile import compile_guards
    from geosolver.problem.incidence_residuals import augment_incidence_clauses

    return tuple(
        LogicalEqualityPlan(augment_incidence_clauses(clauses, constructions), context_name)
        for guard in compile_guards(guards)
        if (clauses := _clauses(guard))
    )


@lru_cache(maxsize=1024)
def residual_sources(guards, context_name=LOGICAL_CONTEXT, constructions=()):
    return tuple(
        source
        for plan in logical_plans(guards, context_name, constructions)
        for source in plan.components
    )


@lru_cache(maxsize=4096)
def component_references(source):
    if LOGICAL_CONTEXT not in source and SMOOTH_LOGICAL_CONTEXT not in source:
        return ()
    references = []
    for node in ast.walk(ast.parse(source, mode="eval")):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Subscript)
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id.startswith((LOGICAL_CONTEXT, SMOOTH_LOGICAL_CONTEXT))
            and isinstance(node.value.slice, ast.Constant)
            and isinstance(node.value.slice.value, str)
            and isinstance(node.slice, ast.Constant)
            and type(node.slice.value) is int
        ):
            references.append((node.value.value.id, node.value.slice.value, node.slice.value))
    return tuple(references)


@lru_cache(maxsize=4096)
def evaluation_sources(source, plans=()):
    """Expose actual dependencies to bounds, construction slicing and verification."""
    identities = {identity for _, identity, _ in component_references(source)}
    if not identities:
        return (source,)
    return tuple(
        dict.fromkeys(leaf for plan in plans if plan.identity in identities for leaf in plan.leaves)
    )


def lower_logical_equalities(spec):
    if spec.logical_plans:
        return spec
    occupied = set(spec.variables.resolved_names()) | {item.name for item in spec.construction}
    context_name = LOGICAL_CONTEXT
    while (
        context_name in occupied
        or context_name.replace(LOGICAL_CONTEXT, SMOOTH_LOGICAL_CONTEXT, 1) in occupied
    ):
        context_name += "_internal"
    constructions = tuple((item.name, item.expr) for item in spec.construction)
    extra = residual_sources(tuple(spec.guards), context_name, constructions)
    if not extra:
        return spec
    return replace(
        spec,
        constraints=[*spec.constraints, *extra],
        v=[*(spec.v or [0] * len(spec.constraints)), *([0] * len(extra))],
        m=None,
        logical_plans=logical_plans(tuple(spec.guards), context_name, constructions),
    )
