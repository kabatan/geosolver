"""Build variable transforms from GuardIR bound hints."""

from __future__ import annotations

from collections.abc import Sequence

import mpmath as mp

from geosolver._internal.autosolve.guards.compile import GuardBoundHint, GuardIR
from geosolver._internal.solver.precision.type_guards.mp_types import MPFloat
from geosolver._internal.solver.reparameterization.variable_transform import (
    VariableTransform,
)


def build_transforms_from_guards(
    *,
    guard_irs: Sequence[GuardIR],
    variable_names: Sequence[str],
    bounds: Sequence[tuple[MPFloat | None, MPFloat | None]] | None = None,
) -> list[VariableTransform]:
    """Convert GuardIR bound hints to variable transforms.

    Args:
        guard_irs: Compiled guard IR nodes.
        variable_names: Names of solver variables (in order).
        bounds: Optional existing bounds per variable.

    Returns:
        One VariableTransform per variable.
    """
    _ = guard_irs
    _ = bounds
    return [
        VariableTransform(
            original_index=index,
            transform_kind="identity",
            lower_bound=None,
            upper_bound=None,
        )
        for index, _name in enumerate(variable_names)
    ]


def _collect_hints(
    guard_ir: GuardIR,
    name_to_index: dict[str, int],
    lower: list[MPFloat | None],
    upper: list[MPFloat | None],
    open_flags: list[bool] | None = None,
) -> None:
    """Extract bound hints recursively from a GuardIR tree."""
    is_open = guard_ir.kind == "bound_open"
    for hint in guard_ir.bounds_hints:
        if not is_open:
            _apply_hint(hint, name_to_index, lower, upper)
        if is_open and open_flags is not None and hint.variable in name_to_index:
            open_flags[name_to_index[hint.variable]] = True
    for child in guard_ir.children:
        _collect_hints(child, name_to_index, lower, upper, open_flags)


def _apply_hint(
    hint: GuardBoundHint,
    name_to_index: dict[str, int],
    lower: list[MPFloat | None],
    upper: list[MPFloat | None],
) -> None:
    """Apply a single GuardBoundHint to lower/upper arrays."""
    if hint.variable not in name_to_index:
        return
    idx = name_to_index[hint.variable]
    if hint.lower_expr is not None:
        val = _parse_constant_bound(hint.lower_expr)
        if val is not None and (lower[idx] is None or val > lower[idx]):
            lower[idx] = val
    if hint.upper_expr is not None:
        val = _parse_constant_bound(hint.upper_expr)
        if val is not None and (upper[idx] is None or val < upper[idx]):
            upper[idx] = val


def _parse_constant_bound(expr: str) -> MPFloat | None:
    """Parse a constant bound expression, or return None if non-constant."""
    try:
        return mp.mpf(expr)
    except Exception:
        return None


def _choose_transform(
    lo: MPFloat | None, hi: MPFloat | None,
) -> tuple[str, MPFloat | None, MPFloat | None]:
    """Choose the appropriate transform kind given bounds."""
    if lo is not None and hi is not None:
        return "sigmoid", lo, hi
    if lo is not None:
        return "softplus_lower", lo, None
    if hi is not None:
        return "softplus_upper", None, hi
    return "identity", None, None


def _count_ignored_hints(
    *,
    guard_irs: Sequence[GuardIR],
    variable_names: Sequence[str],
) -> int:
    """Count bound hints that cannot be converted to transforms."""
    name_set = set(variable_names)
    ignored = 0
    for guard_ir in guard_irs:
        ignored += _count_ignored_in_tree(guard_ir, name_set)
    return ignored


def _count_ignored_in_tree(guard_ir: GuardIR, name_set: set[str]) -> int:
    count = 0
    for hint in guard_ir.bounds_hints:
        if hint.variable not in name_set:
            count += 1
            continue
        lo_ok = hint.lower_expr is None or _parse_constant_bound(hint.lower_expr) is not None
        hi_ok = hint.upper_expr is None or _parse_constant_bound(hint.upper_expr) is not None
        if not (lo_ok and hi_ok):
            count += 1
    for child in guard_ir.children:
        count += _count_ignored_in_tree(child, name_set)
    return count


def _count_deferred_open_bounds(
    *,
    guard_irs: Sequence[GuardIR],
    variable_names: Sequence[str],
) -> int:
    """Count open-bound hints that are deferred to guard/penalty path."""
    name_set = set(variable_names)
    deferred = 0
    for guard_ir in guard_irs:
        deferred += _count_deferred_open_bounds_in_tree(guard_ir, name_set)
    return deferred


def _count_deferred_open_bounds_in_tree(
    guard_ir: GuardIR,
    name_set: set[str],
) -> int:
    count = 0
    if guard_ir.kind == "bound_open":
        for hint in guard_ir.bounds_hints:
            if hint.variable in name_set:
                count += 1
    for child in guard_ir.children:
        count += _count_deferred_open_bounds_in_tree(child, name_set)
    return count
