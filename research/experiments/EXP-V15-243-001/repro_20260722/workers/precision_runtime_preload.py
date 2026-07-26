"""Narrow candidate-private preload for the frozen precision runtime."""

from __future__ import annotations

from pathlib import Path


def install(base, module_name: str):
    """Load only PRECISION_RUNTIME early and reuse it at endpoint selection."""

    original_load = base._load_module
    runtime_path = Path(base.PRECISION_RUNTIME).resolve()
    runtime = original_load(module_name, runtime_path)

    def load(name, path):
        if Path(path).resolve() == runtime_path:
            return runtime
        return original_load(name, path)

    base._load_module = load
    return runtime
