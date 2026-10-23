"""Q21c: read-only census of the fixed 323-problem development collection.

Run from anywhere with the prescribed Python; all outputs stay beside this file.
No solver calls, symbolic elimination, installations, or external writes.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
START = time.monotonic()
HASHES = {}


def read_bytes(rel):
    p = ROOT / rel
    b = p.read_bytes()
    HASHES[str(rel)] = {"sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b)}
    return b


def csv_rows(rel):
    return list(csv.DictReader(read_bytes(rel).decode().splitlines()))


def index(rows, key):
    ans = {r[key]: r for r in rows}
    assert len(ans) == len(rows), (key, "duplicate ids")
    return ans


def number(x, integer=False):
    if x is None or str(x).strip() in {"", "None", "nan"}:
        return None
    return int(x) if integer else float(x)


def med(values):
    x = [a for a in values if a is not None]
    return statistics.median(x) if x else None


def distribution(values):
    x = sorted(a for a in values if a is not None)
    if not x:
        return {"n": 0}
    def quantile(p):
        i = (len(x) - 1) * p
        j = int(i)
        return x[j] + (x[min(j + 1, len(x) - 1)] - x[j]) * (i - j)
    return {"n": len(x), "min": x[0], "q25": quantile(.25),
            "median": quantile(.5), "q75": quantile(.75),
            "q90": quantile(.9), "max": x[-1]}


def write_json(name, obj):
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(name, rows):
    if not rows:
        return
    with (OUT / name).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


basins = index(csv_rows("jssa/difficulty/minima/basins-323.csv"), "id")
human = index(csv_rows("jssa/difficulty/ghost-1023/human_feat.csv"), "case_id")
exact = index(csv_rows("jssa/strategy/astra-consult-17/H/sources/comparison-cases.csv"), "id")
cert = index([r for r in csv_rows("jssa/difficulty/certify-all/per-case.csv")
              if r["group"] == "development323"], "id")
cases = index([json.loads(x) for x in read_bytes("benchmarks/cases.jsonl").decode().splitlines() if x], "id")
assert len(basins) == 323
assert set(basins) == set(exact) == set(cert) == set(human), "population mismatch"
assert set(basins) <= set(cases)

# Freeze the human high-difficulty subgroup by the prewritten selection rule.
hard_ids = set()
cutoffs = {}
for contest in sorted({r["contest"] for r in human.values()}):
    eligible = [r for r in human.values() if r["contest"] == contest and number(r["human"]) is not None]
    eligible.sort(key=lambda r: (-number(r["human"]), r["case_id"]))
    take = math.ceil(len(eligible) / 4)
    hard_ids.update(r["case_id"] for r in eligible[:take])
    cutoffs[contest] = {"n": len(eligible), "n_top": take,
                        "threshold": number(eligible[take-1]["human"]) if take else None}

rows = []
audit = {"raw_mismatch": [], "variable_count_mismatch": [], "missing_raw": [],
         "human_exact_rating_mismatch": [], "exact_audit_A_available": 0}
for cid in sorted(basins):
    b, h, e, c = basins[cid], human[cid], exact[cid], cert[cid]
    dsl = cases[cid]["dsl"]
    d = len(dsl.get("variables", []))
    other_d = {"basins": number(b["n_vars"], True), "human": number(h["n_vars"], True),
               "exact": number(e["dsl_vars"], True)}
    if any(z != d for z in other_d.values()):
        audit["variable_count_mismatch"].append({"id": cid, "current_dsl": d, **other_d})
    path = f"jssa/difficulty/minima/raw-323/{cid}.json"
    n = hits = 0
    p = None
    if (ROOT / path).exists():
        raw = json.loads(read_bytes(path))
        rec = raw.get("records", [])
        n = len(rec)
        hits = sum(r.get("cls") == "hit" for r in rec)
        if d:
            p = hits / n if n else None
            if n != number(b["n_starts"], True) or p is None or abs(p-number(b["p"])) > 1e-12:
                audit["raw_mismatch"].append({"id": cid, "raw_n": n, "raw_p": p,
                                               "csv_n": b["n_starts"], "csv_p": b["p"]})
    else:
        audit["missing_raw"].append(cid)
    N, D = number(e["poly_vars"], True), number(e["max_degree"], True)
    cN, cD = number(c["variables"], True), number(c["max_degree"], True)
    known = N is not None and D is not None
    cknown = cN is not None and cD is not None
    ts = [number(e[k]) for k in ("translate_s", "msolve_s", "filter_s")]
    total = sum(ts) if all(v is not None for v in ts) else None
    score = number(h["human"])
    erating = number(e["e2h_rating"])
    if erating is not None and score is not None and abs(erating-score) > 1e-9:
        audit["human_exact_rating_mismatch"].append({"id": cid, "human": score, "exact": erating})
    audit["exact_audit_A_available"] += bool(e["audit_A"].strip())
    row = {
        "id": cid, "contest": h["contest"], "human": score,
        "human_top_quartile": cid in hard_ids,
        "d": d, "n_constructions": len(dsl.get("constructions", [])),
        "n_conditions": len(dsl.get("conditions", [])),
        "n_starts": n, "hits": hits, "p": p,
        "local_hard": p is not None and p <= .1,
        "local_easy": p is not None and p >= .9,
        "N": N, "m": number(e["poly_eqs"], True), "D": D,
        "bezout_product_recorded": number(e["bezout"], True),
        "real_solutions_recorded": number(e["real_solutions"], True),
        "verified_configurations_recorded": number(e["verified_configurations"], True),
        "small_explicit_proxy": N <= 4 and D <= 4 if known else None,
        "small_d_large_explicit_proxy": d <= 2 and (N >= 10 or D >= 8) if known else None,
        "msolve_class": e["msolve_class"],
        "translate_s": ts[0], "msolve_s": ts[1], "filter_s": ts[2],
        "exact_total_recorded_s": total,
        "exact_match_total_le1s": e["msolve_class"] == "answer_set_matches" and total is not None and total <= 1,
        "geo_runs": number(e["geo_runs"], True), "geo_matched": number(e["geo_matched"], True),
        "geo_median_s": number(e["geo_median_s"]),
        "geo_all_matched": number(e["geo_matched"], True) == number(e["geo_runs"], True),
        "cert_N": cN, "cert_D": cD, "cert_status": c["status"],
        "cert_small_explicit_proxy": cN <= 4 and cD <= 4 if cknown else None,
        "cert_small_d_large_explicit_proxy": d <= 2 and (cN >= 10 or cD >= 8) if cknown else None,
        "cert_zero_dimensional_recorded": c["zero_dimensional"],
        "audit_A": e["audit_A"],
    }
    rows.append(row)


def summarize(rs):
    n = len(rs)
    return {
        "n": n, "d_histogram": dict(sorted(Counter(r["d"] for r in rs).items())),
        "d_le2": sum(r["d"] <= 2 for r in rs),
        "p_measured_n": sum(r["p"] is not None for r in rs),
        "local_trials": sum(r["n_starts"] for r in rs), "local_hits": sum(r["hits"] for r in rs),
        "p_zero": sum(r["p"] == 0 for r in rs),
        "p_le01": sum(r["local_hard"] for r in rs),
        "p_ge09": sum(r["local_easy"] for r in rs),
        "p_distribution": distribution(r["p"] for r in rs),
        "N_distribution": distribution(r["N"] for r in rs),
        "D_distribution": distribution(r["D"] for r in rs),
        "small_explicit_proxy": sum(r["small_explicit_proxy"] is True for r in rs),
        "explicit_proxy_missing": sum(r["small_explicit_proxy"] is None for r in rs),
        "small_d_large_explicit_proxy": sum(r["small_d_large_explicit_proxy"] is True for r in rs),
        "cert_N_distribution": distribution(r["cert_N"] for r in rs),
        "cert_D_distribution": distribution(r["cert_D"] for r in rs),
        "cert_small_explicit_proxy": sum(r["cert_small_explicit_proxy"] is True for r in rs),
        "cert_explicit_proxy_missing": sum(r["cert_small_explicit_proxy"] is None for r in rs),
        "cert_small_d_large_explicit_proxy": sum(r["cert_small_d_large_explicit_proxy"] is True for r in rs),
        "msolve_status": dict(Counter(r["msolve_class"] for r in rs)),
        "exact_match_total_le1s": sum(r["exact_match_total_le1s"] for r in rs),
        "exact_match_total_known_n": sum(r["msolve_class"] == "answer_set_matches" and r["exact_total_recorded_s"] is not None for r in rs),
        "exact_matched_total_time_distribution": distribution(r["exact_total_recorded_s"] for r in rs if r["msolve_class"] == "answer_set_matches"),
        "geo_all_matched": sum(r["geo_all_matched"] for r in rs),
        "geo_matched_runs": sum(r["geo_matched"] for r in rs),
        "geo_total_runs": sum(r["geo_runs"] for r in rs),
        "geo_median_s_distribution": distribution(r["geo_median_s"] for r in rs),
    }


groups = {
    "all323": rows,
    "human_known": [r for r in rows if r["human"] is not None],
    "human_hard": [r for r in rows if r["human_top_quartile"]],
    "human_other": [r for r in rows if r["human"] is not None and not r["human_top_quartile"]],
    "d_le2": [r for r in rows if r["d"] <= 2],
    "small_explicit": [r for r in rows if r["small_explicit_proxy"] is True],
    "small_d_large_explicit": [r for r in rows if r["small_d_large_explicit_proxy"] is True],
    "local_hard": [r for r in rows if r["local_hard"]],
    "local_easy": [r for r in rows if r["local_easy"]],
    "exact_fast": [r for r in rows if r["exact_match_total_le1s"]],
}
for contest in ("AIME", "HMMT"):
    groups[f"human_hard_{contest}"] = [r for r in rows if r["human_top_quartile"] and r["contest"] == contest]
    groups[f"human_other_{contest}"] = [r for r in rows if r["human"] is not None and not r["human_top_quartile"] and r["contest"] == contest]
summaries = {k: summarize(rs) for k, rs in groups.items()}
write_csv("per-problem.csv", rows)
write_csv("human-hard.csv", groups["human_hard"])
write_csv("small-d-large-explicit.csv", groups["small_d_large_explicit"])
write_csv("local-hard-exact-fast.csv", [r for r in rows if r["local_hard"] and r["exact_match_total_le1s"]])
write_json("summary.json", {"selection": cutoffs, "groups": summaries, "audit": audit})
write_json("provenance.json", {"python": sys.executable, "python_version": sys.version,
    "elapsed_seconds": time.monotonic()-START,
    "source_hashes": HASHES,
    "code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    "analysis_plan_sha256": hashlib.sha256((OUT / "analysis-plan.md").read_bytes()).hexdigest(),
    "scope": "existing development data; no new solver or local-search calls"})
short = {k: {a: v for a, v in s.items() if a in ["n", "d_le2", "d_histogram", "p_measured_n", "p_zero", "p_le01", "p_ge09", "small_explicit_proxy", "explicit_proxy_missing", "small_d_large_explicit_proxy", "geo_all_matched", "msolve_status", "exact_match_total_le1s"]}
         for k, s in summaries.items()}
print(json.dumps({"selection": cutoffs, "groups": short, "audit": audit,
                  "elapsed_seconds": time.monotonic()-START}, ensure_ascii=False, indent=2))
