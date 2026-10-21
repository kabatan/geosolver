"""Runtime contract decorator for high-precision critical functions."""

from __future__ import annotations

from functools import wraps
from inspect import Parameter, signature

from .ensure_no_float import ensure_high_precision_mode, ensure_no_float


def hp_contract(*, input_names: tuple[str, ...] = ()):
    """Check actual input values and results; compile only argument locations."""

    def decorate(function):
        call_signature = signature(function)
        parameters = tuple(call_signature.parameters.items())
        variadic = any(
            p.kind in (Parameter.VAR_POSITIONAL, Parameter.VAR_KEYWORD) for _, p in parameters
        )
        inputs = tuple(
            (name, index, parameter.default)
            for index, (name, parameter) in enumerate(parameters)
            if name in input_names
        )
        label = f"hp_contract:{function.__name__}"

        @wraps(function)
        def checked(*args, **kwargs):
            ensure_high_precision_mode(context=label)
            if variadic:
                bound = call_signature.bind_partial(*args, **kwargs)
                bound.apply_defaults()
            for name, index, default in inputs:
                value = (
                    bound.arguments.get(name, Parameter.empty)
                    if variadic
                    else kwargs.get(name, args[index] if index < len(args) else default)
                )
                if value is not Parameter.empty:
                    ensure_no_float(value, context=f"{label}.input:{name}")
            result = function(*args, **kwargs)
            ensure_no_float(result, context=f"{label}.output")
            return result

        return checked

    return decorate
