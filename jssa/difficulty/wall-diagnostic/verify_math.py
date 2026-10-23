"""Deterministic checks of the numerical definition; no local optimization."""
import numpy as np
from experiment import HERE, one_step, context, finite_residual, smb, write_json


def main():
    checks = {}
    linear = lambda x: np.array([x[0] - 1, 0.0])
    F = lambda x: bool(x[0] < .25)
    r = one_step(np.array([0.0]), np.array([-2.0]), np.array([2.0]), linear, F)
    assert r["status"] == "decrease" and r["trial_F"] is False and r["alpha"] == 1
    assert np.allclose(r["delta"], [1 / 1.001], rtol=1e-8)
    checks["analytic_ridge_direction"] = True

    r = one_step(np.array([0.0]), np.array([-2.0]), np.array([.6]), linear, F)
    assert r["alpha"] == .5 and r["trial_outside_box"] == 1
    checks["first_in_box_decrease"] = True

    guard = lambda x: np.array([x[0] - 1, 2 * x[0]])
    r = one_step(np.array([0.0]), np.array([-2.0]), np.array([2.0]), guard, lambda x: True)
    assert np.allclose(r["delta"], [.2 / 1.001], rtol=1e-8)
    checks["guard_row_retained"] = True

    r = one_step(np.array([0.0]), np.array([-2.0]), np.array([2.0]),
                 linear, lambda x: True if x[0] == 0 else None)
    assert r["status"] == "trial_hard_error" and r["alpha"] == 1
    checks["no_retry_after_hard_error"] = True
    r = one_step(np.array([0.0]), np.array([-2.0]), np.array([2.0]),
                 lambda x: linear(x) if x[0] <= 0 else None, F)
    assert r["status"] == "difference_invalid"
    checks["invalid_difference_excluded"] = True
    r = one_step(np.array([1.0]), np.array([-2.0]), np.array([2.0]), linear, lambda x: True)
    assert r["status"] == "zero_or_nonfinite_ss"
    checks["zero_not_decrease"] = True

    # Compare only direct residual evaluation, never invoke a solver here.
    _, bundle, ev, bounds = context("AIME-2010-II-14")
    lo, hi = bounds.T
    for z in [.2, .5, .8]:
        x = lo + z * (hi - lo)
        vector = smb._evaluate_augmented_residual_vector(bundle=bundle, evaluator=ev, values=x,
            n_constraints=len(bundle.spec.constraints), telemetry=smb._SearchTelemetry())
        v = finite_residual(bundle, ev, x)
        assert v is not None and np.array_equal(v, vector[:-1])
    checks["matches_frozen_augmented_without_hard"] = True
    write_json(HERE / "math-checks.json", checks)
    print(checks)


if __name__ == "__main__":
    main()
