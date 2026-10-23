"""Run the frozen solver's CLI with one change: LM multistart starts that fail hard feasibility are redrawn.

Verification modification for preregistration-4 (start-feasibility-1023). Only the start list built by
`_build_local_start_sequence_with_kinds` changes: each start that is not an NOMAD-provided prefix point and
fails the frozen hard-feasibility check is replaced by uniform draws from the same box (RNG [seed, 99, k])
until one passes, at most 2000 redraws. If the first 400 redraws of a start sequence find no feasible
point at all, later starts of that sequence are left unchanged (the box has almost no feasible volume;
this cap was fixed before the run). Usage: python redraw_cli.py MODE solve ...  (MODE = plain | redraw);
statistics go to $REDRAW_STATS (JSON) when set.
"""
from __future__ import annotations

import atexit
import json
import os
import sys

import numpy as np

MODE = sys.argv.pop(1)
from geosolver.engine.standard.search import scipy_multistart_backend as smb  # noqa: E402

STATS = {"mode": MODE, "sequences": 0, "starts": 0, "checked": 0, "infeasible": 0, "replaced": 0,
         "redraws": 0, "gave_up_sequences": 0}
_current = {"ev": None}


def _feasible(ev, x) -> bool:
    try:
        return bool(ev.evaluate_float_hard_feasibility(list(map(float, x)), include_margins=False).hard_feasible)
    except Exception:  # noqa: BLE001
        return False


if MODE == "redraw":
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
        if ev is None:
            return starts, labels, prefix
        STATS["sequences"] += 1
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
        return tuple(out), labels, prefix

    smb.ScipyMultistartBackend.run_search = run_search
    smb._build_local_start_sequence_with_kinds = build


def _dump():
    path = os.environ.get("REDRAW_STATS")
    if path:
        with open(path, "w") as f:
            json.dump(STATS, f)


atexit.register(_dump)

from geosolver.application.cli import app  # noqa: E402

app()
