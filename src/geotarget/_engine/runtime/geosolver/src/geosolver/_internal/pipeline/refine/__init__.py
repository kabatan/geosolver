"""High-precision local refinement for external pipeline."""

from .deduplicate_refined_candidates import deduplicate_refined_candidates
from .finite_difference_jacobian import compute_finite_difference_jacobian
from .levenberg_marquardt_step import compute_levenberg_marquardt_step
from .line_search import run_line_search
from .mpmath_refiner import MpmathRefiner
from .refiner_config import RefinerConfig

__all__ = [
    "MpmathRefiner",
    "RefinerConfig",
    "compute_finite_difference_jacobian",
    "compute_levenberg_marquardt_step",
    "deduplicate_refined_candidates",
    "run_line_search",
]

