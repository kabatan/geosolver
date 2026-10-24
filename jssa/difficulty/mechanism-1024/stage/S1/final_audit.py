"""Read-only audit of S1 provenance, pairing, concurrency and fixed decisions."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from mpmath import mp

mp.dps = 750
OUT = Path(__file__).resolve().parent
M = json.loads((OUT / "pre-run-hashes.json").read_text())
ROOT = Path(M["scratch"])
checks = []


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


for path, expected in M["files"].items():
    assert sha(Path(path)) == expected, path
checks.append("original scripts, rules, preregistration, DSL corpus and prior experiment files unchanged")
for relative, expected in M["source_files"].items():
    assert sha(ROOT / relative) == expected, relative
    if relative.startswith("final/src/"):
        assert sha(Path(M["source_origin"]) / relative.removeprefix("final/src/")) == expected
    if relative.startswith("frozen/src/"):
        assert sha(Path(M["frozen_origin"]) / relative.removeprefix("frozen/src/")) == expected
checks.append("source copies and both provided original source trees unchanged")
repair = json.loads((OUT / "measurement-repair-hashes.json").read_text())
for path, expected in repair["files"].items():
    assert sha(Path(path)) == expected
checks.append("measurement serialization repair matches its pre-repair hashes")
reference_repair = json.loads((OUT / "reference-repair-hashes.json").read_text())
for path, expected in reference_repair["files"].items():
    assert sha(Path(path)) == expected
assert reference_repair["solver_reruns"] == 0
checks.append("reference-loading repair matches pre-repair hashes; original reference expressions and precision unchanged")

events = [json.loads(l) for l in (ROOT / "events.jsonl").read_text().splitlines()]
active = set()
peak = 0
counts = Counter()
for e in events:
    stage = e["stage"]
    if stage.endswith("_start") and "case_id" in e:
        key = (e["case_id"], stage.removesuffix("_start"), e["arm"])
        assert key not in active
        active.add(key)
        peak = max(peak, len(active))
        counts[key] += 1
        assert e["cpu"] in M["cpus"]
    if stage.endswith("_end"):
        key = (e["case_id"], stage.removesuffix("_end"), e["arm"])
        active.remove(key)
        assert e["returncode"] == 0, e
assert not active and peak <= 2
assert len([e for e in events if e["stage"] == "problem_done"]) == 12
checks.append(f"all stages exited 0, 12 problems completed, peak concurrent stages {peak}")

ps = list(csv.DictReader((OUT / "per-problem.csv").open()))
cs = list(csv.DictReader((OUT / "per-candidate.csv").open()))
assert len(ps) == 12 and len({p["case_id"] for p in ps}) == 12
independent = []
total_initial = 0
scale_fallbacks = {}
for task in M["inputs"]:
    case = task["case_id"]
    d = ROOT / "runs" / case
    initial = json.loads((d / "initial.json").read_text())
    scales = json.loads((d / "scales.json").read_text())
    assert initial["source_hash"] == M["source_hash"]
    assert len(initial["candidates"]) > 0
    fallback = [i for i, n in enumerate(scales["finite_counts"]) if n == 0]
    if fallback:
        assert all(mp.mpf(scales["scales"][i]) == 1 for i in fallback)
        scale_fallbacks[case] = fallback
    total_initial += len(initial["candidates"])
    assert counts[(case, "search", None)] == counts[(case, "scales", None)] == 1
    best = {}
    passes = {}
    for arm in ("BASE", "NO_RESIDUAL_REWRITE"):
        for stage in ("refine", "measure", "verify"):
            assert counts[(case, stage, arm)] == 1, (case, stage, arm)
        r = json.loads((d / (arm + ".refinement.json")).read_text())
        v = json.loads((d / (arm + ".verification.json")).read_text())
        mes = json.loads((d / (arm + ".measure.json")).read_text())
        assert r["initial_sha256"] == sha(d / "initial.pkl")
        assert r["scales_sha256"] == sha(d / "scales.json")
        assert r["source_hash"] == mes["source_hash"] == M["source_hash"]
        assert v["source_hash"] == M["frozen_source_hash"] and v["complete"]
        assert len(mes["rows"]) == len(v["rows"]) == r["returned"]
        assert (d / (arm + ".measure-serialization-error.json")).exists()
        assert len(mes["rows"]) > 0
        for x in mes["rows"]:
            assert "answer_error" not in x and "residual_error" not in x, (case, arm, x)
            err = mp.mpf(x["absolute_error"])
            expected = min(mp.mpf(600), -mp.log10(err)) if err else mp.mpf(600)
            assert abs(expected-mp.mpf(str(x["error_digits"]))) < mp.mpf("1e-10")
            assert x["p1_base_threshold"] == (err <= mp.mpf("1e-100"))
            assert x["p1_without_threshold"] == (err > mp.mpf("1e-60"))
        best[arm] = min(mes["rows"], key=lambda x: mp.mpf(x["absolute_error"]))
        passes[arm] = (any(x["immediate_pass"] for x in mes["rows"]), any(x["final_pass"] for x in v["rows"]))
        csvrows = [x for x in cs if x["case_id"] == case and x["arm"] == arm and x.get("absolute_error")]
        assert len(csvrows) == r["returned"]
    b, n = best["BASE"], best["NO_RESIDUAL_REWRITE"]
    independent.append({"p1_group": task["p1_group"],
        "p1": mp.mpf(b["absolute_error"]) <= mp.mpf("1e-100") and mp.mpf(n["absolute_error"]) > mp.mpf("1e-60"),
        "p2": abs(b["error_digits"]-n["error_digits"]) <= 20,
        "before": passes["BASE"][0] and not passes["NO_RESIDUAL_REWRITE"][0],
        "after": passes["BASE"][1] and not passes["NO_RESIDUAL_REWRITE"][1]})
checks.append(f"{total_initial} saved initial candidates paired across 24 arms; source hashes, shared scales, metrics and CSV rows verified")
j = json.loads((OUT / "judgments.json").read_text())
p1 = sum(x["p1"] for x in independent if x["p1_group"])
p2 = sum(x["p2"] for x in independent if not x["p1_group"])
before = sum(x["before"] for x in independent if x["p1_group"])
after = sum(x["after"] for x in independent if x["p1_group"])
assert (p1, p2, before, after) == (j["P1_met"], j["P2_met"], j["P3_before"], j["P3_after"])
assert j["judgments"] == {"P1": "当たり" if p1 >= 6 else "外れ", "P2": "当たり" if p2 == 5 else "外れ", "P3": "当たり" if after <= before else "外れ"}
assert not j["missing"] and not j["nonzero_stages"]
checks.append("P1/P2/P3 independently re-aggregated from high-precision saved measurements with fixed thresholds")
for p in OUT.rglob("*"):
    if p.is_file():
        assert p.stat().st_size <= 3_000_000
checks.append("no repository artifact exceeds 3,000,000 bytes")
print(json.dumps({"status": "ok", "audit_script_sha256": sha(Path(__file__)), "checks": checks,
    "P1_met": p1, "P2_met": p2, "P3_before": before, "P3_after": after,
    "scale_fallbacks_per_fixed_rules": scale_fallbacks}, ensure_ascii=False, indent=2))
