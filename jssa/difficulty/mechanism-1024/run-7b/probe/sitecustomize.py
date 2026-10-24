"""Observe the same calls as switches/verify-log.md, retaining timeout counts.

The 8-byte mmap counter survives worker termination. Handoff events are appended
before refinement; the original functions and their results are unchanged.
"""
import os

if os.environ.get("SWITCH_PROBE_OUT"):
    import importlib
    import json
    import mmap
    import struct
    from functools import wraps
    from pathlib import Path

    prefix = os.environ["SWITCH_PROBE_OUT"] + "." + str(os.getpid())
    stream = open(prefix + ".counter", "w+b")
    stream.write(b"\0" * 8)
    stream.flush()
    counter = mmap.mmap(stream.fileno(), 8)
    count = 0

    def emit(kind, **values):
        with open(prefix + ".jsonl", "a") as output:
            output.write(json.dumps({"kind": kind, **values}, allow_nan=True) + "\n")

    emit("initialized", pid=os.getpid())
    pipeline = importlib.import_module("geosolver.engine.standard.orchestration.run_external_pipeline")
    refinement = importlib.import_module("geosolver.engine.standard.refinement.mpmath_refiner")
    rescue = importlib.import_module("geosolver.engine.standard.orchestration.run_rescue_search")
    original_smooth = refinement._smooth_zero_constraint_residuals

    @wraps(original_smooth)
    def smooth(*args, **kwargs):
        global count
        count += 1
        struct.pack_into("Q", counter, 0, count)
        return original_smooth(*args, **kwargs)

    refinement._smooth_zero_constraint_residuals = smooth

    def observe_refine(original, added=False):
        @wraps(original)
        def call(**kwargs):
            result = None if added else kwargs["search_result"]
            candidates = kwargs["candidates"] if added else result.candidates
            pool = None if added else result.refinement_selection_pool
            emit("added" if added else "main", selected=len(candidates),
                 all_records=None if added else len(result.all_records),
                 pool=None if pool is None else len(pool),
                 uids=[c.candidate_uid for c in candidates],
                 norms=[c.residual_norm_float for c in candidates])
            value = original(**kwargs)
            emit("refinement_return", attempted=value.attempted_count,
                 converged=value.converged_count, hard_feasible=value.hard_feasible_count)
            return value
        return call

    pipeline.run_refinement = observe_refine(pipeline.run_refinement)
    pipeline.refine_added_candidates = observe_refine(pipeline.refine_added_candidates, True)
    original_select = pipeline.select_residual_candidates

    @wraps(original_select)
    def select(records):
        records = tuple(records)
        candidates = original_select(records)
        emit("selection", pool=len(records), selected=len(candidates),
             uids=[c.candidate_uid for c in candidates],
             norms=[c.residual_norm_float for c in candidates])
        return candidates

    pipeline.select_residual_candidates = select
    rescue.select_residual_candidates = select
