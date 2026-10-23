"""Independent numerical checks of residual wrapping and original scoring."""
import json
import math
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as r


def main():
    began = time.monotonic()
    plan = json.loads((r.OUT / "plan.json").read_text())
    r.check_inputs(plan)
    cases = {c["id"]: c for c in map(json.loads, (r.ROOT / "benchmarks/cases.jsonl").open())}
    hit_checks = residual_checks = replay_checks = witness_checks = 0
    max_distance_error = 0.0
    for p in plan["problems"]:
        case = cases[p["id"]]
        raw = json.loads((r.RAW / f"{p['id']}.json").read_text())
        bundle = r.bundle_for(case["dsl"])
        ev = r.build_ir_evaluator(bundle)
        for arm in ("treatment", "placebo"):
            if p[arm] is None:
                continue
            penalty = r.PairPenalty(bundle, case["dsl"], p[arm], p["threshold"])
            for rec in raw["records"]:
                if rec["cls"] == "hit":
                    v = penalty(rec["x"])
                    assert r.np.array_equal(v, r.np.zeros(len(p[arm]))), (p["id"], arm, rec["k"], v)
                    hit_checks += 1
            if p[arm]:
                names = sorted({n for pair in p[arm] for n in pair})
                coords = r.construction_coordinates(case["dsl"], names)
                # Compare the simultaneous float coordinates with the original
                # construction_coordinates high-precision target evaluation.
                rec = next(z for z in raw["records"] if z["cls"] == "hit")
                f = r.hit_figure(coords, bundle.var_names, rec["x"], names)
                xx = r.np.asarray(penalty.ev.evaluate_float_residual(rec["x"]).residual_vector).reshape(-1, 2)
                for i, n in enumerate(names):
                    err = float(r.np.max(r.np.abs(xx[i]-f[n])))
                    scale = max(1.0, float(r.np.max(r.np.abs(f[n]))))
                    assert err <= 1e-9*scale, (p["id"], n, err)
                    max_distance_error = max(max_distance_error, err/scale)
                residual_checks += 1
        # Empty wrapping must preserve the original residual vector exactly.
        empty = r.PairPenalty(bundle, case["dsl"], [], p["threshold"])
        x = r.np.asarray(raw["records"][0]["start"])
        kw = dict(bundle=bundle, evaluator=ev, values=x,
                  n_constraints=len(bundle.spec.constraints), telemetry=r.smb._SearchTelemetry())
        a = r.smb._evaluate_augmented_residual_vector(**kw)
        with r.extra_residuals(empty):
            b = r.smb._evaluate_augmented_residual_vector(**kw)
        assert r.np.array_equal(a, b, equal_nan=True)
    # Replay original starts without intervention, including failure and success.
    replay_mismatches = []
    for cid in ("AIME-2007-II-15", "AIME-2009-I-12", "HMMT-2006-FEB-GEO-03"):
        case = cases[cid]
        raw = json.loads((r.RAW / f"{cid}.json").read_text())
        bundle = r.bundle_for(case["dsl"])
        ev = r.build_ir_evaluator(bundle)
        for old in raw["records"][:3]:
            cand = r.smb._collect_local_start_record(
                bundle=bundle, evaluator=ev, bounds=r.infer_problem_bounds(bundle),
                config=r.ExternalPipelineConfig.production_baseline_tier(seed=0,total_time_budget_sec=180).search,
                seed=0, start_index=old["k"], start=r.np.asarray(old["start"]),
                deadline_monotonic=None, telemetry=r.smb._SearchTelemetry())
            rec = r.classify(cand, ev, raw["references"])
            if rec["cls"] != old["cls"] or not r.np.allclose(rec.get("x", []), old.get("x", []), rtol=1e-10, atol=1e-10):
                replay_mismatches.append(dict(id=cid,k=old["k"],old_cls=old["cls"],new_cls=rec["cls"]))
            replay_checks += 1
    # Check one sol-1 witness per treated problem activates at least one row.
    pairs = r.readcsv(r.ROOT / "jssa/difficulty/ghost-exact/per-pair.csv")
    for p in plan["problems"]:
        if not p["treatment"]:
            continue
        pq = p["treatment"][0]
        row = next(z for z in pairs if z["id"]==p["id"] and [z["P"],z["Q"]]==pq)
        if not row.get("best_x"):
            continue
        case = cases[p["id"]]
        penalty = r.PairPenalty(r.bundle_for(case["dsl"]),case["dsl"],[pq],p["threshold"])
        v = penalty(json.loads(row["best_x"]))
        assert v[0] > 0.99, (p["id"], pq, v)
        witness_checks += 1
    result = dict(seconds=time.monotonic()-began, zero_penalty_hit_checks=hit_checks,
                  coordinate_comparisons=residual_checks, max_relative_coordinate_error=max_distance_error,
                  empty_wrapper_checks=len(plan["problems"]), baseline_replays=replay_checks,
                  baseline_replay_mismatches=replay_mismatches, active_witness_checks=witness_checks)
    r.dump(r.OUT / "verification.json", result)
    print(json.dumps(result, ensure_ascii=False), flush=True)
    assert not replay_mismatches, replay_mismatches


if __name__ == "__main__":
    main()
