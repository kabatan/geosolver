"""Re-evaluate every saved intervention endpoint with the ORIGINAL evaluator."""
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0,str(Path(__file__).resolve().parent))
import run as r


def audit_one(arg):
    p, case = arg
    bundle = r.bundle_for(case["dsl"])
    ev = r.build_ir_evaluator(bundle)
    bounds = r.infer_problem_bounds(bundle)
    cfg = r.ExternalPipelineConfig.production_baseline_tier(seed=0,total_time_budget_sec=180).search
    raw = json.loads((r.RAW/f"{p['id']}.json").read_text())
    assert raw["seed"] == 0
    endpoints = without_endpoint = 0
    failures = []
    for arm in ("treatment","placebo"):
        path = r.OUT/"checkpoints"/f"{p['id']}.{arm}.json"
        if p[arm] is None:
            assert not path.exists()
            continue
        data = json.loads(path.read_text())
        assert data["n_expected"] == len(raw["records"])
        assert data["complete"] == (len(data["records"])==len(raw["records"]))
        assert [z["k"] for z in data["records"]] == [z["k"] for z in raw["records"][:len(data["records"])]]
        for old in data["records"]:
            if "x" not in old:
                assert old["cls"] == "error"
                without_endpoint += 1
                continue
            cand = r.smb._build_candidate(
                evaluator=ev,config=cfg,bounds=bounds,values=r.np.asarray(old["x"]),
                origin_seed=0,family_code=r.smb._LM_FAMILY_CODE,origin_start_point_index=old["k"],
                telemetry=r.smb._SearchTelemetry())
            new = r.classify(cand,ev,raw["references"])
            if new["cls"] != old["cls"]:
                failures.append(dict(id=p["id"],arm=arm,k=old["k"],old=old["cls"],new=new["cls"]))
            for key in ("res","ans"):
                if new.get(key) is not None and old.get(key) is not None:
                    if not math.isclose(new[key],old[key],rel_tol=1e-12,abs_tol=1e-12):
                        failures.append(dict(id=p["id"],arm=arm,k=old["k"],field=key,old=old[key],new=new[key]))
            endpoints += 1
    return dict(id=p["id"],endpoints=endpoints,without_endpoint=without_endpoint,failures=failures)


def main():
    began = time.monotonic()
    plan = json.loads((r.OUT/"plan.json").read_text())
    settings = json.loads((r.OUT/"run-settings.json").read_text())
    assert settings["code_sha256"] == r.digest(r.OUT/"run.py")
    assert settings["plan_sha256"] == r.digest(r.OUT/"plan.json")
    for path,h in plan["inputs_sha256"].items():
        if path != "jssa/difficulty/probe_basins.py":
            assert r.digest(r.ROOT/path)==h,path
    cases = {c["id"]:c for c in map(json.loads,(r.ROOT/"benchmarks/cases.jsonl").open())}
    results = []
    with ProcessPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(audit_one,(p,cases[p["id"]])) for p in plan["problems"]]
        for f in as_completed(futures):
            results.append(f.result())
    rows = r.readcsv(r.OUT/"per-start.csv")
    problems = r.readcsv(r.OUT/"per-problem.csv")
    assert len(rows)==sum(p["n_original"] for p in plan["problems"])
    assert len({(p["id"],p["k"]) for p in rows})==len(rows)
    assert {p["id"] for p in problems}=={p["id"] for p in plan["problems"]}
    for p in problems:
        rr = [z for z in rows if z["id"]==p["id"]]
        assert len(rr)==int(p["n_starts"])
        for arm in ("original","treatment","placebo"):
            hits = sum(z[f"{arm}_cls"]=="hit" for z in rr)
            if p[f"p_{arm}"]:
                assert hits/len(rr)==float(p[f"p_{arm}"])
        rescued = [z for z in rr if z["rescued"]=="1"]
        assert len(rescued)==int(p["rescued"])
        for z in rescued:
            assert z["original_cls"]!="hit" and z["treatment_cls"]=="hit"
            assert z["coinc_source"]=="recomputed_HP_ghost_scan"
        assert sum(z["original_coinc"]!="" and float(z["original_coinc"])<1e-4 for z in rescued)==int(p["rescued_original_coinc_lt_1e4"])
    failures = [z for p in results for z in p["failures"]]
    result = dict(seconds=time.monotonic()-began,problems=len(problems),per_start_rows=len(rows),
                  endpoints_re_evaluated=sum(p["endpoints"] for p in results),
                  errors_without_endpoint=sum(p["without_endpoint"] for p in results),
                  failures=failures,workers=4)
    r.dump(r.OUT/"audit.json",result)
    print(json.dumps(result,ensure_ascii=False),flush=True)
    assert not failures,failures[:10]


if __name__ == "__main__":
    main()
