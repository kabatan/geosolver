"""Synthetic polynomial candidate and completion records shared by solver tests."""

import importlib
from types import SimpleNamespace

from mpmath import mp

from geosolver.engine.standard.contracts.candidate_record import (
    FloatCandidate,
    RefinedCandidate,
    RefinementBatchResult,
    SearchBatchResult,
)
from geosolver.engine.standard.evaluation.classify_evaluation_failure import EvaluationStatus
from geosolver.engine.standard.orchestration.assemble_exact_results import ExactAssemblyResult

pipeline = importlib.import_module("geosolver.engine.standard.orchestration.run_external_pipeline")


def source(index, *, backend="exact_polynomial", attempt=0):
    return FloatCandidate(
        (float(index),),
        0,
        0,
        True,
        EvaluationStatus.OK,
        0,
        index,
        candidate_id=index,
        origin_backend=backend,
        origin_attempt=attempt,
        originating_branch_box=((str(index - 0.25), str(index + 0.25)),),
    )


def refined(origin):
    return RefinedCandidate(
        (mp.mpf(origin.x_float[0]),),
        mp.mpf(0),
        mp.mpf(1),
        "target_reached",
        (),
        source=origin,
        candidate_id=origin.candidate_id,
        hard_feasible=True,
        revision=2,
        coordinate_uncertainty=(mp.mpf("1e-60"),),
    )


def outcome(attempt, proposals, accepted, values):
    assembly = ExactAssemblyResult(
        accepted,
        accepted,
        tuple(values),
        tuple(SimpleNamespace(candidate=c) for c in accepted),
        tuple(values),
        0,
        (),
        tuple({"candidate_uid": c.candidate_uid, "verified": True} for c in accepted),
    )
    stage = pipeline._CompletedPipelineStageState(
        initial_probe_result=None,
        search_result=SearchBatchResult(proposals, len(proposals), 0, all_records=proposals),
        refinement_result=RefinementBatchResult(accepted, len(accepted), len(accepted)),
        exact_assembly_result=assembly,
        rescue_search_summary={},
        integer_fallback_summary={},
    )
    return pipeline._OrderedSearchAttemptOutcome(attempt, stage)
