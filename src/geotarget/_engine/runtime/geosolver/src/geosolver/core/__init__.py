"""GeoSolver Core Module"""

from geosolver.core.errors import (
    GeometryError,
    DegenerateGeometryError,
    CollinearPointsError,
    CoincidentPointsError,
    ParallelLinesError,
    NoIntersectionError,
    ZeroAreaError,
    InvalidCircleError,
    ExcludedPointError,
    SolverError,
    NoSolutionError,
    ConvergenceError,
    SolverTimeoutError,
    PrecisionError,
)

from geosolver.core.result import SolveResult, SolveStatus

from geosolver.core.safety import (
    AssumptionError,
    assume_mode,
    assume_enabled,
    set_assume_tolerance,
    Assume,
    AssumeEq,
    AssumeNe,
    AssumeLt,
    AssumeLe,
    AssumeGt,
    AssumeGe,
    AssumeAcute,
)

__all__ = [
    # Result types
    "SolveResult",
    "SolveStatus",
    # Geometry errors
    "GeometryError",
    "DegenerateGeometryError",
    "CollinearPointsError",
    "CoincidentPointsError",
    "ParallelLinesError",
    "NoIntersectionError",
    "ZeroAreaError",
    "InvalidCircleError",
    "ExcludedPointError",
    # Solver errors
    "SolverError",
    "NoSolutionError",
    "ConvergenceError",
    "SolverTimeoutError",
    "PrecisionError",
    # Safety / Assume
    "AssumptionError",
    "assume_mode",
    "assume_enabled",
    "set_assume_tolerance",
    "Assume",
    "AssumeEq",
    "AssumeNe",
    "AssumeLt",
    "AssumeLe",
    "AssumeGt",
    "AssumeGe",
    "AssumeAcute",
]

