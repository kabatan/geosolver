"""Local arithmetic-error estimates at fixed coordinates (not existence proofs)."""

from mpmath import mp

from geosolver.runtime.deadline import check_deadline


def precision_sample(function, point, precision):
    """Compare the same physical branch at two arithmetic precisions.

    Cancellation inside a geometric primitive is measured here, instead of
    assuming its roundoff is proportional to its possibly tiny final residual.
    The coordinates themselves are never rounded in place.
    """
    from geosolver.engine.standard.evaluation.verification_numerics import same_branches

    check_deadline()
    with mp.workdps(precision):
        low, trace = function(point)
        epsilon = +mp.eps
    with mp.workdps(precision + 30):
        high, other = function(point)
        if not mp.isfinite(low) or not mp.isfinite(high) or not same_branches(trace, other):
            return high, tuple(other), mp.inf
        error = 4 * abs(high - low) + 32 * epsilon * abs(high)
    return high, tuple(other), error
