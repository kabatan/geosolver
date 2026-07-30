import mpmath as mp

from candidate import solve_adaptive
from run_generated import I, ROT, ROT2, Problem


def test_easy_and_hard_quadratic_promote():
    for scale in ("1", "1e12"):
        p = Problem("quadratic", scale, "1", "0", "0", I, I, "1e-8")
        assert solve_adaptive(p.model(), p.start()).proposal_only


def test_orthogonal_decision_invariant():
    base = Problem("quadratic", "1e12", "3", "2", ".25", I, I, "1e-8")
    rot = Problem("quadratic", "1e12", "3", "2", ".25", ROT, ROT2, "1e-8")
    assert solve_adaptive(base.model(), base.start()).proposal_only
    assert solve_adaptive(rot.model(), rot.start()).proposal_only


def test_higher_depth_fails_closed():
    p = Problem("cubic", "1", "1", "0", "0", I, I, "1e-8")
    assert not solve_adaptive(p.model(), p.start()).proposal_only


def test_opaque_fallback_is_zero_work():
    p = Problem("quadratic", "1", "1", "0", "0", I, I, "1e-8", True)
    r = solve_adaptive(p.model(), p.start())
    assert not r.proposal_only and r.reason == "opaque-fallback" and r.callbacks == 0


def test_nonisolated_and_nonroot_controls_do_not_propose():
    for mechanism in ("manifold", "close_regular", "inconsistent"):
        p = Problem(mechanism, "1", "1", ".25", ".125", ROT, ROT2, "1e-8")
        assert not solve_adaptive(p.model(), p.start()).proposal_only


def test_transformed_truth_is_a_high_precision_root():
    p = Problem("quadratic", "1e12", "3", "2", ".25", ROT, ROT2, "1e-8")
    with mp.workprec(384):
        assert mp.norm(p.model().replay_residual(p.truth_root())) < mp.mpf("1e-90")
