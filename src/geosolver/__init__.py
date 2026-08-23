"""
GeoSolver - 幾何問題専用高精度ソルバー

シンプルなAPI:
    from geosolver import solve
    
    result = solve(n=3, f=f, v=v)                    # 基本使用
    result = solve(n=3, f=f, v=v, precision=50)      # 50桁精度

詳細は docs/API.md を参照してください。
"""

from geosolver.public import (
    emit_deprecated_root_import_warning,
    solve,
)

from geosolver.core.result import SolveResult, SolveStatus
from geosolver.core.errors import (
    GeometryError,
    DegenerateGeometryError,
    CollinearPointsError,
    CoincidentPointsError,
    SolverError,
    NoSolutionError,
    ConvergenceError,
    SolverTimeoutError,
)

__version__ = "0.2.0"
from geosolver.sketch import GeometricSketch
from geosolver.geometry import *  # noqa: F403 - re-export ergonomic geometry DSL
from geosolver.geometry._public_api_symbols import GEOMETRY_PUBLIC_API

emit_deprecated_root_import_warning()

__all__ = [
    # Main API
    "solve",
    "GeometricSketch",
    # Result types
    "SolveResult",
    "SolveStatus",
    # Errors
    "GeometryError",
    "DegenerateGeometryError",
    "CollinearPointsError",
    "CoincidentPointsError",
    "SolverError",
    "NoSolutionError",
    "ConvergenceError",
    "SolverTimeoutError",
    *GEOMETRY_PUBLIC_API,
]
