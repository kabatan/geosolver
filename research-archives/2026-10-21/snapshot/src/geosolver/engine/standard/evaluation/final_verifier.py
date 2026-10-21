"""Final verification with branch-aware differences and coordinate uncertainty."""

from dataclasses import dataclass
from fractions import Fraction

from mpmath import mp

from geosolver.engine.standard.evaluation.snapshots import uses_evaluation_store
from geosolver.engine.standard.evaluation.verification_domains import DomainVerifier
from geosolver.engine.standard.evaluation.verification_numerics import (
    correction,
    linearization,
    normalized_error,
)
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.problem.domain_bounds import affine
from geosolver.runtime.deadline import check_deadline

FINAL_NORMALIZED_RESIDUAL_THRESHOLD = mp.mpf("1e-30")
FINAL_PRECISION_SCHEDULE = (80, 120, 180, 250, 350, 500)


@dataclass(frozen=True)
class FinalVerificationResult:
    verified: bool
    status: str
    normalized_residual: object
    precision_dps: int
    residual_norm: object
    hard_feasible: bool
    hard_failure_tags: tuple[str, ...]
    min_margin: object | None
    values: tuple[object, ...] = ()
    coordinate_uncertainty: tuple[object, ...] = ()
    answer_hp: object | None = None
    answer_uncertainty: object | None = None
    branch_trace: tuple[object, ...] = ()
    evidence: tuple[dict[str, object], ...] = ()


def _variable_scales(evaluator, values):
    plan = getattr(evaluator.bundle, "analysis_plan", None)
    bounds = (
        plan.bounds_at_precision(mp.dps)
        if plan is not None
        else infer_problem_bounds(evaluator.bundle)
    )
    return tuple(
        max(abs(mp.mpf(hi) - mp.mpf(lo)), abs(v), mp.mpf(1))
        for v, (lo, hi) in zip(values, bounds, strict=True)
    )


def _inside_explicit_bounds(evaluator, values):
    for value, entry in zip(values, evaluator.bundle.spec.bounds or (), strict=False):
        if entry is None:
            continue
        lo, hi = entry
        if lo is not None and value < mp.mpf(str(lo)):
            return False
        if hi is not None and value > mp.mpf(str(hi)):
            return False
    return True


def _exact_linear_configuration(equations, names, point):
    """A binary rational point can satisfy rational affine equations exactly."""
    from mpmath.libmp import to_rational

    coordinates = {
        name: Fraction(*to_rational(value._mpf_)) for name, value in zip(names, point, strict=True)
    }
    for equation in equations:
        coefficients = affine(equation.source, set(names))
        if coefficients is None:
            return False
        a, b = coefficients
        if b + sum(c * coordinates[name] for name, c in a.items()) != 0:
            return False
    return True


@uses_evaluation_store()
def verify_final_candidate(*, evaluator, values, precision_schedule=FINAL_PRECISION_SCHEDULE):
    """Refine on independent coordinates, but validate every original condition.

    No nonsingular full Jacobian or isolated configuration is required. Estimates
    that cannot separate a candidate from a forbidden boundary remain unresolved.
    """
    point = tuple(values)
    scales = _variable_scales(evaluator, point)
    equations = evaluator.verification_equations
    active_columns = getattr(evaluator, "active_verification_columns", None)
    if active_columns is None:
        active_columns = tuple(
            j
            for j, name in enumerate(evaluator.bundle.var_names)
            if any(equation.constant is None and name in equation.names for equation in equations)
        )
    previous_point, previous_residuals, previous_valid = None, None, False
    latest = None
    for precision in precision_schedule:
        check_deadline()
        with mp.workdps(precision), high_precision_mode():
            if not _inside_explicit_bounds(evaluator, point):
                return FinalVerificationResult(
                    False,
                    "bounds_violation",
                    mp.inf,
                    precision,
                    mp.inf,
                    False,
                    ("bounds_violation",),
                    None,
                    values=point,
                )
            try:
                # Low-precision screening must not discard already refined bits.
                # Arithmetic below is local to this pass; retain the best point.
                uncertainty = tuple(mp.mpf(0) for _ in point)
                for update in range(9):
                    base_samples = []
                    residuals, jacobian, errors, term_scales = linearization(
                        equations,
                        point,
                        evaluator.bundle.var_names,
                        scales,
                        precision,
                        base_samples=base_samples,
                    )
                    if any(not mp.isfinite(r) for r in residuals):
                        raise ValueError("non-finite residual during verification")
                    change, estimate = correction(
                        residuals,
                        jacobian,
                        errors,
                        scales,
                        precision,
                        evaluation_scales=term_scales,
                        active_columns=active_columns,
                    )
                    if change is None:
                        uncertainty = tuple(mp.inf for _ in point)
                        break
                    uncertainty = estimate
                    if update == 8 or not any(change) or not any(residuals):
                        break

                    # A correction must improve the original full system and
                    # follow the natural branch. No fixed selector is imposed.
                    def score(values, term_scales=term_scales):
                        return mp.fsum(
                            max(0, abs(r) - mp.eps * s) / s if s else abs(r)
                            for r, s in zip(values, term_scales, strict=True)
                        )

                    old_score = score(residuals)
                    if old_score == 0:
                        break
                    with mp.workprec(max(mp.prec, max((x._mpf_[3] for x in point), default=0))):
                        trial = tuple(x + d for x, d in zip(point, change, strict=True))
                    from geosolver.engine.standard.evaluation.verification_numerics import (
                        same_branches,
                    )

                    trial_residuals = []
                    follows_branch = True
                    from .verification_system import sample_equations

                    trial_samples = sample_equations(equations, trial, precision)
                    for trial_sample, base_sample in zip(trial_samples, base_samples, strict=True):
                        _, at, _ = base_sample
                        b, bt, _ = trial_sample
                        follows_branch &= same_branches(at, bt)
                        trial_residuals.append(b)
                    if not follows_branch or any(not mp.isfinite(r) for r in trial_residuals):
                        break
                    new_score = score(trial_residuals)
                    if new_score >= old_score:
                        break
                    point = trial
                if previous_point is not None:
                    uncertainty = tuple(
                        max(u, abs(x - y))
                        for u, x, y in zip(uncertainty, point, previous_point, strict=True)
                    )
                if not any(residuals) and _exact_linear_configuration(
                    equations, evaluator.bundle.var_names, point
                ):
                    uncertainty = tuple(mp.mpf(0) for _ in point)
                normalized = normalized_error(
                    equations, residuals, jacobian, errors, scales, previous_residuals, term_scales
                )
                zero_sources = tuple(
                    equation.source
                    for equation, residual, scale in zip(
                        equations, residuals, term_scales, strict=True
                    )
                    if mp.isfinite(scale) and abs(residual) <= 128 * mp.eps * scale
                )
                domain = DomainVerifier(
                    evaluator, point, uncertainty, scales, precision, zero_sources
                )
                domain_state, trace, evidence = domain.verify()
                hard = evaluator.evaluate_hp_hard_feasibility(
                    point, precision=precision, include_margins=True
                )
                valid = (
                    domain_state is True
                    and hard.hard_feasible
                    and normalized <= FINAL_NORMALIZED_RESIDUAL_THRESHOLD
                )
                answer, answer_error = domain.answer() if valid else (None, None)
                valid = (
                    valid
                    and answer is not None
                    and mp.isfinite(answer)
                    and mp.isfinite(answer_error)
                )
                tags = tuple(hard.failure_tags)
                if domain_state is not True:
                    tags += (
                        "domain_boundary_unresolved"
                        if domain_state is None
                        else "domain_violation",
                    )
                latest = FinalVerificationResult(
                    bool(valid and previous_valid and precision >= 180),
                    "verified"
                    if valid and previous_valid and precision >= 180
                    else "verification_unresolved",
                    +normalized,
                    precision,
                    mp.sqrt(mp.fsum(r * r for r in residuals)),
                    bool(domain_state is True and hard.hard_feasible),
                    tags,
                    hard.min_margin,
                    values=point,
                    coordinate_uncertainty=uncertainty,
                    answer_hp=answer,
                    answer_uncertainty=answer_error,
                    branch_trace=trace,
                    evidence=evidence,
                )
                if latest.verified:
                    return latest
                previous_point, previous_residuals, previous_valid = point, residuals, valid
            except TimeoutError:
                raise
            except Exception as exc:
                latest = FinalVerificationResult(
                    False,
                    "verification_unresolved",
                    mp.inf,
                    precision,
                    mp.inf,
                    False,
                    (f"verification_error:{type(exc).__name__}",),
                    None,
                    values=point,
                )
                previous_valid = False
    assert latest is not None
    return latest
