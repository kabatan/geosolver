"""
Solver Package Init

機能:
- solve(): 幾何問題を解く統一API（2パス探索、高精度化、厳密値識別を含む完全版）
"""

from geosolver.core.result import SolveResult, SolveStatus
from geosolver._internal.solver.base import (
    AbstractSolver,
    SolverConfig,
)
from geosolver._internal.solver.public import solve
from geosolver._internal.solver.public.legacy_utils import get_hp_values, get_solution_str
from geosolver.solver.numeric import NumericSolver
from geosolver.solver.solver import GeometricSolver

# 簡易版（Python native implementation）は別名で保持
from geosolver.solver.solve_simple import solve as solve_simple

__all__ = [
    "SolveResult",
    "SolveStatus",
    "SolverConfig",
    "AbstractSolver",
    "NumericSolver",
    "GeometricSolver",
    # Main APIs (Complete Version)
    "solve",
    # Alternative APIs
    "solve_simple",
    # Utilities
    "get_solution_str",
    "get_hp_values",
]
