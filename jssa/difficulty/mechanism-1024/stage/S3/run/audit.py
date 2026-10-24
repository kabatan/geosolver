"""Read-only campaign audit followed by a small receipt and final raw hash list."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from mpmath import mp

OUT = Path(__file__).resolve().parent
M = json.loads((OUT / "pre-run-hashes.json").read_text())
ROOT = Path(M["scratch"])
checks = []


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


for collection in ("files", "source_files", "s1_saved_inputs"):
    for path, expected in M[collection].items():
        assert sha(Path(path)) == expected, path
checks.append("pre-fixed scripts, rules, preregistration, stage1 artifacts, sources, S1 saved inputs unchanged")
events = [json.loads(l) for l in (ROOT / "events.jsonl").read_text().splitlines()]
active, peak = set(), 0
started, ended = Counter(), Counter()
for e in events:
    stage = e["stage"]
    if stage.endswith("_start") and "case_id" in e:
        key = e["case_id"], stage[:-6], e.get("arm")
        assert key not in active
        active.add(key)
        peak = max(peak, len(active))
        started[key] += 1
    elif stage.endswith("_end") and "case_id" in e:
        key = e["case_id"], stage[:-4], e.get("arm")
        assert key in active
        active.remove(key)
        ended[key] += 1
assert not active and peak == 2
assert all(v == 1 for v in started.values()) and started == ended
assert sum(e["stage"] == "problem_done" for e in events) == 12
assert not any(e["stage"].startswith("search") for e in events)
checks.append("12 problems, peak 2 concurrent stages, no repeated stage, no new main search")
assert len([k for k in started if k[1] == "refine"]) == 36
bad = [e for e in events if e.get("returncode", 0) != 0]
paired = 0
for task in M["inputs"]:
    d = ROOT / "runs" / task["case_id"]
    assert sha(d / "initial.pkl") == task["initial_sha256"]
    assert sha(d / "scales.json") == task["scales_sha256"]
    assert sha(d / "input.json") == task["sha256"]
    paired += len(task["candidate_uids"])
    for arm in ("T0", "T1", "T2"):
        path = d / (arm + ".refinement.json")
        if path.exists():
            r = json.loads(path.read_text())
            assert r["initial_sha256"] == task["initial_sha256"]
            assert r["scales_sha256"] == task["scales_sha256"]
            assert r["source_hash"] == M["source_hash"]
            assert set(r["candidate_seconds"]) <= set(task["candidate_uids"])
        path = d / (arm + ".verification.json")
        if path.exists():
            v = json.loads(path.read_text())
            assert v["source_hash"] == M["frozen_source_hash"]
            assert v["complete"]
assert paired == 224
checks.append("224 S1 candidates, shared exact pickle/config/order and scales for T0/T1/T2; verifier source frozen")
mp.dps = 750
with (OUT / "per-problem.csv").open() as f:
    table = list(csv.DictReader(f))
for p in table:
    d = ROOT / "runs" / p["case_id"]
    for arm in ("T0", "T1", "T2"):
        path = d / (arm + ".measure.json")
        if not path.exists():
            continue
        rows = json.loads(path.read_text())["rows"]
        usable = [r for r in rows if r.get("absolute_error") is not None]
        if usable:
            best = min(usable, key=lambda r: mp.mpf(r["absolute_error"]))
            assert best["candidate_uid"] == p[arm+"_best_candidate_uid"]
            err = mp.mpf(best["absolute_error"])
            digits = min(mp.mpf(600), -mp.log10(err)) if err else mp.mpf(600)
            assert abs(digits-mp.mpf(p[arm+"_best_error_digits"])) < mp.mpf("1e-20")
checks.append("best candidate selection and CSV digits rechecked from high-precision absolute errors")
trace = ROOT / "runs" / M["trace_case"]
trace_counts = {}
for arm in ("T0", "T1", "T2"):
    path = trace / (arm+".iteration-errors.json")
    if path.exists():
        obj = json.loads(path.read_text())
        rows = obj["rows"]
        trace_counts[arm] = len(rows)
        if rows:
            final = [r for r in rows if r["phase"].startswith("final:")]
            assert len(final) == 1
            measured = json.loads((trace / (arm+".measure.json")).read_text())["rows"]
            best = next(r for r in measured if r["candidate_uid"] == obj["best_candidate_uid"])
            assert final[0]["absolute_error"] == best["absolute_error"]
checks.append("AIME trace best-candidate final point error matches pre-verification measurement")
for path in OUT.parent.rglob("*"):
    if path.is_file():
        assert path.stat().st_size <= 3_000_000, path
checks.append("all S3 repository files <= 3,000,000 bytes")
receipt = dict(status="ok" if not bad else "completed_with_missing_stages", checks=checks,
    nonzero_stages=bad, paired_initial_candidates=paired, trace_rows=trace_counts,
    peak_concurrent_stages=peak, audit_script_sha256=sha(Path(__file__)))
(OUT / "audit.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n")
(OUT / "raw-hashes.json").write_text(json.dumps({str(p.relative_to(ROOT)): dict(sha256=sha(p), bytes=p.stat().st_size)
    for p in sorted(ROOT.rglob("*")) if p.is_file()}, indent=2)+"\n")
with (OUT / "progress.md").open("a") as f:
    f.write("\n全12問・36条件の計測と集計を終了。最終監査: "+receipt["status"]+"。詳細はanswer.mdとaudit.json。\n")
