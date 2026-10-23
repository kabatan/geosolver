"""Read-only data checks after run.py summarize; only audit.json is written."""
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
from collections import Counter

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
read = lambda p: json.loads(p.read_text())
manifest = read(OUT / "manifest.json")
metrics = read(OUT / "metrics.json")
preflight = read(OUT / "preflight.json")
per_start = list(csv.DictReader((OUT / "per-start.csv").open()))
per_problem = list(csv.DictReader((OUT / "per-problem.csv").open()))
assert len(per_start) == 2560 and len(per_problem) == 40
assert len({(r["id"], r["start_index"]) for r in per_start}) == 2560
assert {r["id"] for r in per_problem} == {t["id"] for t in manifest["targets"]}
by_start = {(r["id"], int(r["start_index"])):r for r in per_start}
by_problem = {r["id"]:r for r in per_problem}
assert preflight["passed"]
assert hashlib.sha256((OUT / "manifest.json").read_bytes()).hexdigest() == preflight["manifest_sha256"]
for path, expected in manifest["inputs"].items():
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == expected, path

unknown = {"timeout", "error", "missing", "missing_answer"}
rescue_bad = rescue_count = 0
deltas = {"phi_lt_0.8":[], "phi_eq_1":[]}
status = {m:Counter() for m in ("base", "sharpen")}
unknown_counts = Counter()
hard_by_group = {g:Counter() for g in deltas}
for target in manifest["targets"]:
    cid = target["id"]
    raw = read(OUT / "raw" / f"{cid}.json")
    assert not raw.get("problem_error"), raw.get("problem_error")
    assert len(raw["rows"]) == 64
    hits = Counter()
    observed = Counter()
    for k, row in enumerate(raw["rows"]):
        csvrow = by_start[cid, k]
        assert row["k"] == k and row["start"] == target["starts"][k] == json.loads(csvrow["start"])
        initial = row.get("start_hard_feasible")
        assert csvrow["start_hard_feasible"] == ("" if initial is None else str(initial))
        hard_by_group[target["group"]][str(initial)] += 1
        for mode in ("base", "sharpen"):
            rec = row[mode]
            assert csvrow[mode+"_cls"] == rec["cls"]
            status[mode][str(rec["status"])] += 1
            if rec["cls"] in unknown:
                unknown_counts[mode+":"+rec["cls"]] += 1
            else:
                observed[mode] += 1
            if rec["cls"] == "hit":
                hits[mode] += 1
                assert rec["res"] is not None and rec["res"] <= 1e-8
                assert rec["guard_ok"] and rec["hard_feasible"]
                assert rec["answer"] is not None and math.isfinite(rec["answer"])
                assert all(lo <= x <= hi for x,(lo,hi) in zip(rec["x"], target["box"]))
            assert rec["cap"] == 320
        bb, ss = row["base"]["cls"], row["sharpen"]["cls"]
        rescued = None if bb in unknown or ss in unknown else (bb != "hit" and ss == "hit")
        assert csvrow["rescued"] == ("" if rescued is None else str(rescued))
        if rescued:
            rescue_count += 1
            rescue_bad += initial is False
    summary = by_problem[cid]
    for mode in ("base", "sharpen"):
        assert int(summary[mode+"_hits"]) == hits[mode]
        assert int(summary[mode+"_observed"]) == observed[mode]
    delta = (hits["sharpen"]-hits["base"])/64 if observed["base"] == observed["sharpen"] == 64 else None
    assert summary["delta_preregistered"] == ("" if delta is None else str(delta))
    deltas[target["group"]].append(delta)
for group, values in deltas.items():
    independent = statistics.median(values) if None not in values else None
    assert independent == metrics["medians"][group]
assert rescue_count == metrics["rescued"] and rescue_bad == metrics["rescued_start_hard_violated"]

for result in preflight["replications"]:
    cid = result["id"]
    replay = read(OUT / "replication" / f"{cid}.json")
    original = read(ROOT / "jssa/strategy/astra-consult-12/B/replication" / f"{cid}.json")
    for a,b in zip(replay["rows"], original["rows"], strict=True):
        assert a["start"] == b["start"]
        assert all(a[m]["cls"] == b[m]["cls"] for m in ("base", "sharpen"))

result = dict(passed=True, problems=40, starts=2560, condition_runs=5120,
              replay_condition_runs=400, source_hashes_match=True,
              statuses={m:dict(c) for m,c in status.items()}, unknown_counts=dict(unknown_counts),
              initial_hard_by_group={g:dict(c) for g,c in hard_by_group.items()},
              metrics_independently_recomputed=True)
(OUT / "audit.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
print(json.dumps(result, ensure_ascii=False, indent=2))
