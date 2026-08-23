"""Backward-compatibility public layer.

Migration guide:
- New internal implementations live under ``geosolver._internal``.
- Backward-compatible imports remain available via this module.
- Prefer importing orchestration APIs from ``geosolver.public`` or ``geosolver._internal``.
"""

import os
from warnings import warn

from geosolver._internal.autosolve.public import run_ir
from geosolver._internal.solver.public import solve

_DEPRECATION_MESSAGE = (
    "geosolver直接インポートは非推奨です。"
    "geosolver.public または geosolver._internal を使用してください。"
)


def emit_deprecated_root_import_warning() -> None:
    """Emit an opt-in root-import deprecation warning.

    Root imports are kept quiet by default because they are the simplest public
    entrypoint for notebooks and examples.  Set ``GEOSOLVER_WARN_ROOT_IMPORT=1``
    to audit legacy imports.
    """
    if os.environ.get("GEOSOLVER_WARN_ROOT_IMPORT") == "1":
        warn(_DEPRECATION_MESSAGE, DeprecationWarning, stacklevel=3)


__all__ = ["emit_deprecated_root_import_warning", "run_ir", "solve"]
