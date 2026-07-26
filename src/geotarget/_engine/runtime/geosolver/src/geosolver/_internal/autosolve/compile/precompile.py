"""Pre-compilation helpers for autosolve IR execution."""

from __future__ import annotations

from typing import Any


def precompile_construction(construction_items: list[Any]) -> list[tuple[str, Any]]:
    """Compile construction expressions with fallback to raw strings."""
    compiled_items: list[tuple[str, Any]] = []
    for item in construction_items:
        try:
            compiled = compile(item.expr, "<string>", "eval")
            compiled_items.append((item.name, compiled))
        except Exception:
            compiled_items.append((item.name, item.expr))
    return compiled_items


def precompile_constraints(constraints: list[str]) -> list[Any]:
    """Compile constraints with fallback to raw strings."""
    compiled_constraints: list[Any] = []
    for expr_str in constraints:
        try:
            compiled_constraints.append(compile(expr_str, "<string>", "eval"))
        except Exception:
            compiled_constraints.append(expr_str)
    return compiled_constraints


def precompile_targets(v_values: list[Any] | None, constraint_count: int) -> list[Any]:
    """Compile target expressions used by constraints."""
    compiled_targets: list[Any] = []
    values = v_values if v_values else [0.0] * constraint_count
    for target in values:
        if isinstance(target, str):
            try:
                compiled_targets.append(compile(target, "<string>", "eval"))
            except Exception:
                compiled_targets.append(target)
        else:
            compiled_targets.append(target)
    return compiled_targets
