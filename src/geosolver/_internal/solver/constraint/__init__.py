"""Constraint projection building blocks and orchestrator."""

from collections.abc import Callable, Sequence

from .convergence import is_converged, residual_norm
from .evaluate import evaluate_constraint_residuals
from .jacobian import compute_constraint_jacobian
from .newton_step import compute_newton_step
from .trust_region import apply_trust_region


def project_constraint_once(
	constraints: Sequence[Callable[[Sequence[float]], float]],
	point: Sequence[float],
	targets: Sequence[float],
	*,
	delta: float = 1e-8,
	trust_radius: float = 1.0,
	tolerance: float = 1e-8,
) -> tuple[list[float], float, bool]:
	"""Run one projected update using all split constraint modules."""
	residuals = evaluate_constraint_residuals(constraints, point, targets)
	jacobian = compute_constraint_jacobian(
		lambda x: evaluate_constraint_residuals(constraints, x, [0.0] * len(constraints)), point, delta
	)
	step = apply_trust_region(compute_newton_step(jacobian, residuals), trust_radius)
	updated = [float(value) + float(delta_value) for value, delta_value in zip(point, step)]
	next_residuals = evaluate_constraint_residuals(constraints, updated, targets)
	return updated, residual_norm(next_residuals), is_converged(next_residuals, tolerance)


__all__ = [
	"apply_trust_region",
	"compute_constraint_jacobian",
	"compute_newton_step",
	"evaluate_constraint_residuals",
	"is_converged",
	"project_constraint_once",
	"residual_norm",
]
