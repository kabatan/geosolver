"""Truth-blind compatibility repairs for Float64/HP geometry parity.

This research shim changes no problem document, variable, constraint, bound,
branch, or target.  It only makes the high-precision backend accept public DSL
spellings that the ordinary geometry backend already accepts, and removes
Python-float contamination from two HP-only conversion paths.

The three repairs are deliberately primitive-wide:

* ``IncircleContactPoint(..., side=...)`` accepts exactly the public
  ``"AB"`` / ``"BC"`` / ``"CA"`` spellings and their documented
  integer/vertex aliases in the MP backend.  Unsupported spellings retain the
  ordinary backend's three-contact-list behavior rather than being promoted
  to a selected side.
* ``CircleThroughThreePoints`` converts the existing Python binary-float
  ``1e-20`` cutoff to its exact integer ratio before constructing an ``mpf``.
  This removes float contamination without changing the previous construction
  boundary.
* mpmath symbolic constants such as ``mp.pi`` are rounded to the active
  precision before entering the strict ``mpf`` boundary.

No case identity or offline target is accepted by this module.
"""

from __future__ import annotations

import importlib
import sys
from typing import Any

from mpmath import mp


_INSTALLED = False
_ORIGINAL_STRICT_TO_MPF: Any = None
_ORIGINAL_INCIRCLE_CONTACT: Any = None
_ORIGINAL_CIRCLE_THROUGH_THREE: Any = None
_CIRCLE_CUTOFF_NUMERATOR, _CIRCLE_CUTOFF_DENOMINATOR = (
    1e-20
).as_integer_ratio()


def _is_mpmath_constant(value: object) -> bool:
    cls = value.__class__
    return (
        cls.__name__ == "constant"
        and str(cls.__module__).startswith("mpmath.")
    )


def strict_to_mpf_compatible(value: object, *, context: str):
    """Preserve strict conversion while admitting mpmath's own constants."""

    if _is_mpmath_constant(value):
        # Unary plus evaluates the constant at the *current* mp.dps.  This is
        # important because caching ``mpf(mp.pi)`` at the first precision lane
        # would silently cap later 768/1024-bit evaluations.
        return +value
    if _ORIGINAL_STRICT_TO_MPF is None:
        raise RuntimeError("semantic parity shim has not been installed")
    return _ORIGINAL_STRICT_TO_MPF(value, context=context)


def _same_point(left: object, right: object) -> bool:
    if left is right:
        return True
    try:
        comparison = left == right
    except Exception:
        return False
    return comparison if isinstance(comparison, bool) else False


def _normalize_contact_side(
    A: object, B: object, C: object, side: object
) -> object:
    if side is None:
        return None
    if isinstance(side, str):
        mapping = {
            "BC": (B, C),
            "CA": (C, A),
            "AB": (A, B),
        }
        # The ordinary primitive is case-sensitive and returns all three
        # contacts for an unsupported spelling.  Do not silently broaden that
        # source behavior in the HP backend.
        return mapping.get(side)
    if isinstance(side, int):
        mapping = {0: (B, C), 1: (C, A), 2: (A, B)}
        return mapping.get(side)
    if isinstance(side, (tuple, list)):
        # A point pair is the MP implementation detail, not a documented
        # source-side selector.  The ordinary primitive returns the complete
        # contact list for it, so preserve that result.
        return None
    # Public legacy semantics also permit the opposite vertex: A denotes BC,
    # B denotes CA, and C denotes AB.
    if _same_point(side, A):
        return (B, C)
    if _same_point(side, B):
        return (C, A)
    if _same_point(side, C):
        return (A, B)
    return None


def incircle_contact_point_compatible(
    A: object, B: object, C: object, side: object = None
):
    if _ORIGINAL_INCIRCLE_CONTACT is None:
        raise RuntimeError("semantic parity shim has not been installed")
    return _ORIGINAL_INCIRCLE_CONTACT(
        A,
        B,
        C,
        _normalize_contact_side(A, B, C, side),
    )


def circle_through_three_points_compatible(
    p1: object, p2: object, p3: object
):
    """Exact copy of the MP backend with its old binary cutoff MP-typed."""

    from geosolver.geometry.mp.mp_core_types import MPCircle, MPPoint

    x1, y1 = p1.x, p1.y
    x2, y2 = p2.x, p2.y
    x3, y3 = p3.x, p3.y
    determinant = 2 * (
        x1 * (y2 - y3)
        + x2 * (y3 - y1)
        + x3 * (y1 - y2)
    )
    # Preserve the prior comparison against the Python binary-float literal
    # exactly.  ``mp.mpf("1e-20")`` is a different, slightly larger number and
    # would make a positive-width set of formerly defined circles undefined.
    cutoff = (
        mp.mpf(_CIRCLE_CUTOFF_NUMERATOR)
        / mp.mpf(_CIRCLE_CUTOFF_DENOMINATOR)
    )
    if abs(determinant) < cutoff:
        return None
    ux = (
        (x1**2 + y1**2) * (y2 - y3)
        + (x2**2 + y2**2) * (y3 - y1)
        + (x3**2 + y3**2) * (y1 - y2)
    ) / determinant
    uy = (
        (x1**2 + y1**2) * (x3 - x2)
        + (x2**2 + y2**2) * (x1 - x3)
        + (x3**2 + y3**2) * (x2 - x1)
    ) / determinant
    center = MPPoint(ux, uy)
    radius = mp.sqrt((x1 - ux) ** 2 + (y1 - uy) ** 2)
    return MPCircle(center, radius)


def install() -> dict[str, object]:
    """Install the primitive-wide HP compatibility layer once per process."""

    global _INSTALLED
    global _ORIGINAL_STRICT_TO_MPF
    global _ORIGINAL_INCIRCLE_CONTACT
    global _ORIGINAL_CIRCLE_THROUGH_THREE

    if _INSTALLED:
        return {
            "installed": True,
            "already_installed": True,
            "case_identity_read": False,
            "truth_read": False,
        }

    strict_module = importlib.import_module(
        "geosolver._internal.solver.precision.type_guards.strict_to_mpf"
    )
    mp_api = importlib.import_module("geosolver.geometry.mp.mp_api")
    mp_common_wrappers = importlib.import_module(
        "geosolver.geometry.mp.mp_api_common_wrappers"
    )
    construction_module = importlib.import_module(
        "geosolver.geometry.operations.constructions_extra"
    )
    triangle_module = importlib.import_module(
        "geosolver.geometry.operations.triangle"
    )
    hp_context_module = importlib.import_module(
        "geosolver._internal.autosolve.context.high_precision"
    )

    _ORIGINAL_STRICT_TO_MPF = strict_module.strict_to_mpf
    # Bind to the stable low-level wrapper, not the public MP_API slot.  The
    # public slot may already contain this same compatibility shim loaded
    # under another research-module name; capturing it would stack two
    # normalizers and turn a canonical point-pair back into ``None``.
    _ORIGINAL_INCIRCLE_CONTACT = (
        mp_common_wrappers.MP_IncircleContactPoint
    )
    _ORIGINAL_CIRCLE_THROUGH_THREE = (
        construction_module.CircleThroughThreePoints._mpmath
    )

    strict_module.strict_to_mpf = strict_to_mpf_compatible
    # Modules that imported the function before installation retain a direct
    # reference.  Replace only exact references to the original converter.
    for module in tuple(sys.modules.values()):
        if module is None:
            continue
        try:
            current = getattr(module, "strict_to_mpf", None)
        except Exception:
            continue
        if current is _ORIGINAL_STRICT_TO_MPF:
            setattr(module, "strict_to_mpf", strict_to_mpf_compatible)

    mp_api.MP_IncircleContactPoint = incircle_contact_point_compatible
    if isinstance(getattr(mp_api, "MP_API", None), dict):
        mp_api.MP_API["IncircleContactPoint"] = (
            incircle_contact_point_compatible
        )
    triangle_module.IncircleContactPoint._mpmath = (
        incircle_contact_point_compatible
    )
    construction_module.CircleThroughThreePoints._mpmath = (
        circle_through_three_points_compatible
    )

    # Cached contexts close over old callbacks, so invalidate only the context
    # dictionary cache.  Every later lane still obtains its own active mp.dps.
    hp_context_module._build_hp_context_dict.cache_clear()

    _INSTALLED = True
    return {
        "installed": True,
        "already_installed": False,
        "repairs": [
            "IncircleContactPoint public side spelling parity",
            (
                "CircleThroughThreePoints behavior-preserving binary-float "
                "cutoff conversion"
            ),
            "mpmath constant strict-conversion parity",
        ],
        "case_identity_read": False,
        "truth_read": False,
        "source_modified": False,
    }


__all__ = [
    "circle_through_three_points_compatible",
    "incircle_contact_point_compatible",
    "install",
    "strict_to_mpf_compatible",
]
