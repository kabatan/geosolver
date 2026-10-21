"""Solve-local call-site identity and optional evaluation evidence."""

from contextlib import contextmanager
from contextvars import ContextVar

from geosolver.runtime.deadline import check_deadline

_call_site = ContextVar("dsl_call_site", default="")
_calls = ContextVar("dsl_calls", default=None)
_scope = ContextVar("dsl_evaluation_scope", default="")
_PUBLIC_PARAMETER_NAMES = {
    "Line": ("A", "B"),
    "Triangle": ("points",),
    "Polygon": ("arg1",),
    "PointOnSegment": ("A", "B", "t"),
    "PointOnCircle": ("omega", "t"),
    "PointOnLine": ("line", "t"),
}


def replay_calls(records):
    destination = _calls.get()
    if destination is not None:
        destination.extend(records)


@contextmanager
def evaluation_scope(name):
    token = _scope.set(name)
    try:
        yield
    finally:
        _scope.reset(token)


def current_call_site():
    return _call_site.get()


def current_evaluation_scope():
    return _scope.get()


@contextmanager
def capture_calls():
    records = []
    token = _calls.set(records)
    try:
        yield records
    finally:
        _calls.reset(token)


def runtime_call(site, name, function, *args, **kwargs):
    check_deadline()
    site = f"{_scope.get()}:{site}"
    # Bind the public names independently of backend implementation signatures.
    parameter_names = _PUBLIC_PARAMETER_NAMES.get(name)
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
        check_deadline()
        records = _calls.get()
        if records is not None:
            records.append((site, name, args, dict(kwargs), result))
        return result
    finally:
        _call_site.reset(token)
