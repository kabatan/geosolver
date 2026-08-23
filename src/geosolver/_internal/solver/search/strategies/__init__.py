"""Search strategy generators."""

from .halton_random import generate_halton_random_points
from .scale_adaptive import generate_scale_adaptive_points

__all__ = ["generate_halton_random_points", "generate_scale_adaptive_points"]
