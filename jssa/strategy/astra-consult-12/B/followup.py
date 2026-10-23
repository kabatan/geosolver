"""Post-result replication on new starts, plus threshold sensitivity audit."""
from __future__ import annotations
import csv
import json
import math
import time
from collections import Counter

import numpy as np
from scipy.stats import binomtest

from experiment import (OUT, all_cases, answer_float, context, dump, norm,
                        reference_values, solve, vector_function)


def replicate():
    cases = all_cases()
    selected = {r["id"]: r for r in json.loads((OUT / "selected.json").read_text())}
    result_dir = OUT / "replication"
    result_dir.mkdir(exist_ok=True)
    summaries = []
    for cid in ("AIME-2023-I-12", "HMMT-2024-FEB-GEO-04"):
        sel = selected[cid]
        path = result_dir / f"{cid}.json"
        if not path.exists():
            b, ev, box = context(cases[cid])
            refs = reference_values(cases[cid]["answer"])
            rng = np.random.default_rng([102317, sel["index"]])
            rows = []
            started = time.monotonic()
            for k in range(100):
                start = box[:, 0] + rng.random(len(box)) * (box[:, 1]-box[:, 0])
                row = {"k": k, "start": start}
                for mode in ("base", "sharpen", "flatten", "scale10"):
                    row[mode] = solve(b, ev, box, refs, start, sel["a"], mode, 320, k)
                rows.append(row)
                if (k+1) % 20 == 0:
                    print(cid, k+1, {m:sum(r[m]["cls"] == "hit" for r in rows) for m in ("base", "sharpen", "flatten", "scale10")}, flush=True)
            dump(path, dict(sel, seed=102317, rows=rows, elapsed=time.monotonic()-started))
        d = json.loads(path.read_text())
        base = np.array([r["base"]["cls"] == "hit" for r in d["rows"]])
        for mode in ("base", "sharpen", "flatten", "scale10"):
            hit = np.array([r[mode]["cls"] == "hit" for r in d["rows"]])
            diff = hit.astype(float)-base.astype(float)
            gain, loss = int((hit & ~base).sum()), int((base & ~hit).sum())
            rng = np.random.default_rng(102318)
            boot = [float(np.mean(diff[rng.integers(0, len(diff), len(diff))])) for _ in range(5000)]
            summaries.append({"id": cid, "mode": mode, "n": len(hit), "hits": int(hit.sum()),
                              "p": float(hit.mean()), "delta_p": float(diff.mean()),
                              "delta_ci95": np.quantile(boot, [.025, .975]).tolist(),
                              "gain": gain, "loss": loss,
                              "mcnemar_p": binomtest(gain, gain+loss, .5).pvalue if gain+loss else 1,
                              "classes": dict(Counter(r[mode]["cls"] for r in d["rows"])),
                              "median_evaluations": float(np.median([r[mode]["evaluations"] for r in d["rows"]])),
                              "elapsed_problem": d["elapsed"]})
    dump(OUT / "replication-summary.json", summaries)
    print(json.dumps(summaries, ensure_ascii=False, indent=2), flush=True)


def threshold_audit():
    cases = all_cases()
    summary = []
    details = []
    for path in sorted((OUT / "interventions").glob("*.json")):
        d = json.loads(path.read_text())
        cid = d["id"]
        b, ev, box = context(cases[cid])
        refs = reference_values(cases[cid]["answer"])
        counts = {(mode, tol): 0 for mode in ("base", "sharpen", "flatten") for tol in (1e-8, 1e-6, 1e-4)}
        for row in d["rows"]:
            for mode in ("base", "sharpen", "flatten"):
                rec = row[mode]["320"]
                res = rec.get("res")
                feasible = bool(rec.get("guard_ok")) and bool(rec.get("hard_feasible")) and "out_of_bounds" not in rec.get("hard_tags", [])
                value = None
                if feasible and res is not None and res <= 1e-4:
                    value = answer_float(ev, rec["x"])
                answer_ok = value is not None and any(abs(value-ref) <= 1e-6*max(1., abs(ref)) for ref in refs)
                for tol in (1e-8, 1e-6, 1e-4):
                    hit = bool(feasible and res is not None and res <= tol and answer_ok)
                    counts[mode, tol] += int(hit)
                    if tol == 1e-8:
                        assert hit == (rec["cls"] == "hit"), (cid, row["k"], mode)
                if feasible and res is not None and 1e-8 < res <= 1e-4:
                    details.append({"id":cid,"k":row["k"],"mode":mode,"res":res,"answer":value,"answer_ok":answer_ok})
        for (mode, tol), hits in counts.items():
            summary.append({"id":cid,"mode":mode,"residual_tolerance":tol,"hits":hits,"n":len(d["rows"]),"p":hits/len(d["rows"])})
    with (OUT / "threshold-sensitivity.csv").open("w") as f:
        w=csv.DictWriter(f,fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)
    dump(OUT / "threshold-changed-endpoints.json", details)


def stalled_point_diagnostics():
    cases = all_cases()
    diagnostics = []
    for cid in ("AIME-2023-I-12", "HMMT-2024-FEB-GEO-04"):
        d = json.loads((OUT / "interventions" / f"{cid}.json").read_text())
        b, ev, box = context(cases[cid])
        fn, tel = vector_function(b, ev)
        for row in d["rows"]:
            base, sharp = row["base"]["320"], row["sharpen"]["320"]
            if base["cls"] == "hit" or sharp["cls"] != "hit":
                continue
            x = np.array(base["x"])
            r = fn(x)
            gradients = []
            for rel_h in (1e-4, 1e-5, 1e-6):
                cols=[]
                for j in range(len(x)):
                    h = rel_h*max(1., abs(x[j]))
                    xp,xm=x.copy(),x.copy()
                    xp[j]+=h;xm[j]-=h
                    cols.append((fn(xp)-fn(xm))/(2*h))
                J=np.column_stack(cols)
                gradients.append({"relative_step":rel_h,"gradient":(J.T@r).tolist(),"gradient_norm":norm(J.T@r)})
            diagnostics.append({"id":cid,"k":row["k"],"start":row["start"],"base_x":x.tolist(),
                                "base_stop":base["message"],"base_res":base["res"],
                                "base_aug_res":base["augmented_residual_norm"],
                                "base_penalties":base["guard_hard_penalties"],
                                "sharpen_x":sharp["x"],"sharpen_res":sharp["res"],
                                "gradients":gradients})
    dump(OUT / "stalled-point-diagnostics.json", diagnostics)


if __name__ == "__main__":
    replicate()
    threshold_audit()
    stalled_point_diagnostics()
