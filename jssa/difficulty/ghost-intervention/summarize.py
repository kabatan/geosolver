"""Score the fixed 58-problem target, preserving every missing observation."""
from __future__ import annotations
import csv
import ast
import hashlib
import json
import math
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from fractions import Fraction
from pathlib import Path
from statistics import median as exact_median

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import run as r


def writecsv(path, rows):
    keys = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def median(values):
    return float(r.np.median(values)) if values else None


def decision(lo, hi, threshold):
    if lo is None or hi is None:
        return "判定不能"
    threshold = Fraction(str(threshold))
    if lo >= threshold:
        return "成立"
    if hi < threshold:
        return "不成立"
    return "判定不能"


def original_coinc(p, case, raw, needed):
    """Exactly ghost_scan's hit-based exclusions and HP coordinate convention."""
    if not needed:
        return {}
    bundle = r.bundle_for(case["dsl"])
    names = sorted(r.point_names(case["dsl"]))
    coords = r.construction_coordinates(case["dsl"], names)
    figures = [r.hit_figure(coords, bundle.var_names, x["x"], names)
               for x in raw["records"] if x["cls"] == "hit"]
    hits = [f for f in figures if len(f) >= 2]
    always = set()
    for i, a in enumerate(names):
        for b in names[i+1:]:
            if hits and all(a in f and b in f and r.np.linalg.norm(f[a]-f[b]) <
                            1e-6*max(1.0,max(r.np.linalg.norm(v) for v in f.values())) for f in hits):
                always.add((a,b))
    result = {}
    for rec in raw["records"]:
        if rec["k"] not in needed:
            continue
        if "x" not in rec:
            result[rec["k"]] = None
            continue
        f = r.hit_figure(coords, bundle.var_names, rec["x"], names)
        if len(f) < 2:
            result[rec["k"]] = None
            continue
        ks = sorted(f)
        diam = max(r.np.linalg.norm(f[a]-f[b]) for a in ks for b in ks)
        best = math.inf
        for i, a in enumerate(ks):
            for b in ks[i+1:]:
                if (a,b) not in always:
                    best = min(best,float(r.np.linalg.norm(f[a]-f[b])))
        result[rec["k"]] = float(best/diam) if diam > 0 and math.isfinite(best) else 0.0
    return result


def main():
    began = time.monotonic()
    plan = json.loads((r.OUT / "plan.json").read_text())
    settings = json.loads((r.OUT / "run-settings.json").read_text())
    # Another authorized task may edit the case-file CLI of probe_basins while
    # this run's forked workers retain the originally imported helpers. Compare
    # every other AST node against the archived, hash-verified frozen source.
    concurrent_changes = []
    for path, expected in plan["inputs_sha256"].items():
        actual = r.digest(r.ROOT/path)
        if actual == expected:
            continue
        if path != "jssa/difficulty/probe_basins.py":
            raise RuntimeError(f"frozen input changed: {path}")
        frozen = (r.OUT/"probe-basins-at-freeze.py.txt").read_bytes()
        assert hashlib.sha256(frozen).hexdigest() == expected
        def relevant(source):
            tree = ast.parse(source)
            tree.body = [node for node in tree.body if not (
                isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and node.name in ("main","load_case"))]
            return ast.dump(tree,include_attributes=False)
        assert relevant(frozen) == relevant((r.ROOT/path).read_bytes()), "used helper AST changed"
        concurrent_changes.append(dict(path=path,frozen_sha256=expected,current_sha256=actual,
                                       validation="AST identical outside unused main/load_case"))
    assert settings["plan_sha256"] == r.digest(r.OUT/"plan.json")
    cases = {c["id"]: c for c in map(json.loads, (r.ROOT/"benchmarks/cases.jsonl").open())}
    old_coinc = {(z["id"],int(z["k"])): z["coinc"] for z in
                 r.readcsv(r.ROOT/"jssa/difficulty/ghost-1023/endpoints_v1.csv")}
    perstart, perproblem = [], []
    armseconds = 0.0
    rescued_total = rescued_collapsed = rescued_unknown = rescue_unobserved = 0
    counts = {a: Counter() for a in ("original","treatment","placebo")}
    for p in plan["problems"]:
        cid = p["id"]
        raw = json.loads((r.RAW/f"{cid}.json").read_text())
        n = len(raw["records"])
        original_hits = sum(x["cls"]=="hit" for x in raw["records"])
        base = original_hits/n
        assert base == raw["p_any"]
        pp = dict(id=cid, problem_index=p["problem_index"], n_vars=p["n_vars"],
                  n_starts=n, original_hits=original_hits, p_original=base,
                  L=p["L"], epsilon=r.EPSILON, weight=r.WEIGHT,
                  n_found_before_safety=p["n_found_before_safety"],
                  n_treatment_pairs=len(p["treatment"]), n_placebo_pool=len(p["placebo_pool"]),
                  placebo_selection_status=p["placebo_status"])
        results = {}
        for arm in ("treatment","placebo"):
            path = r.OUT/"checkpoints"/f"{cid}.{arm}.json"
            data = json.loads(path.read_text()) if path.exists() else None
            if p[arm] is not None:
                assert data is not None, (cid,arm,"missing checkpoint")
            else:
                assert data is None
            recs = {x["k"]:x for x in data["records"]} if data else {}
            assert set(recs) <= {x["k"] for x in raw["records"]}
            hits = sum(x["cls"]=="hit" for x in recs.values())
            missing = n-len(recs)
            complete = missing == 0
            lo, hi = hits/n, (hits+missing)/n
            pp.update({f"{arm}_status": "complete" if complete else
                       ("deadline_incomplete" if data else p["placebo_status"]),
                       f"{arm}_n_done":len(recs), f"{arm}_n_missing":missing,
                       f"{arm}_hits":hits if data else "",
                       f"p_{arm}":hits/n if complete else "",
                       f"p_{arm}_lower":lo, f"p_{arm}_upper":hi,
                       f"delta_{arm}":hits/n-base if complete else "",
                       f"delta_{arm}_lower":lo-base, f"delta_{arm}_upper":hi-base,
                       f"{arm}_seconds":data["total_seconds"] if data else "",
                       f"{arm}_nonfinite_penalty_calls":data["nonfinite_penalty_calls"] if data else ""})
            if data:
                armseconds += data["total_seconds"]
            results[arm] = recs
        rescued = {x["k"] for x in raw["records"] if x["cls"]!="hit" and
                   results["treatment"].get(x["k"],{}).get("cls")=="hit"}
        cc = original_coinc(p,cases[cid],raw,rescued)
        collapsed = sum(cc[k] is not None and cc[k] < 1e-4 for k in rescued)
        unknown = sum(cc[k] is None for k in rescued)
        unobserved = sum(x["cls"]!="hit" and x["k"] not in results["treatment"] for x in raw["records"])
        rescued_total += len(rescued)
        rescued_collapsed += collapsed
        rescued_unknown += unknown
        rescue_unobserved += unobserved
        pp.update(rescued=len(rescued), rescued_original_coinc_lt_1e4=collapsed,
                  rescued_coinc_missing=unknown, unobserved_possible_rescues=unobserved)
        for old in raw["records"]:
            k = old["k"]
            row = dict(id=cid,k=k,start=json.dumps(old["start"],separators=(",",":")),
                       original_cls=old["cls"],original_hit=int(old["cls"]=="hit"),
                       original_x=json.dumps(old.get("x"),separators=(",",":")),
                       original_res=old.get("res",""),
                       original_coinc=cc[k] if k in cc and cc[k] is not None else old_coinc.get((cid,k),""),
                       coinc_source="recomputed_HP_ghost_scan" if k in cc else "endpoints_v1_rounded_or_missing",
                       rescued=int(k in rescued))
            counts["original"][old["cls"]] += 1
            for arm in ("treatment","placebo"):
                z = results[arm].get(k)
                cls = z["cls"] if z else ("not_run_deadline" if p[arm] is not None else "missing_placebo_pairs")
                counts[arm][cls] += 1
                row.update({f"{arm}_cls":cls, f"{arm}_hit":int(cls=="hit") if z else "",
                            f"{arm}_x":json.dumps(z.get("x"),separators=(",",":")) if z else "",
                            f"{arm}_res":z.get("res","") if z else "",
                            f"{arm}_ans":z.get("ans","") if z else "",
                            f"{arm}_sec":z["sec"] if z else "",
                            f"{arm}_nfev":z["nfev"] if z else "",
                            f"{arm}_err":z.get("err","") if z else ""})
            perstart.append(row)
        perproblem.append(pp)
        print(f"SCORE {len(perproblem)}/58 {cid} rescued={len(rescued)} collapsed={collapsed}",flush=True)
    writecsv(r.OUT/"per-start.csv",perstart)
    writecsv(r.OUT/"per-problem.csv",perproblem)
    # All comparisons use integer counts and exact rational arithmetic so that
    # e.g. exactly 0.10 is never rejected due to binary64 subtraction error.
    def delta_median(arm, upper=False):
        values = []
        for p in perproblem:
            hits = p[f"{arm}_hits"] or 0
            extra = p[f"{arm}_n_missing"] if upper else 0
            values.append(Fraction(hits+extra-p["original_hits"],p["n_starts"]))
        return exact_median(values)
    tlo, thi = delta_median("treatment"), delta_median("treatment",True)
    plo, phi = delta_median("placebo"), delta_median("placebo",True)
    b2lo, b2hi = tlo-phi, thi-plo
    # Conservative B3 bounds: any not-run original nonhit might be rescued,
    # with or without original coincidence. Do not drop these starts.
    denom = rescued_total+rescue_unobserved
    b3lo = Fraction(rescued_collapsed,denom) if denom else None
    b3hi = Fraction(rescued_collapsed+rescued_unknown+rescue_unobserved,denom) if denom else None
    b3point = rescued_collapsed/rescued_total if rescued_total and not rescued_unknown and not rescue_unobserved else None
    t_complete = [p["delta_treatment"] for p in perproblem if p["treatment_status"]=="complete"]
    p_complete = [p["delta_placebo"] for p in perproblem if p["placebo_status"]=="complete"]
    summary = dict(target_problems=58, original_starts=len(perstart),
                   treatment_complete_problems=len(t_complete), placebo_complete_problems=len(p_complete),
                   insufficient_placebo_problems=[p["id"] for p in plan["problems"] if p["placebo"] is None],
                   zero_treatment_problems=[p["id"] for p in plan["problems"] if not p["treatment"]],
                   counts={a:dict(c) for a,c in counts.items()}, arm_seconds_sum=armseconds,
                   B1=dict(threshold=0.10, lower=float(tlo),upper=float(thi),
                           exact_bounds=[str(tlo),str(thi)],decision=decision(tlo,thi,0.10)),
                   B2=dict(threshold=0.08,lower=float(b2lo),upper=float(b2hi),
                           exact_bounds=[str(b2lo),str(b2hi)],decision=decision(b2lo,b2hi,0.08),
                           treatment_median_range=[float(tlo),float(thi)],placebo_median_range=[float(plo),float(phi)]),
                   B3=dict(threshold=0.50,lower=float(b3lo) if b3lo is not None else None,
                           upper=float(b3hi) if b3hi is not None else None,point=b3point,
                           exact_bounds=[str(b3lo),str(b3hi)],
                           decision=decision(b3lo,b3hi,0.50),rescued=rescued_total,
                           rescued_original_coinc_lt_1e4=rescued_collapsed,
                           rescued_coinc_missing=rescued_unknown,unobserved_possible_rescues=rescue_unobserved),
                   descriptive_complete_case_only=dict(treatment_median=median(t_complete),
                                                       placebo_median=median(p_complete)),
                   concurrent_changes=concurrent_changes,
                   scoring_seconds=time.monotonic()-began, scored_at=datetime.now(UTC).isoformat())
    r.dump(r.OUT/"summary.json",summary)
    def fmt(z):
        return "欠測" if z is None else f"{z:.6f}"
    score = "# 事前登録 B の判定\n\n"
    score += (f"対象は固定58問、元の保存済み出発点{len(perstart):,}個。"
              f"全出発点の完了は treatment {len(t_complete)}/58問、placebo {len(p_complete)}/58問。\n\n")
    score += "| 基準 | 固定対象全体の値または保証範囲 | 閾値 | 判定 |\n|---|---:|---:|---|\n"
    for name in ("B1","B2","B3"):
        z = summary[name]
        value = fmt(z["lower"]) if z["lower"]==z["upper"] else f"[{fmt(z['lower'])}, {fmt(z['upper'])}]"
        score += f"| {name} | {value} | ≥ {z['threshold']:.2f} | {z['decision']} |\n"
    score += ("\nB1 は問題ごとの treatment 改善の中央値。B2 は treatment 改善の中央値から"
              "placebo 改善の中央値を引いた値。B3 は救済された出発点全体の元の coinc<1e-4 の割合。"
              "coinc は救済例について ghost_scan と同じ座標評価・常時一致除外で丸め前から再計算した。\n\n")
    score += (f"観測済みの救済は{rescued_total}個、そのうち元の終点が coinc<1e-4 は"
              f"{rescued_collapsed}個、coinc欠測{rescued_unknown}個。未完了のため救済されたか"
              f"不明な元の非hit出発点は{rescue_unobserved}個。\n\n")
    score += ("欠測は成功・失敗に置換せず、対象58問に残した。各未完了startのhitを0/1の両極端に"
              "置いて問題ごとのpの下限・上限を求め、中央値の単調性からB1/B2の範囲を求めた。"
              "B3も未観測の救済と元のcoinc欠測を保守的に含む範囲とした。"
              "範囲全体が閾値未満なら不成立、範囲全体が閾値以上なら成立、それ以外は判定不能。"
              "欠測の値を推定した点推定ではない。\n\n")
    if summary["B2"]["decision"] != "成立":
        score += "**B2 を満たしたとは言えないため、退化解が当たり外れの原因だとは主張しない。**\n\n"
    else:
        score += "B2 は保証範囲でも成立。ただし欠測と以下の実行上の制限を伴う。\n\n"
    score += (f"完全ケースだけの補助記述：treatment改善中央値{fmt(median(t_complete))}"
              f"（{len(t_complete)}問）、placebo改善中央値{fmt(median(p_complete))}"
              f"（{len(p_complete)}問）。これらの値で固定58問の基準を置き換えていない。\n\n")
    score += "同数の安全な found=0 点対がなく placebo を構成できなかった問題：\n\n"
    for cid in summary["insufficient_placebo_problems"]:
        p = next(z for z in plan["problems"] if z["id"]==cid)
        score += f"- {cid}：必要{len(p['treatment'])}組、候補{len(p['placebo_pool'])}組。\n"
    score += "\n全実行条件・限界は README.md、結果を見る前の扱いは protocol.md、個別値は両CSVに記載。\n"
    (r.OUT/"score.md").write_text(score)
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__ == "__main__":
    main()
