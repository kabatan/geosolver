"""High-precision geometry execution context."""

import functools
from typing import Any

from mpmath import mp

import geosolver.geometry.mp.mp_api as mp_api
from geosolver.engine.standard.interpreter.context.aliases import apply_geometry_aliases
from geosolver.engine.standard.interpreter.context.geometry import _get_geometry_context
from geosolver.engine.standard.precision.type_guards.ensure_mpf import ensure_mpf
from geosolver.engine.standard.precision.type_guards.strict_to_mpf import strict_to_mpf
from geosolver.geometry.mp.signed_tangency import signed_tangency
from geosolver.geometry.registry import MultiFunctionWrapper
from geosolver.problem.dsl_spec import dsl_spec, public_symbol_names

try:
    import numpy as np

    _NUMPY_FLOATING_TYPES: tuple[type, ...] = (np.floating,)
except Exception:  # pragma: no cover
    _NUMPY_FLOATING_TYPES = ()


_SYMBOL_PARITY_EXCLUDE = {"__builtins__"}


class _HPFloatReturnTracer:
    def __init__(self) -> None:
        self._symbols: set[str] = set()

    def record(self, *, symbol: str, value: object) -> None:
        if isinstance(value, float) or (
            _NUMPY_FLOATING_TYPES and isinstance(value, _NUMPY_FLOATING_TYPES)
        ):
            self._symbols.add(symbol)

    def snapshot(self) -> list[str]:
        return sorted(self._symbols)


class _HPCallableWithTrace:
    def __init__(self, *, symbol: str, callback: Any, tracer: _HPFloatReturnTracer) -> None:
        self._symbol = symbol
        self._callback = callback
        self._tracer = tracer

    def __call__(self, *args: object, **kwargs: object) -> Any:
        result = self._callback(*args, **kwargs)
        self._tracer.record(symbol=self._symbol, value=result)
        return result


def _is_mpmath_constant_callable(value: Any) -> bool:
    cls = getattr(value, "__class__", None)
    if cls is None:
        return False
    module_name = str(getattr(cls, "__module__", ""))
    class_name = str(getattr(cls, "__name__", ""))
    return callable(value) and class_name == "constant" and module_name.startswith("mpmath.")


def _attach_float_return_tracer(context: dict[str, Any]) -> dict[str, Any]:
    tracer = _HPFloatReturnTracer()
    wrapped: dict[str, Any] = {}
    for name, value in context.items():
        if name.startswith("__"):
            wrapped[name] = value
            continue
        if callable(value) and (not _is_mpmath_constant_callable(value)):
            wrapped[name] = _HPCallableWithTrace(symbol=name, callback=value, tracer=tracer)
            continue
        wrapped[name] = value
    wrapped["_hp_float_return_tracer"] = tracer
    wrapped["_hp_get_float_return_symbols"] = tracer.snapshot
    return wrapped


def _forbidden_float(*_args: object, **_kwargs: object) -> None:
    raise TypeError("float() is forbidden in high-precision context")


def _raw_float_bridge(value: object) -> object:
    return strict_to_mpf(value, context="high_precision_context._RawFloat")


def _validate_line_backend_consistency(context: dict[str, Any]) -> None:
    point_ctor = context.get("Point")
    line_ctor = context.get("Line")
    parallel_fn = context.get("Parallel")
    perpendicular_fn = context.get("Perpendicular")

    required = (point_ctor, line_ctor, parallel_fn, perpendicular_fn)
    if not all(callable(entry) for entry in required):
        raise RuntimeError(
            "HP context backend mismatch: "
            "Point/Line/Parallel/Perpendicular callable set is incomplete"
        )

    try:
        p1 = point_ctor(0, 0)
        p2 = point_ctor(1, 0)
        p3 = point_ctor(0, 1)
        l1 = line_ctor(p1, p2)
        l2 = line_ctor(p1, p3)
        parallel_fn(l1, l2)
        perpendicular_fn(l1, l2)
    except Exception as exc:
        raise RuntimeError(
            f"HP context backend mismatch for Line/Parallel/Perpendicular: {exc}"
        ) from exc


def _validate_symbol_parity(std_context: dict[str, Any], hp_context: dict[str, Any]) -> None:
    missing_symbols: list[str] = []
    non_callable_symbols: list[str] = []
    for symbol_name, symbol_value in std_context.items():
        if symbol_name in _SYMBOL_PARITY_EXCLUDE:
            continue
        if not callable(symbol_value):
            continue
        hp_value = hp_context.get(symbol_name)
        if hp_value is None:
            missing_symbols.append(symbol_name)
            continue
        if not callable(hp_value):
            non_callable_symbols.append(symbol_name)

    if missing_symbols:
        missing_symbols.sort()
        raise RuntimeError(
            "HP context symbol parity violation: missing symbols " + ", ".join(missing_symbols)
        )
    if non_callable_symbols:
        non_callable_symbols.sort()
        raise RuntimeError(
            "HP context symbol parity violation: non-callable symbols "
            + ", ".join(non_callable_symbols)
        )


@functools.lru_cache(maxsize=1)
def _build_hp_context_dict() -> dict[str, Any]:
    std_context = _get_geometry_context()
    context: dict[str, Any] = {}
    for name, value in std_context.items():
        if isinstance(value, MultiFunctionWrapper):
            context[name] = value.mp
        else:
            context[name] = value
    context.update(
        {
            "sqrt": mp.sqrt,
            "sin": mp.sin,
            "cos": mp.cos,
            "tan": mp.tan,
            "asin": mp.asin,
            "acos": mp.acos,
            "atan": mp.atan,
            "atan2": mp.atan2,
            "pi": mp.pi,
            "abs": abs,
            "min": min,
            "max": max,
            "int": int,
            "float": _forbidden_float,
            "_RawFloat": _raw_float_bridge,
            "mpf": ensure_mpf,
            "ensure_mpf": ensure_mpf,
            "_SignedTangency": signed_tangency,
        }
    )
    for name in dir(mp_api):
        if not name.startswith("MP_"):
            continue
        value = getattr(mp_api, name)
        if not callable(value):
            continue
        alias = name[3:]
        if alias in public_symbol_names():
            context[alias] = value

    # Rebind aliases *after* selecting the backend.  Copying the symbolic context
    # otherwise leaves aliases such as midpoint bound to a symbolic fallback.
    for symbol in dsl_spec().symbols:
        if symbol.name in context:
            for alias in symbol.aliases:
                context[alias] = context[symbol.name]
    # These compatibility closures capture backend-specific constructors.
    context.pop("Triangle", None)
    context = apply_geometry_aliases(context)
    context = _attach_float_return_tracer(context)
    if "Midpoint" in context:
        context["MidPoint"] = context["Midpoint"]
    _validate_symbol_parity(std_context, context)
    _validate_line_backend_consistency(context)
    return context


def _get_high_precision_context(precision: int = 80) -> dict[str, Any]:
    """Build high-precision context with mpmath-first functions."""
    _ = precision
    return _build_hp_context_dict().copy()
