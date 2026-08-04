#!/usr/bin/env python3
"""Exact, source-level answer-set scoring for the geometry corpus.

The contest answer is often a presentation of a geometric quantity (for
example ``a+b`` after a problem gives a reduced fraction ``a/b``).  That
presentation is not part of the solver's mathematical target.  This module
therefore compares the *raw exact expression* reported by Phase C with a
separately audited source truth set.

Decimal values are never promoted to exact answers.  A decimal emitted next
to the same symbolic value is treated as a serialization duplicate only; a
decimal-only answer is not a proof of an exact solution.
"""
from __future__ import annotations

import re
from typing import Any


_DECIMAL_RE = re.compile(r"^[+-]?(?:\d+\.\d*|\.\d+|\d+[eE][+-]?\d+)$")
_EXACT_TEXT_RE = re.compile(r"^[0-9A-Za-z_+*/().,\-\s]+$")


def expected_parts(expected: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if expected in (None, ""):
        return []
    if isinstance(expected, (list, tuple)):
        return [str(x).strip() for x in expected if str(x).strip()]
    return [part.strip() for part in str(expected).split(";") if part.strip()]


def _normalise_text(value: str) -> str:
    text = str(value).strip()
    text = text.replace("π", "pi").replace("√", "sqrt")
    text = text.replace("^", "**")
    text = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", text)
    text = re.sub(r"sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", text)
    # The solver's exact printer and the source ledger may differ only in
    # harmless whitespace around multiplication and division.
    text = re.sub(r"\s+", "", text)
    return text


def _sympy_exact(value: str) -> Any | None:
    """Parse an exact expression, rejecting all floating-point literals.

    SymPy is part of the isolated solver runtime.  The optional import keeps
    metadata-only tools usable on a minimal host; in that case the caller
    falls back to conservative textual comparison.
    """
    text = _normalise_text(value)
    if not text or _DECIMAL_RE.fullmatch(text):
        return None
    try:
        import sympy as sp

        x = sp.Symbol("x")
        expr = sp.sympify(
            text,
            locals={
                "sqrt": sp.sqrt,
                "pi": sp.pi,
                "CRootOf": sp.CRootOf,
                "RootOf": sp.RootOf,
                "x": x,
            },
        )
        # A decimal hidden inside a larger expression is still approximate.
        if expr.atoms(sp.Float):
            return None
        return sp.simplify(expr)
    except Exception:
        return None


def exact_equivalent(left: str, right: str) -> bool:
    left_expr = _sympy_exact(left)
    right_expr = _sympy_exact(right)
    if left_expr is not None and right_expr is not None:
        try:
            import sympy as sp

            return bool(sp.simplify(left_expr - right_expr) == 0)
        except Exception:
            pass
    # Conservative fallback: this can prove textual identity, but never
    # interprets a decimal as an exact value.
    left_text = _normalise_text(left)
    right_text = _normalise_text(right)
    if _DECIMAL_RE.fullmatch(left_text) or _DECIMAL_RE.fullmatch(right_text):
        return False
    return left_text == right_text


def _numeric(value: str) -> Any | None:
    """Return a high-precision numeric proxy only for representation dedupe."""
    try:
        import sympy as sp

        expr = _sympy_exact(value)
        if expr is not None:
            return sp.N(expr, 100)
        text = _normalise_text(value)
        if _DECIMAL_RE.fullmatch(text):
            return sp.Float(text, 100)
    except Exception:
        return None
    return None


def _dedupe_solution_values(values: list[str] | tuple[str, ...]) -> tuple[list[str], bool]:
    """Keep exact values and discard only decimal serializations of them.

    The second return value is true when a non-duplicate decimal was seen.
    Such a value cannot establish strict exactness and causes the final set
    predicate to be false (rather than silently applying a tolerance).
    """
    exact_values: list[str] = []
    exact_numeric: list[Any] = []
    approximate_values: list[str] = []
    for raw in values:
        value = str(raw).strip()
        expr = _sympy_exact(value)
        if expr is not None:
            if not any(exact_equivalent(value, old) for old in exact_values):
                exact_values.append(value)
                number = _numeric(value)
                if number is not None:
                    exact_numeric.append(number)
            continue
        # On a minimal host without SymPy, retain conservative textual exact
        # forms (rationals, radicals, pi, and CRootOf expressions).  They can
        # only prove equality by normalized text, but are still not decimal
        # approximations.
        normalized = _normalise_text(value)
        if not _DECIMAL_RE.fullmatch(normalized) and _EXACT_TEXT_RE.fullmatch(normalized):
            if not any(exact_equivalent(value, old) for old in exact_values):
                exact_values.append(value)
            continue
        approximate_values.append(value)

    approximate_extra = False
    for value in approximate_values:
        number = _numeric(value)
        if number is None:
            approximate_extra = True
            continue
        # A decimal alongside its exact symbolic identification is only a
        # duplicate serialization.  This threshold is used solely for that
        # serialization dedupe; it is never used to match a value to truth.
        if not any(abs(number - old) < 10 ** -12 for old in exact_numeric):
            approximate_extra = True
    return exact_values, approximate_extra


def strict_answer_set_exact(
    solution_values: list[str] | tuple[str, ...] | None,
    expected: str | list[str] | tuple[str, ...] | None,
) -> bool | None:
    """Compare solver and audited truth as mathematical exact sets.

    ``None`` means that the truth ledger is unavailable.  ``False`` means the
    solver produced no exact set, an extra branch, or a value not equal to the
    audited set.  No numeric tolerance is used for truth matching.
    """
    parts = expected_parts(expected)
    if not parts:
        return None
    if not solution_values:
        return False
    expected_values, expected_approx = _dedupe_solution_values(parts)
    actual_values, actual_approx = _dedupe_solution_values(solution_values)
    if expected_approx or not expected_values:
        return None
    # A decimal-only solver answer is not an exact solution set.  Decimal
    # fallbacks paired with an exact value are harmless serialization dupes.
    if actual_approx or not actual_values:
        return False
    if len(actual_values) != len(expected_values):
        return False
    return all(
        any(exact_equivalent(actual, expected_value) for expected_value in expected_values)
        for actual in actual_values
    ) and all(
        any(exact_equivalent(expected_value, actual) for actual in actual_values)
        for expected_value in expected_values
    )


def exact_target_is_valid(expected: str | list[str] | tuple[str, ...] | None) -> bool:
    """Return whether a truth-ledger target is a nonempty exact set.

    A verified ledger row must never contain a decimal approximation.  This
    helper is used by the corpus validator so a malformed truth row cannot be
    silently converted into a false solver result.
    """
    parts = expected_parts(expected)
    if not parts:
        return False
    exact_values, approximate = _dedupe_solution_values(parts)
    return not approximate and len(exact_values) == len(parts) and bool(exact_values)


def strict_answer_set_complete(
    solution_values: list[str] | tuple[str, ...] | None,
    expected: str | list[str] | tuple[str, ...] | None,
) -> bool | None:
    """Strict coverage (extras are allowed) for diagnostic reporting."""
    parts = expected_parts(expected)
    if not parts:
        return None
    if not solution_values:
        return False
    expected_values, expected_approx = _dedupe_solution_values(parts)
    actual_values, actual_approx = _dedupe_solution_values(solution_values)
    if expected_approx or not expected_values:
        return None
    if actual_approx:
        return False
    return all(any(exact_equivalent(target, actual) for actual in actual_values) for target in expected_values)
