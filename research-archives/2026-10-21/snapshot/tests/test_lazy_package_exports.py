from __future__ import annotations

import os
import subprocess
import sys


def _fresh(code: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_symbolic_worker_import_avoids_unrelated_public_services() -> None:
    _fresh("""
import sys
import geosolver.runtime.symbolic_worker
for name in ('pydantic', 'sympy', 'numpy', 'geosolver.application.service',
             'geosolver.problem.models', 'geosolver.runtime.protocol'):
    assert name not in sys.modules, name
""")


def test_lazy_public_exports_keep_defining_object_identity_and_introspection() -> None:
    _fresh("""
import importlib
packages = {
    'geosolver': {
        'GeometryProblem': 'geosolver.problem.models',
        'SolveOptions': 'geosolver.problem.models',
        'solve': 'geosolver.application.service',
        'validate': 'geosolver.problem.validation',
    },
    'geosolver.application': {'solve': 'geosolver.application.service'},
    'geosolver.problem': {
        'GeometryProblem': 'geosolver.problem.models',
        'to_engine_document': 'geosolver.problem.adapter',
        'validate': 'geosolver.problem.validation',
    },
    'geosolver.runtime': {
        'WorkerArtifact': 'geosolver.runtime.protocol',
        'WorkerRequest': 'geosolver.runtime.protocol',
    },
}
for package_name, exports in packages.items():
    package = importlib.import_module(package_name)
    assert package.__all__ == list(exports)
    assert set(exports) <= set(dir(package))
    for name, defining_module in exports.items():
        value = getattr(package, name)
        assert value is getattr(importlib.import_module(defining_module), name)
        assert vars(package)[name] is value
    namespace = {}
    exec('from ' + package_name + ' import *', namespace)
    assert all(namespace[name] is getattr(package, name) for name in exports)
    try:
        getattr(package, 'unrecognized_public_export')
    except AttributeError as error:
        assert package_name in str(error)
        assert 'unrecognized_public_export' in str(error)
    else:
        raise AssertionError(package_name)
assert importlib.import_module('geosolver').__version__ == '1.0.0'
""")
