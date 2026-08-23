"""Standardized failure reasons for solver phases."""

from enum import Enum


class SolverFailureReason(str, Enum):
    """Typed failure reasons used by phase-level diagnostics."""

    NO_INITIAL_POINTS = "no_initial_points"
    OPTIMIZATION_DIVERGED = "optimization_diverged"
    PRECISION_INSUFFICIENT = "precision_insufficient"
    EXACT_IDENTIFICATION_FAILED = "exact_identification_failed"
    FLOAT_CONTAMINATION = "float_contamination"
    UNKNOWN = "unknown"
