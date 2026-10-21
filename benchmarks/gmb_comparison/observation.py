"""Temporary, observation-only hooks around completed candidate returns.

No extra optimizer/refiner call, early stopping, goal feedback, or deduplication
is introduced. Materialization/serialization cost remains inside the run budget.
"""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from functools import wraps


@contextmanager
def observe_candidates(sink, *, include_intermediate=False):
    from geosolver.engine.standard.refinement.mpmath_refiner import MpmathRefiner

    assembly = importlib.import_module(
        "geosolver.engine.standard.orchestration.assemble_exact_results"
    )
    pipeline = importlib.import_module(
        "geosolver.engine.standard.orchestration.run_external_pipeline"
    )
    original_refine = MpmathRefiner._refine_single_candidate
    original_revise = assembly._revise
    original_assemble = assembly.assemble_exact_results
    original_pipeline_alias = pipeline.assemble_exact_results

    @wraps(original_refine)
    def refine(self, *args, **kwargs):
        results = original_refine(self, *args, **kwargs)
        for candidate in results:
            sink(candidate, "refinement_return")
        return results

    @wraps(original_revise)
    def revise(*args, **kwargs):
        candidate = original_revise(*args, **kwargs)
        sink(candidate, "verified_candidate_revision")
        return candidate

    @wraps(original_assemble)
    def assemble(*args, **kwargs):
        result = original_assemble(*args, **kwargs)
        for candidate in result.accepted_candidates:
            sink(candidate, "native_accepted_return")
        return result

    if include_intermediate:
        MpmathRefiner._refine_single_candidate = refine
        assembly._revise = revise
    assembly.assemble_exact_results = assemble
    pipeline.assemble_exact_results = assemble
    try:
        yield
    finally:
        MpmathRefiner._refine_single_candidate = original_refine
        assembly._revise = original_revise
        assembly.assemble_exact_results = original_assemble
        pipeline.assemble_exact_results = original_pipeline_alias
