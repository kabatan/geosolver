"""Independent Q39 observations. Reference answers never enter solver workers.

Measurement is performed on saved binary coordinates before Phase C starts.
The global additional-observation/assessment allowance is 1,200 worker seconds.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import fcntl
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

import diagnostic as d


@contextmanager
def budget_lock():
    path = d.OUT / "observation-budget.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        yield


def reserve(seconds, label):
    with budget_lock():
        path = d.OUT / "observation-budget.json"
        data = d.read(path) if path.exists() else {
            "limit_worker_seconds": 1200., "remaining": 1200., "spent": 0., "active": {}}
        allowance = min(seconds, max(0., data["remaining"]))
        data["remaining"] -= allowance
        data["active"][label] = {"reserved": allowance, "utc": d.utc()}
        d.save(path, data)
    return allowance


def finish(label, elapsed):
    with budget_lock():
        path = d.OUT / "observation-budget.json"
        data = d.read(path)
        reservation = data["active"].pop(label)
        used = elapsed
        data["spent"] += used
        data["remaining"] += reservation["reserved"] - used
        data["actual_elapsed_including_startup_cleanup"] = data.get(
            "actual_elapsed_including_startup_cleanup", 0.) + elapsed
        d.save(path, data)


def observe_job_in_child(identifier, seed, front_mode, rear_mode):
    """Called by the reference-blind worker after saving all eight final points."""
    destination = d.rear_dir(identifier, seed, front_mode, rear_mode)
    label = f"{identifier}|{seed}|{front_mode}|{rear_mode}"
    allowance = reserve(15., label)
    receipt = {"utc_start": d.utc(), "reserved_seconds": allowance, "reference_isolation": "subprocess"}
    start = time.monotonic()
    if allowance < .1:
        receipt["status"] = "observation_budget_exhausted"
    else:
        args = [sys.executable, str(Path(__file__).resolve()), "job", "--id", identifier,
                "--seed", str(seed), "--front", front_mode, "--rear", rear_mode,
                "--deadline", str(start + allowance)]
        # Parent is idle; the child inherits exactly the same one-CPU affinity.
        with (destination / "observation.log").open("wb") as log:
            process = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT,
                                       env=os.environ.copy(), cwd=d.ROOT)
            try:
                receipt["returncode"] = process.wait(timeout=allowance)
                receipt["status"] = "completed" if process.returncode == 0 else "observation_failed"
            except subprocess.TimeoutExpired:
                import psutil
                try:
                    parent = psutil.Process(process.pid)
                    for p in reversed([parent] + parent.children(recursive=True)):
                        try:
                            p.kill()
                        except psutil.Error:
                            pass
                except psutil.Error:
                    pass
                process.wait(timeout=2)
                receipt["status"] = "observation_timeout"
    elapsed = time.monotonic() - start
    finish(label, elapsed)
    receipt.update(elapsed_seconds=elapsed, utc_end=d.utc())
    d.save(destination / "observation-receipt.json", receipt)


def reference_values(identifier):
    # Importing this module in the parent does not load the corpus or answers.
    if not (d.OUT / "front-seal.json").exists():
        raise RuntimeError("reference access prohibited until front ledger is sealed")
    cache_path = d.OUT / "numeric-references.json"
    if cache_path.exists():
        cache = d.read(cache_path)
        if cache["front_seal_sha256"] != d.sha(d.OUT / "front-seal.json"):
            raise RuntimeError("reference cache belongs to a different sealed front ledger")
        if cache["corpus_sha256"] != d.sha(d.ROOT / "benchmarks/cases.jsonl"):
            raise RuntimeError("reference corpus changed")
        return d.unpacked(cache["values"][identifier])
    from benchmarks import research_runner as rr
    import sympy as sp
    record = next(r for r in rr._load_cases() if r.identifier == identifier)
    expressions = [expr for v in record.references for expr in rr.reference_expressions(v)]
    with d.mp.workdps(180):
        values = [d.mp.mpf(str(sp.sympify(expr).evalf(180))) for expr in expressions]
    if not values or not all(d.mp.isfinite(v) for v in values):
        raise ValueError("nonfinite or missing numeric reference")
    return values


def prepare_references():
    if (d.OUT / "numeric-references.json").exists():
        raise RuntimeError("numeric references already prepared")
    label = "numeric-reference-preparation"
    allowance = reserve(45., label)
    start = time.monotonic()
    values = {}
    try:
        for identifier in d.selected():
            if time.monotonic() - start >= allowance:
                raise TimeoutError("reference observation allowance exhausted")
            values[identifier] = d.packed(reference_values(identifier))
        d.save(d.OUT / "numeric-references.json", {"utc": d.utc(), "dps": 180,
            "front_seal_sha256": d.sha(d.OUT / "front-seal.json"),
            "corpus_sha256": d.sha(d.ROOT / "benchmarks/cases.jsonl"), "values": values})
    finally:
        finish(label, time.monotonic() - start)
    print(json.dumps({"numeric_references": len(values), "dps": 180,
                      "elapsed_seconds": time.monotonic() - start}))


def digits(error, cap=100):
    if error is None or not d.mp.isfinite(error):
        return 0.
    if error == 0:
        return float(cap)
    return float(max(0, min(cap, -d.mp.log10(abs(error)))))


def absent(reason):
    return {"status": reason, "R50": False, "R80": False, "target_digits": 0.,
            "Q_digits": 0., "A_digits": 0., "hard_feasible": False,
            "Q": None, "QA": None, "QB": None, "target_relative_error": None}


def textnum(x):
    return d.mp.nstr(x, 30) if x is not None and d.mp.isfinite(x) else None


def coincident_contacts(bundle, reps, point, a, b):
    plans = d.mr._zero_constraint_plans(tuple(bundle.spec.constraints), tuple(bundle.targets))
    records = []
    for block in reps.plan["blocks"]:
        if not block["rewrite"].get("coincident_circle_caveat"):
            continue
        _, sources = plans[block["a"]]
        context = d.mr.build_solution_context_high_precision(bundle.spec, list(bundle.var_names),
                      point, bundle.base_context, 180, expressions=list(sources))
        objects = [d.mr.safe_eval_expr_hp(s, context) for s in sources]
        c1, c2 = [getattr(c, "circle", c) for c in objects]
        separation = d.mp.sqrt((c1.center.x - c2.center.x)**2 + (c1.center.y - c2.center.y)**2)
        radius_gap = abs(c1.radius - c2.radius)
        scale = max(d.mp.mpf(1), c1.radius, c2.radius)
        exact = separation == 0 and radius_gap == 0
        near = max(separation, radius_gap) / scale <= d.mp.mpf("1e-30")
        if exact or near:
            records.append({"row": block["a"], "exact_at_180dps": exact,
                            "near_at_1e_minus_30": near, "center_separation": textnum(separation),
                            "radius_gap": textnum(radius_gap), "A": textnum(a[block["a"]]),
                            "B": textnum(b[block["b"][0]])})
    return records


def observe_point(evaluator, reps, point, references):
    with d.mp.workdps(180):
        with d.high_precision_mode():
            a = evaluator.evaluate_hp_residual(point, precision=180)
            b, valid = reps.both(point, list(a.residual_vector), 180)
            q, qa, qb = reps.quality(a.residual_vector, b, valid)
            hard = evaluator.evaluate_hp_hard_feasibility(point, precision=180, include_margins=False)
            target = evaluator.evaluate_answer_hp(point, precision=180)
            contacts = coincident_contacts(evaluator.bundle, reps, point, a.residual_vector, b) if valid else []
        # Convert diagnostic scalars only outside the product's HP contract.
        # The point and all numerical evaluations above remain exact mpf inputs.
        value = target.answer_hp
        error = (min(abs(value - v) / max(d.mp.mpf(1), abs(v)) for v in references)
                 if value is not None and d.mp.isfinite(value) else d.mp.inf)
        original_norm = (d.mp.sqrt(d.mp.fsum(v*v for v in a.residual_vector))
                         if a.evaluation_status is d.EvaluationStatus.OK else d.mp.inf)
        common = bool(hard.hard_feasible and a.evaluation_status is d.EvaluationStatus.OK and valid)
        result = {"status": "observed", "hard_feasible": bool(hard.hard_feasible),
                  "hard_failure_tags": list(hard.failure_tags), "B_valid": valid,
                  "Q": textnum(q), "QA": textnum(qa), "QB": textnum(qb),
                  "target_relative_error": textnum(error), "target_digits": digits(error),
                  "Q_digits": digits(q, 180), "A_digits": digits(original_norm, 180),
                  "R50": common and q <= d.mp.mpf("1e-50") and error <= d.mp.mpf("1e-50"),
                  "R80": common and q <= d.mp.mpf("1e-80") and error <= d.mp.mpf("1e-80")}
        result["coincident_contacts"] = contacts
        return result


def measure_job(identifier, seed, front_mode, rear_mode, deadline):
    seal = d.read(d.OUT / "front-seal.json")
    for i in range(8):
        path = d.front_dir(identifier, seed, front_mode) / f"{i}.json"
        if d.sha(path) != seal["sha256"][str(path.relative_to(d.OUT))]:
            raise RuntimeError("front candidate seal mismatch")
    references = reference_values(identifier)
    prep = d.read(d.OUT / "prepared" / f"{identifier}.json")
    bundle, evaluator, _ = d.problem(identifier)
    reps = d.Representations(bundle, prep["mapping"], prep["scales"])
    destination = d.rear_dir(identifier, seed, front_mode, rear_mode)
    # Cache only exact identical binary points in this observation process.
    cache = {}
    def measure(p):
        key = json.dumps(p, separators=(",", ":"))
        if key not in cache:
            try:
                cache[key] = observe_point(evaluator, reps, d.unpacked(p), references)
            except TimeoutError:
                raise
            except Exception as exc:
                cache[key] = absent(type(exc).__name__ + ": " + str(exc)[:500])
        return cache[key]
    with d.mp.workdps(180), d.runtime_session(deadline):
        for i in range(8):
            saved = d.read(destination / f"{i}.json")
            result = {"id": identifier, "seed": seed, "start_index": i,
                      "front_mode": front_mode, "rear_mode": rear_mode, "utc": d.utc(),
                      "source_sha256": d.sha(destination / f"{i}.json"),
                      "input": absent("missing"), "final": absent("missing"), "observations": []}
            if not saved["missing"]:
                try:
                    input_snapshot = next(s for s in saved["snapshots"] if s["label"] == "input")
                    result["input"] = measure(input_snapshot["point"])
                    if saved["candidates"]:
                        result["final"] = measure(saved["candidates"][0]["x"])
                    for snapshot in saved["snapshots"]:
                        result["observations"].append({"label": snapshot["label"],
                             "elapsed_seconds": snapshot["elapsed_seconds"], "dps": snapshot["dps"],
                             "metric": measure(snapshot["point"])})
                except TimeoutError:
                    result["observation_timeout"] = True
                except Exception as exc:
                    result["observation_error"] = type(exc).__name__ + ": " + str(exc)[:500]
            result["target_digit_gain"] = result["final"]["target_digits"] - result["input"]["target_digits"]
            for threshold in (50, 80):
                hits = [s["elapsed_seconds"] for s in result["observations"] if s["metric"][f"R{threshold}"]]
                result[f"first_{threshold}_digits_saved_time_upper_bound"] = min(hits) if hits else None
            d.save(destination / f"measurement-{i}.json", result)


def choose_order_root(identifier):
    found = []
    for seed in d.SEEDS:
        for f, r in (("A", "A"), ("A", "B"), ("B", "A"), ("B", "B")):
            path = d.rear_dir(identifier, seed, f, r) / "phase-c.json"
            if not path.exists():
                continue
            for item in d.read(path)["verified_candidates"]:
                found.append(((seed, f + "->" + r, item["start_index"]), path, item["candidate"]))
    return min(found, key=lambda v: v[0]) if found else None


def order_job(identifier):
    start = time.monotonic()
    root = choose_order_root(identifier)
    result = {"id": identifier, "utc": d.utc(), "status": "NA", "new_solves": 0}
    if root is None:
        result["reason"] = "no originally verified saved point in normal four arms"
        d.save(d.OUT / "orders" / f"{identifier}.json", result)
        return result
    key, path, candidate = root
    prep = d.read(d.OUT / "prepared" / f"{identifier}.json")
    bundle, evaluator, _ = d.problem(identifier)
    reps = d.Representations(bundle, prep["mapping"], prep["scales"])
    point = d.unpacked(candidate["x"])
    records = []
    with d.mp.workdps(180), d.runtime_session(start + 10):
        try:
            for direction_index in range(3):
                v = [2 * d.uniform(f"Q39-order-v1|{identifier}|{direction_index}|{j}") - 1
                     for j in range(len(point))]
                v = [d.mp.mpf(x) for x in v]
                norm = d.mp.sqrt(d.mp.fsum(x*x for x in v))
                direction = [x / norm for x in v] if norm else [d.mp.mpf(j == 0) for j in range(len(v))]
                for sign in (-1, 1):
                    for power in range(-2, -9, -1):
                        eps = sign * d.mp.power(10, power)
                        shifted = [x + eps * delta * (d.mp.mpf(hi) - d.mp.mpf(lo))
                                   for x, delta, (lo, hi) in zip(point, direction, prep["bounds"], strict=True)]
                        with d.high_precision_mode():
                            a = evaluator.evaluate_hp_residual(shifted, precision=180)
                            b, valid = reps.both(shifted, list(a.residual_vector), 180)
                            hard = evaluator.evaluate_hp_hard_feasibility(shifted, precision=180,
                                                                         include_margins=False)
                            guard, violations = evaluator.evaluate_guard(shifted)
                        aa, bb = reps.norms(a.residual_vector, b) if valid else ([], [])
                        def logs(values):
                            return [float(d.mp.log10(abs(x))) if d.mp.isfinite(x) and x else None for x in values]
                        records.append({"direction": direction_index, "sign": sign, "power": power,
                                        "A_log10_abs": logs(aa), "B_log10_norm": logs(bb),
                                        "B_valid": valid, "guard_ok": guard,
                                        "guard_violations": list(violations),
                                        "hard_feasible": bool(hard.hard_feasible)})
        except TimeoutError:
            result["timeout"] = True
        except Exception as exc:
            result["error"] = type(exc).__name__ + ": " + str(exc)[:1000]
    slopes = []
    for k, block in enumerate(prep["mapping"]["blocks"]):
        per_direction = []
        for direction in range(3):
            for sign in (-1, 1):
                seq = sorted((r for r in records if r["direction"] == direction and r["sign"] == sign),
                             key=lambda r: -r["power"])
                values = {}
                for mode, index in (("A", block["a"]), ("B", k)):
                    field = "A_log10_abs" if mode == "A" else "B_log10_norm"
                    s = []
                    if index is not None:
                        for a, b in zip(seq, seq[1:]):
                            if index < len(a[field]) and index < len(b[field]):
                                x, y = a[field][index], b[field][index]
                                if x is not None and y is not None:
                                    s.append((y - x) / (b["power"] - a["power"]))
                    values[mode] = s
                per_direction.append({"direction": direction, "sign": sign, "adjacent_slopes": values})
        av = [x for v in per_direction for x in v["adjacent_slopes"]["A"]]
        bv = [x for v in per_direction for x in v["adjacent_slopes"]["B"]]
        oa, ob = statistics.median(av) if av else None, statistics.median(bv) if bv else None
        slopes.append({"block": k, "kind": block["kind"], "a_row": block["a"],
                       "order_A_median": oa, "order_B_median": ob,
                       "quadratic_to_linear_compatible": bool(oa is not None and ob is not None
                                                              and 1.8 <= oa <= 2.2 and .8 <= ob <= 1.2),
                       "directions": per_direction})
    result.update(status="observed" if len(records) == 42 else "partial", root_key=list(key),
                  root_file=str(path.relative_to(d.OUT)), root_file_sha256=d.sha(path),
                  root_point=candidate["x"], observations=records, slopes=slopes,
                  elapsed_seconds=time.monotonic() - start)
    d.save(d.OUT / "orders" / f"{identifier}.json", result)
    return {"id": identifier, "status": result["status"], "elapsed": result["elapsed_seconds"]}


if __name__ == "__main__":
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE, (4_900_000, 4_900_000))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=["job", "order", "references"])
    p.add_argument("--id")
    p.add_argument("--seed", type=int)
    p.add_argument("--front")
    p.add_argument("--rear")
    p.add_argument("--deadline", type=float)
    args = p.parse_args()
    if args.command == "references":
        prepare_references()
    elif args.command == "job":
        measure_job(args.id, args.seed, args.front, args.rear, args.deadline)
    else:
        print(json.dumps(order_job(args.id)))
