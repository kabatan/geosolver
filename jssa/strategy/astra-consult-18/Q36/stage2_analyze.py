"""Grade only the preregistered new Q36 seeds; no solver calls or old-run pooling."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import io
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT), str(HERE)]
from stage2 import OUT, read, save, sha, now, LIMIT
from analyze import wilson, iid_missing

MAIN = {"AIME-2007-I-15": 0, "HMMT-2013-FEB-GEO-04": 1}
CONTROLS = ["HMMT-2009-FEB-GEO-07", "HMMT-2011-FEB-ALGGEO-18", "HMMT-2019-FEB-GEO-05"]
QCASES = set(MAIN) | set(CONTROLS)


def proportion(h, n):
    lo, hi = wilson(h, n)
    return {"count": h, "denominator": n, "proportion": h/n if n else None,
            "wilson95_low": lo, "wilson95_high": hi}


def emit_csv(name, rows):
    stream = io.StringIO(newline="")
    keys = list(dict.fromkeys(k for row in rows for k in row))
    writer = csv.DictWriter(stream, keys, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: json.dumps(v, ensure_ascii=False, separators=(",", ":")) if isinstance(v, (dict, list)) else v for k,v in row.items()})
    payload = stream.getvalue().encode()
    assert len(payload) <= LIMIT
    (OUT / name).write_bytes(payload)


def outcome(ok, enough=True):
    return "測定不足" if not enough else ("的中" if ok else "外れ")


def exact_binomial(R, C):
    n = R+C
    return sum(math.comb(n, k) for k in range(R, n+1))/2**n if n else 1.0


def p1_result(cid, n, hits):
    total = sum(hits)
    p = [h/n for h in hits] if n else [None]*len(hits)
    q = [h/total for h in hits] if total else [None]*len(hits)
    pa = total/n if n else None
    enough = n >= 900 and (cid not in QCASES or total >= 100)
    if not enough:
        return "測定不足"
    rules = {
        "AIME-2007-I-15": lambda: .08 <= q[0] <= .20 and pa >= .80,
        "HMMT-2013-FEB-GEO-04": lambda: .05 <= q[1] <= .20 and pa >= .25,
        "HMMT-2009-FEB-GEO-07": lambda: .35 <= q[0] <= .65 and pa >= .80,
        "HMMT-2011-FEB-ALGGEO-18": lambda: .30 <= q[1] <= .70 and pa >= .80,
        "HMMT-2019-FEB-GEO-05": lambda: .20 < q[0] <= .45 and pa >= .90,
        "HMMT-2010-FEB-GEO-09": lambda: p[1] <= .01 and p[0] <= .03,
        "aime-2003-1-7": lambda: hits[2] == 0 and pa <= .10,
        "aime-2000-2-11": lambda: pa <= .02,
    }
    return outcome(rules[cid]())


def grade_set(task, references, expected_keys):
    from pydantic import TypeAdapter
    from geosolver.problem.models import ExactAnswer
    adapter = TypeAdapter(ExactAnswer)
    path = OUT / "full" / task["case_id"] / f"{task['seed']}.json"
    public = read(path) if path.exists() else None
    worker_path = path.with_suffix(".worker-final.json")
    worker = read(worker_path) if worker_path.exists() else None
    source, result = None, None
    if public and public.get("status") in {"solved", "no_answer_found"} and isinstance(public.get("answers"), list):
        source, result = "public_returned_set", public
    elif worker and worker.get("status") == "completed" and isinstance(worker.get("answers"), list):
        source, result = "saved_completed_worker_set", worker
    row = {**task, "status": public.get("status") if public else "missing_public_result",
           "termination_reason": public.get("termination_reason") if public else None,
           "set_source": source, "final_set_available": result is not None,
           "public_elapsed_seconds": public.get("elapsed_seconds") if public else None}
    expected = expected_keys[task["case_id"]]
    if result is None:
        return {**row, "answers": None, "per_value": ["unresolved"]*len(expected),
                "set_relation": "missing_data", "all_values_present": None, "equal": None,
                "extra": None, "empty": None, "unresolved_answers": None, "value_sources": []}
    actual, unresolved = [], []
    for i, answer in enumerate(result["answers"]):
        try:
            key = adapter.validate_python(answer).canonical_key()
            actual.append(json.dumps(key, ensure_ascii=False, separators=(",", ":")))
        except Exception as e:
            unresolved.append({"index": i, "error": type(e).__name__})
    actual = set(actual)
    per = ["present" if k in actual else ("unresolved" if unresolved else "absent") for k in expected]
    extra = sorted(actual-set(expected))
    missing = [i for i, flag in enumerate(per) if flag == "absent"]
    relation = "unresolved" if unresolved else ("extra_and_missing" if extra and missing else "extra" if extra else "missing" if missing else "equal")
    diag = result.get("diagnostics") or {}
    sources = diag.get("q36_value_sources", [])
    # If both public and completed worker sets exist, verify lossless transfer.
    if worker and source == "public_returned_set":
        assert public["answers"] == worker["answers"], (task, "worker/public answer mismatch")
    return {**row, "answers": result["answers"], "per_value": per, "set_relation": relation,
            "all_values_present": all(x=="present" for x in per), "equal": relation=="equal",
            "extra": extra, "empty": len(result["answers"])==0,
            "unresolved_answers": unresolved, "value_sources": sources}


def analyze():
    pf, tasks = read(OUT / "preflight.json"), read(OUT / "tasks.json")
    assert sha(OUT / "tasks.json") == pf["tasks_sha256"]
    assert sha(OUT / "grading/references.json") == pf["references_sha256"]
    ids = [x["case_id"] for x in pf["inputs"]]
    references = read(OUT / "grading/references.json")
    receipts = []
    for task in tasks:
        path = OUT/task["kind"]/task["case_id"]/f"{task['seed']}.end.json"
        assert path.exists(), f"unfinished planned job: {task}"
        r = read(path)
        for name, identity in r["artifacts"].items():
            assert sha(path.parent/name) == identity["sha256"], path.parent/name
        receipts.append(r)
    local_rows, local_jobs, locals_by_id = [], [], {}
    for cid in ids:
        rows = []
        for seed in range(36001, 36021):
            path = OUT/"local"/cid/f"{seed}.json"
            partial = path.with_suffix(".partial.json")
            d = read(path) if path.exists() else read(partial) if partial.exists() else {"records": []}
            records = d["records"]
            assert [r["k"] for r in records] == list(range(len(records)))
            assert len(records) <= 50
            rows.extend(records)
            local_jobs.append({"case_id":cid,"seed":seed,"completed_starts":len(records),
                "unfinished_starts":50-len(records), "end_reason":d.get("end_reason", "missing_data"),
                "complete_receipt":d.get("complete_receipt",False), "class_counts":dict(Counter(r["cls"] for r in records))})
        n = len(rows)
        hits = [sum(r["cls"]=="hit" and r.get("ref")==j for r in rows) for j in range(len(references[cid]["numeric"]))]
        total = sum(hits)
        assert total == sum(r["cls"]=="hit" for r in rows)
        for j, h in enumerate(hits):
            local_rows.append({"case_id":cid, "ref_index":j,"value":references[cid]["numeric"][j],
                "completed_starts":n,"hits_any":total,"value_hits":h,
                **{f"p_{k}":v for k,v in proportion(h,n).items()},
                **{f"q_{k}":v for k,v in proportion(h,total).items()}})
        locals_by_id[cid] = {"completed_starts":n,"unfinished_starts":1000-n,"hits":hits,
            "class_counts":dict(Counter(r["cls"] for r in rows)), "p_any":proportion(total,n),
            "p1":p1_result(cid,n,hits),
            "iid_missing_20_starts_plugin":iid_missing([h/n for h in hits],20) if n else None,
            "iid_missing_20_hits_plugin":iid_missing([h/total for h in hits],20) if total else None}
    from benchmarks.research_runner import reference_expressions
    from geosolver.exact import describe_exact
    expected = {}
    expressions = {}
    for cid, refs in references.items():
        values = refs["answer"] if isinstance(refs["answer"],list) else [refs["answer"]]
        expressions[cid] = [v for item in values for v in reference_expressions(str(item))]
        expected[cid] = [json.dumps(describe_exact(v).canonical_key(),ensure_ascii=False,separators=(",", ":")) for v in expressions[cid]]
        assert len(expected[cid]) == len(refs["numeric"])
    full_rows = [grade_set(t,references,expected) for t in tasks if t["kind"]=="full"]
    full_by_id, value_rows, sources_rows = {}, [], []
    for cid in ids:
        rs = [r for r in full_rows if r["case_id"]==cid]
        assert len(rs)==30
        resolved = [r for r in rs if r["final_set_available"] and "unresolved" not in r["per_value"] and not r["unresolved_answers"]]
        enough = len(resolved)==30
        n = len(resolved)
        count = lambda key: sum(bool(r[key]) for r in resolved)
        d = {"restored_resolved_sets":n,"missing_or_unresolved_sets":30-n,
            "all_values":proportion(count("all_values_present"),n), "equal":proportion(count("equal"),n),
            "extra":proportion(count("extra"),n),"empty":proportion(count("empty"),n),
            "statuses":dict(Counter(r["status"] for r in rs)),
            "saved_worker_set_used":sum(r["set_source"]=="saved_completed_worker_set" for r in rs)}
        for j, expr in enumerate(expressions[cid]):
            present = sum(r["per_value"][j]=="present" for r in rs)
            absent = sum(r["per_value"][j]=="absent" for r in rs)
            value_rows.append({"case_id":cid,"ref_index":j,"expression":expr,
                "unresolved":30-present-absent,
                **{f"present_{k}":v for k,v in proportion(present,present+absent).items()},
                **{f"absent_{k}":v for k,v in proportion(absent,present+absent).items()}})
        if cid in MAIN:
            j=MAIN[cid]
            R=sum(r["per_value"][j]=="absent" and r["per_value"][1-j]=="present" for r in resolved)
            C=sum(r["per_value"][j]=="present" and r["per_value"][1-j]=="absent" for r in resolved)
            Z=sum(all(x=="absent" for x in r["per_value"]) for r in resolved)
            d.update(R=proportion(R,n), C=proportion(C,n), Z=proportion(Z,n), R_minus_C=R-C,
                     one_sided_exact_p=exact_binomial(R,C), effect_prediction=outcome(R>=3 and R-C>=3 and Z<=3,enough),
                     statistical_support=enough and exact_binomial(R,C)<=.025)
            d["p2"]=d["effect_prediction"]
        elif cid in CONTROLS or cid=="aime-2003-1-7":
            d["p2"] = outcome(count("all_values_present")>=27,enough)
        elif cid=="aime-2000-2-11":
            d["p2"] = outcome(count("all_values_present")<=6,enough)
        else:
            absent70=sum(r["per_value"][0]=="absent" for r in resolved)
            absent160=sum(r["per_value"][1]=="absent" for r in resolved)
            d.update(absent70=proportion(absent70,n),absent160=proportion(absent160,n),
                     p2=outcome(absent160>=3 and absent160>=absent70,enough))
        full_by_id[cid]=d
        for r in rs:
            for source in r["value_sources"]:
                sources_rows.append({"case_id":cid,"seed":r["seed"],**source})
    geometry=[]
    for model in read(HERE/"geometry-model.json")["models"]:
        cid=model["case_id"]
        d=locals_by_id[cid]
        for j,count in enumerate(model["saved_start_cell_counts"]):
            g=count/model["saved_start_count"]
            q=proportion(d["hits"][j],sum(d["hits"]))
            enough=d["completed_starts"]>=900 and sum(d["hits"])>=100
            geometry.append({"case_id":cid,"ref_index":j,"g_fixed":g,"predicted_rare":g<=.2,
                **{f"q_{k}":v for k,v in q.items()},"p3":outcome((g<=.2)==(q["proportion"]<=.2) if q["proportion"] is not None else False,enough)})
    assert len(geometry)==10
    ctrl=locals_by_id["HMMT-2019-FEB-GEO-05"]
    q=ctrl["hits"][0]/sum(ctrl["hits"]) if sum(ctrl["hits"]) else None
    negative=outcome(abs(q-47/81)>=.15 if q is not None else False,ctrl["completed_starts"]>=900 and sum(ctrl["hits"])>=100)
    strong = all(locals_by_id[c]["p1"]=="的中" and full_by_id[c]["p2"]=="的中" and full_by_id[c]["statistical_support"] for c in MAIN) and all(full_by_id[c]["p2"]=="的中" for c in CONTROLS)
    summary={"analyzed_at_utc":now(),"new_data_only":True,"first_execution_utc":min(r["started_at_utc"] for r in receipts),
        "last_execution_utc":max(r["finished_at_utc"] for r in receipts),"local_jobs":160,"full_runs":240,
        "outer_timeouts":sum(r["outer_timeout"] for r in receipts),"nonzero_returncodes":sum(r["returncode"]!=0 for r in receipts),
        "local":locals_by_id,"full":full_by_id,"p3":outcome(all(r["p3"]=="的中" for r in geometry),all(r["p3"]!="測定不足" for r in geometry)),
        "p3_matches":sum(r["p3"]=="的中" for r in geometry),"negative_control":negative,"negative_control_q":q,
        "strong_support_for_solver_weakness":strong,"analyzer_sha256":sha(__file__),
        "binomial_intervals":"Wilson two-sided 95%; descriptive IID intervals, not guarantees under deadline censoring or solver dependence",
        "prediction_and_selection_unchanged":True}
    emit_csv("local-jobs.csv",local_jobs)
    emit_csv("local-values.csv",local_rows)
    emit_csv("full-runs.csv",full_rows)
    emit_csv("full-values.csv",value_rows)
    emit_csv("geometry-new.csv",geometry)
    if sources_rows:emit_csv("value-sources.csv",sources_rows)
    save(OUT/"results.json",summary,exclusive=False)
    print(json.dumps(summary,ensure_ascii=False))


def progress():
    tasks=read(OUT/"tasks.json")
    done=[]
    for task in tasks:
        path=OUT/task["kind"]/task["case_id"]/f"{task['seed']}.end.json"
        if path.exists():done.append(read(path))
    print(json.dumps({"at_utc":now(),"completed":dict(Counter(x["kind"] for x in done)),
        "nonzero_returncodes":sum(x["returncode"]!=0 for x in done),"outer_timeouts":sum(x["outer_timeout"] for x in done),
        "max_command_seconds":max((x["command_elapsed_seconds"] for x in done),default=0)},ensure_ascii=False))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--progress",action="store_true")
    args=parser.parse_args()
    progress() if args.progress else analyze()
