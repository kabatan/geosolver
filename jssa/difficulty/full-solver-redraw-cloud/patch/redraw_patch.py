"""Patch the frozen solver in-process with one change: LM multistart starts that fail hard feasibility are redrawn.

Verification modification for preregistration-4 (start-feasibility-1023). Only the start list built by
`_build_local_start_sequence_with_kinds` changes: each start that is not an NOMAD-provided prefix point and
fails the frozen hard-feasibility check is replaced by uniform draws from the same box (RNG [seed, 99, k])
until one passes, at most 2000 redraws. If the first 400 redraws of a start sequence find no feasible
point at all, later starts of that sequence are left unchanged (the box has almost no feasible volume;
this cap was fixed before the run).
Imported by sitecustomize.py when REDRAW_MODE is set. With REDRAW_MODE=plain nothing changes: it only counts
the start sequences (to see whether the LM multistart stage ran at all). statistics are rewritten to $REDRAW_STATS (JSON)
after every start sequence, because the worker can be killed at the deadline.
"""
from __future__ import annotations

import json
import os

import numpy as np

from geosolver.engine.standard.search import scipy_multistart_backend as smb  # noqa: E402

MODE = os.environ.get("REDRAW_MODE", "plain")
STATS = {"mode": MODE, "pid": os.getpid(), "sequences": 0, "starts": 0, "checked": 0, "infeasible": 0, "replaced": 0,
         "redraws": 0, "gave_up_sequences": 0}
_current = {"ev": None}


def _feasible(ev, x) -> bool:
    try:
        return bool(ev.evaluate_float_hard_feasibility(list(map(float, x)), include_margins=False).hard_feasible)
    except Exception:  # noqa: BLE001
        return False


_orig_build = smb._build_local_start_sequence_with_kinds
_orig_run = smb.ScipyMultistartBackend.run_search

def run_search(self, *, bundle, evaluator, **kwargs):
    _current["ev"] = evaluator
    try:
        return _orig_run(self, bundle=bundle, evaluator=evaluator, **kwargs)
    finally:
        _current["ev"] = None

def build(*, lower, upper, n_starts_halton, burn_in, seed, extra_prefix_points):
    starts, labels, prefix = _orig_build(lower=lower, upper=upper, n_starts_halton=n_starts_halton,
                                         burn_in=burn_in, seed=seed, extra_prefix_points=extra_prefix_points)
    ev = _current["ev"]
    STATS["sequences"] += 1
    if MODE != "redraw" or ev is None:
        STATS["starts"] += len(starts)
        _dump()
        return starts, labels, prefix
    out, tried, found, gave_up = [], 0, 0, False
    for k, (s, label) in enumerate(zip(starts, labels)):
        STATS["starts"] += 1
        if label == "extra_prefix" or gave_up:
            out.append(s)
            continue
        STATS["checked"] += 1
        if _feasible(ev, s):
            out.append(s)
            continue
        STATS["infeasible"] += 1
        rng = np.random.default_rng([int(seed), 99, k])
        x, n, ok = s, 0, False
        while n < 2000:
            x = lower + rng.random(lower.size) * (upper - lower)
            n += 1
            if _feasible(ev, x):
                ok = True
                break
            if found == 0 and tried + n >= 400:
                gave_up = True
                break
        tried += n
        STATS["redraws"] += n
        if ok:
            found += 1
            STATS["replaced"] += 1
            out.append(np.asarray(x, dtype=float))
        else:
            out.append(s)
    if gave_up:
        STATS["gave_up_sequences"] += 1
    _dump()
    return tuple(out), labels, prefix

smb.ScipyMultistartBackend.run_search = run_search
smb._build_local_start_sequence_with_kinds = build


def _dump():
    path = os.environ.get("REDRAW_STATS")
    if path:
        with open(path, "w") as f:
            json.dump(STATS, f)


# Arm B of preregistration-4 (追記2): with LM_FIRST=1, the first search stage uses the frozen LM multistart
# (scipy_multistart) instead of disco_mads, so that the start list above drives the whole search.
if os.environ.get("LM_FIRST") == "1":
    from geosolver.engine.standard.orchestration import run_search as _rs

    _orig_baseline = _rs._run_search_baseline

    def _baseline(*args, search_mode, **kwargs):
        if search_mode == _rs.SEARCH_MODE_DISCO_MADS:
            search_mode = _rs.SEARCH_MODE_SCIPY_MULTISTART
        return _orig_baseline(*args, search_mode=search_mode, **kwargs)

    _rs._run_search_baseline = _baseline
