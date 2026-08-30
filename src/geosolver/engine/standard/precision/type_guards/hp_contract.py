"""Runtime contract decorator for high-precision critical functions."""

from __future__ import annotations

from collections.abc import Callable
from inspect import signature
from typing import Any

from .ensure_no_float import ensure_high_precision_mode, ensure_no_float


class _HPContractWrapped:
    def __init__(self, func: Callable[..., Any], input_names: tuple[str, ...]) -> None:
        self._func = func
        self._input_names = input_names
        self.__name__ = getattr(func, "__name__", self.__class__.__name__)
        self.__doc__ = getattr(func, "__doc__", None)
        self.__module__ = getattr(func, "__module__", None)
        self.__wrapped__ = func

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        ensure_high_precision_mode(context=f"hp_contract:{self.__name__}")
        bound = signature(self._func).bind_partial(*args, **kwargs)
        bound.apply_defaults()
        for name in self._input_names:
            if name in bound.arguments:
                ensure_no_float(
                    bound.arguments[name], context=f"hp_contract:{self.__name__}.input:{name}"
                )
        result = self._func(*args, **kwargs)
        ensure_no_float(result, context=f"hp_contract:{self.__name__}.output")
        return result


class _HPContractDecorator:
    def __init__(self, input_names: tuple[str, ...]) -> None:
        self._input_names = input_names

    def __call__(self, func: Callable[..., Any]) -> _HPContractWrapped:
        return _HPContractWrapped(func=func, input_names=self._input_names)


def hp_contract(*, input_names: tuple[str, ...] = ()) -> _HPContractDecorator:
    """Create a high-precision runtime contract decorator.

    Args:
        input_names: Named arguments that must pass ``ensure_no_float`` at entry.
    """
    return _HPContractDecorator(input_names=tuple(input_names))
