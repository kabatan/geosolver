from collections import OrderedDict
from types import SimpleNamespace

import pytest
from mpmath import mp

from geosolver.runtime.deadline import deadline_scope


def test_only_completed_success_at_identical_coordinates_and_schedule_is_shared(monkeypatch):
    import importlib

    assembly = importlib.import_module(
        "geosolver.engine.standard.orchestration.assemble_exact_results"
    )
    evaluator = SimpleNamespace(
        final_verification_cache=OrderedDict(), verified_coordinate_cache=OrderedDict()
    )
    candidate = SimpleNamespace(candidate_key="a", revision=0, x_hp=(mp.mpf(1),))
    calls = []
    success = SimpleNamespace(verified=True)

    def verify(**kwargs):
        calls.append(kwargs)
        return success

    monkeypatch.setattr(assembly, "verify_final_candidate", verify)
    assert assembly._verify_revision(evaluator, candidate) is success
    other = SimpleNamespace(**(vars(candidate) | {"candidate_key": "b"}))
    assert assembly._verify_revision(evaluator, other) is success
    assert len(calls) == 1
    assembly._verify_revision(evaluator, other, precision_schedule=(250, 350, 500))
    assert len(calls) == 2
    with mp.workdps(200):
        close = SimpleNamespace(**(vars(other) | {"x_hp": (mp.mpf(1) + mp.mpf("1e-150"),)}))
    assembly._verify_revision(evaluator, close)
    assert len(calls) == 3
    with deadline_scope(0), pytest.raises(TimeoutError):
        assembly._verify_revision(evaluator, other)


@pytest.mark.parametrize("interrupted", [False, True])
def test_unresolved_or_interrupted_results_are_not_shared_between_candidates(
    monkeypatch, interrupted
):
    import importlib

    assembly = importlib.import_module(
        "geosolver.engine.standard.orchestration.assemble_exact_results"
    )
    evaluator = SimpleNamespace(
        final_verification_cache=OrderedDict(), verified_coordinate_cache=OrderedDict()
    )
    calls = []

    def verify(**kwargs):
        calls.append(kwargs)
        if interrupted:
            raise TimeoutError("fixture")
        return SimpleNamespace(verified=False)

    monkeypatch.setattr(assembly, "verify_final_candidate", verify)
    for key in ("a", "b"):
        candidate = SimpleNamespace(candidate_key=key, revision=0, x_hp=(mp.mpf(1),))
        if interrupted:
            with pytest.raises(TimeoutError):
                assembly._verify_revision(evaluator, candidate)
        else:
            assembly._verify_revision(evaluator, candidate)
    assert len(calls) == 2
    assert not evaluator.verified_coordinate_cache
