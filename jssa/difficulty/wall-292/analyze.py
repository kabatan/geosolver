"""Aggregate completed/partial runs without changing preregistered criteria."""
from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, spearmanr

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ARMS = ("B", "N", "G2")


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, np.generic):
        return clean(x.item())
    if isinstance(x, float) and not math.isfinite(x):
        return None
    return x


def write_json(path, x):
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(clean(x), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    temp.replace(path)


def write_csv(path, rows):
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def divide(x, n):
    return x/n if n else None


def rho(x, y):
    if len(x) < 3 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    return float(spearmanr(x, y).statistic)


def partial(x, y, z):
    if len(x) < 4 or len(set(x)) < 2 or len(set(y)) < 2:
        return None
    xx, yy, zz = [rankdata(v) for v in (x, y, z)]
    D = np.column_stack([np.ones(len(zz)), zz])
    xx = xx - D @ np.linalg.lstsq(D, xx, rcond=None)[0]
    yy = yy - D @ np.linalg.lstsq(D, yy, rcond=None)[0]
    if np.std(xx) < 1e-12 or np.std(yy) < 1e-12:
        return None
    return float(np.corrcoef(xx, yy)[0, 1])


def average_ci(values):
    values = np.asarray(values, dtype=float)
    if not values.size:
        return {"mean": None, "ci95": [None, None]}
    rng = np.random.default_rng(2921023)
    means = np.mean(values[rng.integers(len(values), size=(10000, len(values)))], axis=1)
    return {"mean": float(values.mean()), "ci95": np.quantile(means, [.025, .975]).tolist()}


def collect(final):
    manifest = json.loads((HERE/"manifest.json").read_text())
    human = {r["case_id"]: float(r["human"]) for r in csv.DictReader(
        (ROOT/"jssa/difficulty/ghost-1023/human_feat.csv").open()) if r["human"]}
    independent_path = ROOT/"jssa/strategy/astra-consult-13/phi-independent.csv"
    independent_phi = ({r["id"]: float(r["phi"]) for r in csv.DictReader(independent_path.open())}
                       if independent_path.exists() else {})
    table, status_rows, error_rows, transition_rows, g2_rows = [], [], [], [], []
    totals = {a: Counter() for a in (*ARMS, "S")}
    status = Counter()
    transition = Counter()
    g2counts = Counter()
    audit = Counter()
    mechanisms = Counter()
    costs = defaultdict(list)
    evals = defaultdict(list)
    groups = defaultdict(Counter)
    mechanism_cases = defaultdict(Counter)
    actual = 0
    for meta in manifest["problems"]:
        cid = meta["id"]
        path = HERE/"records"/(cid+".jsonl")
        records = {}
        if path.exists():
            data = path.read_text()
            for line in data.splitlines(keepends=True):
                if not line.endswith("\n"):
                    audit["partial_last_line"] += 1
                    continue
                r = json.loads(line)
                assert r["k"] not in records, (cid, "duplicate", r["k"])
                records[r["k"]] = r
        actual += len(records)
        complete = len(records) == meta["n"]
        cs = HERE/"case-summary"/(cid+".json")
        case_error = json.loads(cs.read_text()).get("case_error") if cs.exists() else None
        if case_error:
            error_rows.append({"id": cid, "k": "", "arm": "all", "cls": "case_error", "detail": case_error})
            audit["case_error"] += 1
        selected = final or complete
        row = {"id": cid, "method": meta["method"], "n_vars": meta["n_vars"],
               "n_constraints": meta["n_constraints"], "n": meta["n"], "observed": len(records),
               "complete": complete, "risk": meta["risk"], "risk_reasons": "|".join(meta["risk_reasons"]),
               "human": human.get(cid), "diagnostic": sum(s["diagnostic"] for s in meta["starts"])}
        start_counts = Counter(str(s["F"]) for s in meta["starts"])
        row["nF"], row["nI"], row["nUnknown"] = (start_counts[str(k)] for k in (True, False, None))
        row["phi"] = divide(row["nF"], row["nF"]+row["nI"])
        row["phi_independent"] = independent_phi.get(cid)
        pc = {a: Counter() for a in ARMS}
        hits_FI = defaultdict(Counter)
        paired = Counter()
        pcg2 = Counter()
        for spec in meta["starts"]:
            k = spec["k"]
            r = records.get(k)
            if r is None:
                audit["unobserved_starts"] += 1
                if selected:
                    for a in ARMS:
                        pc[a]["missing_run"] += 1
                        totals[a]["missing_run"] += 1
                continue
            assert r["F"] == spec["F"] and r["diagnostic"] == spec["diagnostic"]
            for a in (*ARMS, "S"):
                if a not in r:
                    continue
                out = r[a]
                totals[a][out["cls"]] += 1
                if a in ARMS:
                    pc[a][out["cls"]] += 1
                    hits_FI[a][str(r["F"])] += out["cls"] == "hit"
                    groups[(meta["method"], str(r["F"]), a)][out["cls"]] += 1
                opt = out.get("optimizer", {})
                native = out.get("native", {})
                status[(meta["method"], a, str(opt.get("status")), str(native.get("raw_info")), out["cls"])] += 1
                if "seconds" in out:
                    costs[a].append(out["seconds"])
                    evals[a].append(out["evaluations"])
                if out["cls"] in ("error", "timeout", "missing_start", "missing_run"):
                    error_rows.append({"id": cid, "k": k, "arm": a, "cls": out["cls"],
                                       "detail": out.get("exception", opt.get("exception", "|".join(out.get("tags", []))))})
                if r["diagnostic"] and meta["method"] == "LM":
                    mechanisms[a+"_expected_trace"] += 1
                    if not native:
                        mechanisms[a+"_missing_trace"] += 1
                    elif native.get("raw_info") is None:
                        mechanisms[a+"_incomplete_trace"] += 1
                    if native.get("issues"):
                        mechanisms[a+"_issue_runs"] += 1
                    mechanisms[a+"_unknown_trials"] += native.get("counts", {}).get("unknown", 0)
                    mechanisms[a+"_trial_count"] += sum(native.get("counts", {}).values())
            pcg2.update(r["G2"].get("g2", {}))
            if any(k != "calls" and v for k,v in r["G2"].get("g2", {}).items()):
                audit["g2_fallback_runs"] += 1
            old = r["old_cls"]
            b, n, g = (r[a]["cls"] for a in ARMS)
            transition[("B_to_N", b, n)] += 1
            transition[("B_to_G2", b, g)] += 1
            transition[("old_to_B", old, b)] += 1
            if "S" in r:
                transition[("B_to_S_diagnostic", b, r["S"]["cls"])] += 1
                mechanisms["B_S_class_disagree_all_diagnostic"] += b != r["S"]["cls"]
            paired["old_disagree"] += old != b
            paired["rescue_N"] += b != "hit" and n == "hit"
            paired["loss_N"] += b == "hit" and n != "hit"
            paired["rescue_G2"] += b != "hit" and g == "hit"
            paired["loss_G2"] += b == "hit" and g != "hit"
            if r["diagnostic"] and meta["method"] == "LM" and r["F"] is True:
                if b != "hit" and n == "hit":
                    mechanisms["F_B_fail_N_hit"] += 1
                    mc = mechanism_cases[cid]
                    mc["F_B_fail_N_hit"] += 1
                    bn = r["B"].get("native", {})
                    nn = r["N"].get("native", {})
                    s = r.get("S", {})
                    if bn.get("raw_info") is None or bn.get("issues") or not s:
                        mechanisms["rescue_missing_mechanism"] += 1
                        mc["missing"] += 1
                    wall = bn.get("wall_reject_joint", 0) > 0
                    sh = s.get("cls") == "hit"
                    mechanisms["rescue_with_wall_reject"] += wall
                    mechanisms["rescue_also_S_hit"] += sh
                    mechanisms["rescue_N_accepted_I"] += nn.get("accepted_I", 0) > 0
                    mc["wall_reject"] += wall
                    mc["S_hit"] += sh
                if "S" in r:
                    mechanisms["B_S_class_disagree"] += b != r["S"]["cls"]
            if r["diagnostic"] and meta["method"] == "Powell":
                mechanisms["powell_diagnostic_nonapplicable"] += 1
        g2counts.update(pcg2)
        if any(k != "calls" and v for k,v in pcg2.items()):
            audit["g2_fallback_cases"] += 1
        g2_rows.append({"id": cid, **dict(pcg2)})
        row.update(paired)
        for a in ARMS:
            row[a+"_hits"] = pc[a]["hit"]
            row["p_"+a] = divide(pc[a]["hit"], meta["n"])
            row["pF_"+a] = divide(hits_FI[a]["True"], row["nF"])
            row["pI_"+a] = divide(hits_FI[a]["False"], row["nI"])
            for cl in ("hit", "stuck", "wrong_branch", "wrong_answer", "left_box", "error", "timeout", "missing_start", "missing_run"):
                row[a+"_"+cl] = pc[a][cl]
        row["delta_N"] = row["p_N"]-row["p_B"]
        row["delta_G2"] = row["p_G2"]-row["p_B"]
        row["wrong_increase_N"] = (row["N_wrong_branch"]+row["N_wrong_answer"] > row["B_wrong_branch"]+row["B_wrong_answer"])
        table.append(row)
    for (method, a, st, info, cl), count in sorted(status.items()):
        status_rows.append({"method": method, "arm": a, "status": st, "raw_info": info, "cls": cl, "count": count})
    for (pair, b, n), count in sorted(transition.items()):
        transition_rows.append({"pair": pair, "from": b, "to": n, "count": count})
    used = table if final else [r for r in table if r["complete"]]
    res = {"final": final, "problems_expected": len(table), "completed_problems": sum(r["complete"] for r in table),
           "problems_analyzed": len(used), "starts_expected": sum(r["n"] for r in table), "starts_observed": actual,
           "short_original_problems": sum(r["n"] < 200 for r in table), "audit": dict(audit),
           "class_counts_all_observed": {a: dict(c) for a,c in totals.items()},
           "g2_counts": dict(g2counts), "mechanism": dict(mechanisms),
           "costs": {a: {"n_timed": len(v), "sum_seconds": sum(v), "median_seconds": float(np.median(v)),
                          "sum_evaluations": sum(evals[a]), "median_evaluations": float(np.median(evals[a]))}
                     for a,v in costs.items()},
           "group_counts": [{"method": m, "start_F": F, "arm": a, **dict(c)} for (m,F,a),c in groups.items()]}
    if used:
        res["means"] = {a: float(np.mean([r["p_"+a] for r in used])) for a in ARMS}
        res["delta_N"] = average_ci([r["delta_N"] for r in used])
        res["delta_G2"] = average_ci([r["delta_G2"] for r in used])
        res["delta_counts"] = {"positive": sum(r["delta_N"] > 1e-12 for r in used),
                               "zero": sum(abs(r["delta_N"]) <= 1e-12 for r in used),
                               "negative": sum(r["delta_N"] < -1e-12 for r in used),
                               "ge_0.10": sum(r["delta_N"] >= .10-1e-12 for r in used),
                               "le_minus_0.05": sum(r["delta_N"] <= -.05+1e-12 for r in used)}
        res["correlations"] = {}
        for kind in ("phi", "phi_independent", "human"):
            rr = [r for r in used if r[kind] is not None]
            res["correlations"][kind] = {"n": len(rr), "missing": len(used)-len(rr),
                **{a: {"spearman": rho([r[kind] for r in rr], [r["p_"+a] for r in rr]),
                       "partial_nvars": partial([r[kind] for r in rr], [r["p_"+a] for r in rr], [r["n_vars"] for r in rr])}
                   for a in ARMS}}
        res["strata"] = {}
        for name, rr in [(m, [r for r in used if r["method"] == m]) for m in ("LM", "Powell")]:
            res["strata"][name] = {"n": len(rr), "delta_N": average_ci([r["delta_N"] for r in rr]),
                                   "means": {a: float(np.mean([r["p_"+a] for r in rr])) if rr else None for a in ARMS}}
        bad = [r for r in used if r["delta_N"] <= -.05+1e-12]
        res["risk"] = {"bad_n": len(bad), "bad_fraction": len(bad)/len(used),
                       "bad_wrong_increase": sum(r["wrong_increase_N"] for r in bad)}
        for R in (True, False):
            rr = [r for r in used if r["risk"] == R]
            nb = sum(r["delta_N"] <= -.05+1e-12 for r in rr)
            res["risk"][str(R)] = {"n": len(rr), "bad_n": nb, "rate": divide(nb, len(rr))}
        res["ratio_G2"] = (res["delta_G2"]["mean"]/res["delta_N"]["mean"] if res["delta_N"]["mean"] > 0 else None)
        res["mean_abs_G2_N"] = float(np.mean([abs(r["p_G2"]-r["p_N"]) for r in used]))
        res["paired"] = {key: sum(r.get(key, 0) for r in used) for key in
                         ("rescue_N", "loss_N", "rescue_G2", "loss_G2", "old_disagree")}
        for name, rr in [("complete_records", [r for r in used if r["complete"]]),
                         ("original_200", [r for r in used if r["n"] == 200]),
                         ("G2_no_boolean_guard", [r for r,meta in zip(table,manifest["problems"])
                             if (final or r["complete"]) and not meta["boolean_kinds"]])]:
            res["strata"][name] = {"n": len(rr), "delta_N": average_ci([r["delta_N"] for r in rr]),
                                   "delta_G2": average_ci([r["delta_G2"] for r in rr]),
                                   "means": {a: float(np.mean([r["p_"+a] for r in rr])) if rr else None for a in ARMS}}
        if final:
            res["verdicts"] = verdicts(res)
    write_csv(HERE/"per-problem.csv", table)
    write_csv(HERE/"status.csv", status_rows)
    write_csv(HERE/"transitions.csv", transition_rows)
    write_csv(HERE/"failures.csv", error_rows)
    write_csv(HERE/"g2-fallbacks.csv", g2_rows)
    write_csv(HERE/"mechanism-by-problem.csv", [{"id": cid, **dict(c)} for cid,c in mechanism_cases.items()])
    write_json(HERE/"summary.json", res)
    return res, used


def verdicts(s):
    delta = s["delta_N"]
    corr = s["correlations"]
    pb, pn = (corr["phi"][a]["partial_nvars"] for a in ("B", "N"))
    hb, hn = (corr["human"][a]["spearman"] for a in ("B", "N"))
    risk = s["risk"]
    r1, r0 = (risk[str(b)]["rate"] for b in (True, False))
    m = s["mechanism"]
    denom = m.get("F_B_fail_N_hit", 0)
    return {"P1": delta["mean"] >= .03 and delta["ci95"][0] > 0 and s["delta_counts"]["ge_0.10"] >= 30,
            "P2": None if pb is None or pn is None else abs(pn) < .15 and pb-pn >= .20,
            "P3": None if r1 is None or r0 is None else
                  .05 <= risk["bad_fraction"] <= .20 and r1 >= 2*r0 and risk["bad_wrong_increase"] > risk["bad_n"]/2,
            "P4": None if s["ratio_G2"] is None else .25 <= s["ratio_G2"] <= 1.25,
            "P5": None if hb is None or hn is None else abs(hn) < .20 and abs(hn-hb) < .10,
            "M1": None if not denom or m.get("rescue_missing_mechanism", 0) else
                  m.get("rescue_with_wall_reject", 0)/denom >= .80 and m.get("rescue_also_S_hit", 0)/denom <= .10}


def provisional(s):
    counts = s["class_counts_all_observed"]
    text = "# Q1 暫定報告\n\n## 結論（実行途中）\n\n"
    text += (f"292問中{s['completed_problems']}問が全保存startを完了した。全体の結論とP1〜P5・M1の判定は保留する。"
             "処理順は過去の実行時間が長い問題からであり、完了部分は292問の無作為標本ではない。\n\n")
    text += "## 根拠：何を測り、ここまで何が出たか\n\n"
    text += (f"同じ保存開始点からB（凍結）、N（hardのみ0）、G2（固定の距離型）を比較している。"
             f"{s['starts_expected']:,}開始点のうち{s['starts_observed']:,}組が完了した。"
             "最大4ワーカー、各開始・条件10秒上限、最終採点は元の等式・guard・hard・箱・答えを共通に保つ。\n\n")
    if s.get("means"):
        text += "完了問題に限った問題平均（暫定）：" + "、".join(f"{a}={s['means'][a]:.4f}" for a in ARMS) + "。\n\n"
        pairs=s["paired"]
        text += (f"同じ完了問題の対応開始点で、Nの救済{pairs['rescue_N']}・喪失{pairs['loss_N']}。"
                 f"再実行Bと旧rawの分類差は{pairs['old_disagree']}件（時間上限の違いも含む）。\n\n")
    text += "|条件|記録数|hit|stuck|wrong_branch|wrong_answer|left_box|error|timeout|\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    for a in (*ARMS, "S"):
        c=counts[a]
        text += "|"+"|".join([a,str(sum(c.values())),*[str(c.get(k,0)) for k in ("hit","stuck","wrong_branch","wrong_answer","left_box","error","timeout")]])+"|\n"
    text += ("\nSは固定診断集合のLMだけで行う停止条件対照であり、主3条件と分母が違う。"
             "未完了分を完了したと扱わない。最終報告では欠測、旧Bとの不一致、G2 fallback、native軌道の不明判定も数える。\n\n"
             "[事前登録](preregistration.md)は新しい探索前に固定済み。開始座標・F/I・診断対象・悪化リスク群は"
             "[manifest.json](manifest.json)、入力と実装のSHA256は[execution-freeze.json](execution-freeze.json)。"
             "G2は制約値の空間のhinge型であり、作図不能・真偽値述語等のfallbackを含むため大域的に滑らかな方法ではない。\n\n"
             "実行前の人工guard単体チェックでcontext不足の失敗が2回あり、補正して合格した。"
             "その時点でoptimizer実行は0回で、本実験の失敗とは別に[preflight.json](preflight.json)へ記録した。\n")
    (HERE/"answer.md").write_text(text)


if __name__ == "__main__":
    ap=argparse.ArgumentParser()
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--update-answer", action="store_true")
    args=ap.parse_args()
    if args.final:
        assert (HERE/"run-complete.json").exists()
    result, rows = collect(args.final)
    if args.update_answer and not args.final:
        provisional(result)
    print(json.dumps({k:result[k] for k in ("final","completed_problems","starts_observed")}, ensure_ascii=False))
    if result.get("verdicts"):
        print(json.dumps(result["verdicts"], ensure_ascii=False))
