"""Public GeoTarget API."""

from geotarget.models import SolveOptions, SolveResult, V15Problem, ValidationReport
from geotarget.service import solve
from geotarget.validation import validate

__all__ = [
    "SolveOptions",
    "SolveResult",
    "V15Problem",
    "ValidationReport",
    "solve",
    "validate",
]

__version__ = "1.0.0"
