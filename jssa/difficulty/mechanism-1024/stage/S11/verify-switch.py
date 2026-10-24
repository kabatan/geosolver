#!/usr/bin/env python3
"""S11 preparation only: two tiny backend problems, all mutations under /tmp."""
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import importlib
import importlib.util
import io
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections import Counter


def emit(**record):
    print(json.dumps(record, ensure_ascii=False, sort_keys=True), flush=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--frozen-root", type=Path)
    args = parser.parse_args()
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    resource.setrlimit(resource.RLIMIT_CPU, (45, 45))
    signal.alarm(55)
    for name in list(os.environ):
        if name.startswith("GEOSOLVER_"):
            del os.environ[name]
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
        os.environ[name] = "1"
    sys.dont_write_bytecode = True
    started = time.monotonic()
    repo = args.source_root.resolve()
    relative = Path("src/geosolver/engine/standard/search/scipy_multistart_backend.py")
    patch = Path(__file__).resolve().with_name("halton-start-count.patch")
    before = sha(repo / relative)
    scratch = Path(tempfile.mkdtemp(prefix="mechanism-S11-prep-", dir="/tmp"))
    # Leave this task's own small copy available for inspection; touch no other runs.
    shutil.copytree(repo / "src", scratch / "src", ignore=shutil.ignore_patterns("__pycache__"))
    sys.path.insert(0, str(scratch / "src"))
    import numpy as np
    import scipy
    import geosolver
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.search.nomad_config import NomadConfig

    module_name = "geosolver.engine.standard.search.scipy_multistart_backend"
    alias = module_name + "_s11_original"
    spec = importlib.util.spec_from_file_location(alias, scratch / relative)
    original = importlib.util.module_from_spec(spec)
    sys.modules[alias] = original
    spec.loader.exec_module(original)
    applied = subprocess.run(
        ["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch)],
        cwd=scratch, text=True, capture_output=True, check=True,
    )
    backend = importlib.import_module(module_name)
    assert Path(backend.__file__).resolve() == scratch / relative
    assert Path(geosolver.__file__).resolve().is_relative_to(scratch)
    emit(event="setup", source_root=str(repo), source_sha256=before,
         patch_sha256=sha(patch), patched_sha256=sha(scratch / relative),
         scratch=str(scratch), python=sys.version.split()[0], numpy=np.__version__,
         scipy=scipy.__version__, affinity=sorted(os.sched_getaffinity(0)),
         threads=1, cpu_limit_sec=45, wall_alarm_sec=55,
         patch_output=applied.stdout.strip())
    config = NomadConfig(max_bb_eval=20, max_time_sec=8.0, seed_values=(801,))
    bounds = [(-1.0, 1.0), (-1.0, 1.0)]
    extra = ([0.91, -0.83],)
    problems = {
        "linear2": ["x-0.125", "y+0.25"],
        "quadratic2": ["x*x-0.25", "y*y-0.0625"],
    }

    def run(mod, constraints):
        bundle = load_problem_bundle({
            "task": "solve", "variables": {"names": ["x", "y"]},
            "construction": [], "constraints": constraints, "guards": [], "answer": "x+y",
        })
        evaluator = build_ir_evaluator(bundle)
        calls = Counter()
        generated = {}
        real_least_squares = mod.least_squares
        real_halton = mod._build_halton_starts

        def counted_solver(*a, **kw):
            calls[kw["method"]] += 1
            return real_least_squares(*a, **kw)

        def counted_halton(**kw):
            points = real_halton(**kw)
            generated[kw["family_tag"]] = tuple(tuple(map(float, p)) for p in points)
            assert len(points) == kw["n_starts"]
            return points

        mod.least_squares = counted_solver
        mod._build_halton_starts = counted_halton
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                result = mod.ScipyMultistartBackend(config, extra).run_search(
                    bundle=bundle, evaluator=evaluator, bounds=bounds)
        finally:
            mod.least_squares = real_least_squares
            mod._build_halton_starts = real_halton
        events = result.search_diagnostics["local_start_events"]
        kinds = Counter(e["start_kind"] for e in events)
        assert all(e["status"] == "finished" for e in events)
        k = mod._N_HALTON_STARTS
        assert sum(kinds[t] for t in ("halton_prefix", "front_tail", "remaining_tail")) == k
        assert calls == {"lm": k + 6, "trf": 24}, calls
        assert sum(c.origin_family == "2" for c in result.all_records) == 24
        assert sum(c.origin_family == "1" for c in result.all_records) == k + 6
        assert any(mod._is_admissible_candidate(c) for c in result.all_records)
        starts, labels, shallow = mod._build_local_start_sequence_with_kinds(
            lower=np.array([-1., -1.]), upper=np.array([1., 1.]), n_starts_halton=k,
            burn_in=0, seed=801, extra_prefix_points=extra)
        nonhalton = sorted(tuple(map(float, p)) for p, label in zip(starts, labels, strict=True)
                           if label in ("extra_prefix", "front_anchor", "final_anchor"))
        # Exact comparison includes selected/all candidates, scores, evaluations and telemetry.
        signature = dataclasses.asdict(result)
        emit(event="problem", problem=constraints, k=k,
             env=os.environ.get("GEOSOLVER_SCIPY_N_HALTON_STARTS"),
             module="original" if mod is original else "patched",
             actual_optimizer_calls=dict(calls), actual_local_kinds=dict(kinds),
             local_events=len(events), seed_prefix_count=shallow,
             local_halton_generated=len(generated["local_halton"]),
             trf_halton_generated=len(generated["bounded_trf"]),
             nonhalton_start_count=len(nonhalton), evaluation_count=result.evaluation_count)
        return signature, generated, nonhalton

    for name, constraints in problems.items():
        baseline, baseline_points, baseline_nonhalton = run(original, constraints)
        signatures = {}
        for value in (None, "1", "4", "16", "64", "320"):
            if value is None:
                os.environ.pop("GEOSOLVER_SCIPY_N_HALTON_STARTS", None)
            else:
                os.environ["GEOSOLVER_SCIPY_N_HALTON_STARTS"] = value
            backend = importlib.reload(backend)
            signature, points, nonhalton = run(backend, constraints)
            k = backend._N_HALTON_STARTS
            assert points["local_halton"] == baseline_points["local_halton"][:k]
            assert points["bounded_trf"] == baseline_points["bounded_trf"]
            assert nonhalton == baseline_nonhalton
            if k == 320:
                assert signature == baseline
            signatures[value] = signature
        assert signatures[None] == signatures["320"] == baseline
        emit(event="equivalence_pass", name=name,
             unset_equals_original=True, explicit_320_equals_original=True,
             halton_nested_prefix=True, trf_points_unchanged=True,
             nonhalton_points_unchanged=True)
    for value in ("0", "2", "321", "abc", ""):
        os.environ["GEOSOLVER_SCIPY_N_HALTON_STARTS"] = value
        try:
            importlib.reload(backend)
        except ValueError as error:
            emit(event="invalid_value_rejected", value=value, error=str(error))
        else:
            raise AssertionError(f"invalid value accepted: {value!r}")
    if args.frozen_root:
        frozen = args.frozen_root.resolve()
        frozen_before = sha(frozen / relative)
        compat = scratch / "frozen-compatibility"
        (compat / relative).parent.mkdir(parents=True)
        shutil.copy2(frozen / relative, compat / relative)
        check = subprocess.run(
            ["patch", "--batch", "--fuzz=0", "-p1", "-i", str(patch)],
            cwd=compat, text=True, capture_output=True, check=True)
        compile((compat / relative).read_text(), str(compat / relative), "exec")
        assert sha(frozen / relative) == frozen_before
        emit(event="frozen_compatibility", root=str(frozen), sha256=frozen_before,
             patch_output=check.stdout.strip(), syntax_pass=True, original_unchanged=True,
             note="patch and syntax only; no frozen full-N execution")
    assert sha(repo / relative) == before
    emit(event="PASS", source_unchanged=True, elapsed_sec=round(time.monotonic()-started, 3),
         note="backend-only smoke on two tiny problems; no S11 campaign")


if __name__ == "__main__":
    main()
