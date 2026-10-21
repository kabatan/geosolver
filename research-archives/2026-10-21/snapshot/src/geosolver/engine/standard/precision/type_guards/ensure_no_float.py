"""Runtime guard to reject float contamination in high-precision paths."""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping, Sequence
from types import BuiltinFunctionType, FunctionType, MappingProxyType, MethodType

from mpmath import mpf

from .high_precision_contamination_error import HighPrecisionContaminationError
from .high_precision_mode import is_high_precision_mode

try:
    import numpy as np

    _NUMPY_FLOATING_TYPES: tuple[type, ...] = (np.floating,)
except Exception:  # pragma: no cover
    _NUMPY_FLOATING_TYPES = ()

try:
    from sympy import Float as _SympyFloat

    _SYMPY_FLOAT_TYPES: tuple[type, ...] = (_SympyFloat,)
except Exception:  # pragma: no cover
    _SYMPY_FLOAT_TYPES = ()


_FLOAT_TYPES = (float,) + _NUMPY_FLOATING_TYPES + _SYMPY_FLOAT_TYPES
_TEXT_TYPES = (str, bytes, bytearray)
_MISSING_BINDING = object()
# Exact types only: subclasses may also implement Mapping/Sequence. This is a
# type fast path, never a cache of checked values or mutable container contents.
_ATOMIC_TYPE_IDS = frozenset(
    id(kind)
    for kind in (
        mpf,
        int,
        bool,
        str,
        bytes,
        bytearray,
        type(None),
        FunctionType,
        BuiltinFunctionType,
        MethodType,
    )
)


class ValidatedHPContext(MutableMapping):
    """Immutable checked bindings plus a delta checked at every HP boundary.

    Container values remain in the delta, even when supplied by the base, so
    mutations through external aliases cannot bypass contamination checks.
    Opaque objects follow the existing contract (attributes are not inspected).
    """

    def __init__(self, base):
        ensure_no_float(base, context="validated_context.base")
        fixed, changing = {}, {}
        for key, value in base.items():
            container = isinstance(value, Mapping | Sequence) and not isinstance(value, _TEXT_TYPES)
            (changing if container else fixed)[key] = value
        self._base = MappingProxyType(fixed)
        self._delta = changing
        self.scalar_evaluator = None

    def fork(self):
        result = object.__new__(ValidatedHPContext)
        result._base = self._base
        result._delta = self._delta.copy()
        result.scalar_evaluator = None
        return result

    def __getitem__(self, key):
        value = self._delta.get(key, _MISSING_BINDING)
        if value is not _MISSING_BINDING:
            return value
        return self._base[key]

    def __setitem__(self, key, value):
        self._delta[key] = value

    def __delitem__(self, key):
        self[key]
        self._delta.pop(key, None)
        if key in self._base:
            self._base = MappingProxyType({k: v for k, v in self._base.items() if k != key})

    def __iter__(self):
        yield from (k for k in self._base if k not in self._delta)
        yield from self._delta

    def __len__(self):
        return sum(1 for _ in self)


def _find_float(value: object) -> tuple[str, str] | None:
    value_type = type(value)
    if value_type is ValidatedHPContext:
        return _find_float(value._delta)
    if id(value_type) in _ATOMIC_TYPE_IDS:
        return None
    if value_type is dict:
        mapping = True
    elif value_type is list or value_type is tuple:
        mapping = False
    else:
        if isinstance(value, _FLOAT_TYPES):
            return value_type.__name__, ""
        mapping = isinstance(value, Mapping)
        if not mapping and (isinstance(value, _TEXT_TYPES) or not isinstance(value, Sequence)):
            return None
    entries = value.items() if mapping else enumerate(value)
    for key, item in entries:
        failure = _find_float(item)
        if failure is not None:
            kind, suffix = failure
            return kind, f".{key}{suffix}" if mapping else f"[{key}]{suffix}"
    return None


def ensure_no_float(value: object, *, context: str) -> None:
    """Reject float contamination, formatting its path only when it is found.

    Every mapping value and sequence element is revisited on every call, even
    when a previous call checked the same container. Opaque objects retain the
    existing contract: this check does not inspect arbitrary object attributes.
    """
    failure = _find_float(value)
    if failure is not None:
        kind, suffix = failure
        raise HighPrecisionContaminationError(
            f"float contamination detected at {context}{suffix}: {kind}"
        )


def ensure_high_precision_mode(*, context: str) -> None:
    if not is_high_precision_mode():
        raise HighPrecisionContaminationError(f"high_precision_mode is required at {context}")
