"""Public exports loaded only when requested by their caller."""

from importlib import import_module

__all__ = ["WorkerArtifact", "WorkerRequest"]

_EXPORT_MODULES = {
    "WorkerArtifact": "geosolver.runtime.protocol",
    "WorkerRequest": "geosolver.runtime.protocol",
}


def __getattr__(name):
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
