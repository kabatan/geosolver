"""Solve-local call-site identity and optional evaluation evidence."""

from contextlib import contextmanager
from contextvars import ContextVar

_call_site = ContextVar("dsl_call_site", default="")
_calls = ContextVar("dsl_calls", default=None)
_scope = ContextVar("dsl_evaluation_scope", default="")


@contextmanager
def evaluation_scope(name):
    token = _scope.set(name)
    try:
        yield
    finally:
        _scope.reset(token)


def current_call_site():
    return _call_site.get()


@contextmanager
def capture_calls():
    records = []
    token = _calls.set(records)
    try:
        yield records
    finally:
        _calls.reset(token)


def runtime_call(site, name, function, *args, **kwargs):
    site = f"{_scope.get()}:{site}"
    # Bind the public names independently of backend implementation signatures.
    parameter_names = {
        "PointOnSegment": ("A", "B", "t"),
        "PointOnCircle": ("omega", "t"),
        "PointOnLine": ("line", "t"),
    }.get(name)
    if parameter_names is not None and kwargs:
        values = list(args)
        for index, parameter in enumerate(parameter_names):
            if parameter in kwargs:
                if index < len(args):
                    raise TypeError(f"duplicate argument {parameter}")
                if index != len(values):
                    raise TypeError(f"missing argument {parameter_names[len(values)]}")
                values.append(kwargs.pop(parameter))
        args = tuple(values)
    if name in {"InscribedPolygon", "InscribedPolygonVertices"} and kwargs:
        values = list(args)
        if "circle" in kwargs and "omega" in kwargs:
            raise TypeError("circle and omega denote the same argument")
        if "circle" in kwargs:
            kwargs["omega"] = kwargs.pop("circle")
        for index, parameter in enumerate(("omega", "t2", "t3")):
            if parameter in kwargs:
                if index < len(values):
                    raise TypeError(f"duplicate argument {parameter}")
                if index != len(values):
                    raise TypeError("nonconsecutive polygon parameters")
                values.append(kwargs.pop(parameter))
        args = tuple(values)
    token = _call_site.set(site)
    try:
        result = function(*args, **kwargs)
        records = _calls.get()
        if records is not None:
            records.append((site, name, args, dict(kwargs), result))
        return result
    finally:
        _call_site.reset(token)
