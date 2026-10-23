"""Audit saved v8 evidence only; never import or run a solver/optimizer.

Run from any directory with:
  /home/kabatan/work/solver/.venv/bin/python -B jssa/strategy/astra-consult-15/recompute.py

All outputs are small files beside this script. Input files are opened read-only.
CSV rows in the output retain source row numbers (header is row 1).
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
from collections import Counter
from fractions import Fraction
from pathlib import Path

import numpy as np
from scipy.stats import binomtest, rankdata, spearmanr


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = "jssa/difficulty/start-feasibility-1023/"
MANIFEST = {}


def read_bytes(relative):
    path = ROOT / relative
    data = path.read_bytes()
    MANIFEST[relative] = {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return data


def read_csv(relative):
    rows = list(csv.DictReader(io.StringIO(read_bytes(relative).decode("utf-8-sig"))))
    for line, row in enumerate(rows, 2):
        row["_csv_row"] = line
    return rows


def read_json(relative):
    return json.loads(read_bytes(relative))


def write_json(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(name, rows):
    with (HERE / name).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def rho(x, y):
    return float(spearmanr(x, y).statistic)


def partial_spearman(x, y, z):
    a, b, c = map(rankdata, (x, y, z))
    design = np.column_stack((np.ones(len(c)), c))
    residuals = [v - design @ np.linalg.lstsq(design, v, rcond=None)[0] for v in (a, b)]
    return float(np.corrcoef(*residuals)[0, 1])


def mean(values):
    return float(np.mean(list(values)))


def main():
    # Record the required attachments without executing figure-generation code.
    for name in (
        "jssa/strategy/gpt-pro-consult-15-prompt.md",
        "jssa/draft/report-draft-v8.md",
        "jssa/draft/figures/fig4_feasible_start.png",
        BASE + "score_seed2.md",
        "jssa/strategy/gpt-pro-consult-14-answer.md",
        "jssa/draft/supplement-v7.md",
    ):
        read_bytes(name)

    summary = read_csv(BASE + "seed2-summary.csv")
    seed0 = read_csv(BASE + "per-problem.csv")
    seed1 = read_csv(BASE + "per-problem-seed1.csv")
    predictions = read_csv(BASE + "predictions.csv")
    by0 = {r["id"]: r for r in seed0}
    bypred = {r["id"]: r for r in predictions}
    assert set(bypred) == {r["id"] for r in summary}
    assert set(bypred) == {r["id"] for r in seed0 if int(r["n_feas"]) < int(r["starts"])}

    audited = []
    exact_delta = {}
    raw_methods = []
    for row in seed0:
        cid = row["id"]
        raw = read_json("jssa/difficulty/minima/raw-323/" + cid + ".json")
        assert len(raw["records"]) == int(row["starts"])
        assert math.isclose(raw["p_any"], float(row["p"]), abs_tol=1e-14)
        raw_methods.append({
            "id": cid, "n_vars": raw["n_vars"], "n_constraints": raw["n_constraints"],
            "method_by_backend_rule": "Powell" if raw["n_vars"] > raw["n_constraints"] else "LM",
            "starts": raw["starts_done"],
        })
    for row in summary:
        cid = row["id"]
        source = by0[cid]
        nf, hf, ni, hi = (int(source[k]) for k in ("n_feas", "hit_feas", "n_infeas", "hit_infeas"))
        result = dict(id=cid, summary_csv_row=row["_csv_row"], seed0_csv_row=source["_csv_row"],
                      seed0_feasible=nf, seed0_feasible_hits=hf, seed0_infeasible=ni,
                      seed0_infeasible_hits=hi, phi0=nf / (nf + ni), p0=(hf + hi) / (nf + ni),
                      pred_delta=row["pred_delta"])
        rates = {}
        for condition, column in (("plain", "p_plain"), ("feasible", "p_feasible")):
            raw = read_json(BASE + "seed2-" + condition + "/" + cid + ".json")
            recs = raw["records"]
            starts = len(recs)
            hits = sum(r["cls"] == "hit" for r in recs)
            feasible_starts = sum(r["start_feasible"] for r in recs)
            rate = Fraction(hits, starts)
            assert raw["starts_done"] == starts == int(row["starts_" + condition])
            assert math.isclose(float(rate), float(row[column]), rel_tol=0, abs_tol=1e-14)
            rates[condition] = rate
            result.update({
                condition + "_starts": starts, condition + "_hits": hits,
                column: float(rate), condition + "_feasible_starts": feasible_starts,
                condition + "_feasible_share": feasible_starts / starts,
                condition + "_elapsed_s": raw["elapsed"],
            })
        delta = rates["feasible"] - rates["plain"]
        exact_delta[cid] = delta
        result["delta"] = float(delta)
        result["abs_delta_lt_005"] = int(abs(delta) < Fraction(1, 20))
        result["abs_delta_le_005"] = int(abs(delta) <= Fraction(1, 20))
        result["delta_ge_030"] = int(delta >= Fraction(3, 10))
        result["low_p0"] = int(Fraction(hf + hi, nf + ni) < Fraction(3, 10))
        assert result["low_p0"] == int(float(row["p0"]) < 0.3)
        if row["pred_delta"]:
            pred = float(row["pred_delta"])
            result["prediction_error"] = float(delta) - pred
            result["abs_prediction_error"] = abs(float(delta) - pred)
            assert math.isclose(pred, float(bypred[cid]["pred_delta"]), abs_tol=1e-14)
        else:
            result["prediction_error"] = result["abs_prediction_error"] = ""
        audited.append(result)
    write_csv("seed2-audit.csv", audited)
    write_csv("local-search-methods.csv", raw_methods)

    predictable = [r for r in audited if r["pred_delta"] != ""]
    low = [r for r in audited if r["low_p0"]]
    negative = [r for r in predictable if float(r["pred_delta"]) < 0]
    increased = sum(v > 0 for v in exact_delta.values())
    decreased = sum(v < 0 for v in exact_delta.values())
    errs = [float(r["prediction_error"]) for r in predictable]
    raw_seed2 = {}
    for condition in ("plain", "feasible"):
        raw_seed2[condition] = dict(
            starts=sum(r[condition + "_starts"] for r in audited),
            minimum_starts=min(r[condition + "_starts"] for r in audited),
            maximum_starts=max(r[condition + "_starts"] for r in audited),
            cases_under_200=sum(r[condition + "_starts"] < 200 for r in audited),
            all_starts_feasible=sum(r[condition + "_feasible_share"] == 1 for r in audited),
            no_starts_feasible=sum(r[condition + "_feasible_share"] == 0 for r in audited),
        )
    output = {"seed2": dict(
        n=len(audited), mean_plain=mean(r["p_plain"] for r in audited),
        mean_feasible=mean(r["p_feasible"] for r in audited),
        mean_delta=mean(r["delta"] for r in audited),
        increased=increased, decreased=decreased, unchanged=len(audited)-increased-decreased,
        sign_test_one_sided=float(binomtest(increased, increased+decreased, alternative="greater").pvalue),
        predictable_n=len(predictable),
        prediction_spearman=rho([float(r["pred_delta"]) for r in summary if r["pred_delta"]],
                               [float(r["p_feasible"])-float(r["p_plain"]) for r in summary if r["pred_delta"]]),
        prediction_spearman_exact_rate_difference=rho([float(r["pred_delta"]) for r in predictable], [r["delta"] for r in predictable]),
        prediction_mae=mean(abs(v) for v in errs), prediction_rmse=math.sqrt(mean(v*v for v in errs)),
        I3_within_010=sum(abs(float(r["p_feasible"])-float(r["pred_p_feasible"])) <= 0.1
                         for r in summary if r["pred_p_feasible"]),
        negative_prediction_n=len(negative),
        negative_prediction_decreased=sum(r["delta"] < 0 for r in negative),
        negative_prediction_unchanged=sum(r["delta"] == 0 for r in negative),
        negative_prediction_increased=sum(r["delta"] > 0 for r in negative),
        negative_prediction_counterexamples=[r for r in negative if r["delta"] >= 0],
        largest_absolute_prediction_errors=sorted(predictable, key=lambda r: float(r["abs_prediction_error"]), reverse=True)[:5],
        low_p0_n=len(low), low_median_delta=float(np.median([r["delta"] for r in low])),
        low_delta_ge_030=sum(r["delta_ge_030"] for r in low),
        low_abs_delta_lt_005=sum(r["abs_delta_lt_005"] for r in low),
        low_abs_delta_le_005=sum(r["abs_delta_le_005"] for r in low),
        low_increased=sum(r["delta"]>0 for r in low), low_decreased=sum(r["delta"]<0 for r in low),
        low_unchanged=sum(r["delta"]==0 for r in low),
        low_all_starts_feasible=sum(r["feasible_feasible_share"]==1 for r in low),
        low_no_starts_feasible=sum(r["feasible_feasible_share"]==0 for r in low),
        low_small_change_all_starts_feasible=sum(r["abs_delta_lt_005"] and r["feasible_feasible_share"]==1 for r in low),
        figure4_low_n=sum(r["low_p0"] for r in predictable), raw=raw_seed2,
    )}

    human = read_csv("jssa/difficulty/ghost-1023/human_feat.csv")
    human_by_id = {r["case_id"]: r for r in human if r["human"]}
    write_csv("human-correlations.csv", [dict(
        seed=seed, contest=contest,
        n=len(group := [r for r in rows if r["id"] in human_by_id and human_by_id[r["id"]]["contest"] == contest]),
        rho_human_p=rho([float(human_by_id[r["id"]]["human"]) for r in group], [float(r["p"]) for r in group]),
        rho_human_phi=rho([float(human_by_id[r["id"]]["human"]) for r in group],
                          [int(r["n_feas"])/int(r["starts"]) for r in group]),
    ) for seed, rows in ((0, seed0), (1, seed1)) for contest in ("AIME", "HMMT")])
    output["start_observation"] = {}
    for seed, rows in ((0, seed0), (1, seed1)):
        totals = {key: sum(int(r[key]) for r in rows) for key in ("starts", "n_feas", "hit_feas", "n_infeas", "hit_infeas")}
        phi = [int(r["n_feas"])/int(r["starts"]) for r in rows]
        p = [float(r["p"]) for r in rows]
        totals.update(n=len(rows), under_200=sum(int(r["starts"])<200 for r in rows),
                      infeasible_share=totals["n_infeas"]/totals["starts"],
                      p_feasible=totals["hit_feas"]/totals["n_feas"],
                      p_infeasible=totals["hit_infeas"]/totals["n_infeas"], rho_phi_p=rho(phi,p),
                      partial_rho_phi_p_nvars=partial_spearman(phi,p,[int(r["n_vars"]) for r in rows]))
        output["start_observation"][str(seed)] = totals
    hmmt = sorted((r for r in human if r["contest"]=="HMMT" and r["human"]),
                  key=lambda r:float(r["human"]), reverse=True)
    output["human_example"] = [dict(rank=i+1, total=len(hmmt), **r) for i,r in enumerate(hmmt)
                               if r["case_id"]=="HMMT-2019-FEB-GEO-10"][0]
    output["powell"] = dict(n=sum(r["method_by_backend_rule"]=="Powell" for r in raw_methods),
                            selected150_n=sum(r["method_by_backend_rule"]=="Powell" and r["id"] in bypred for r in raw_methods))

    stages = read_csv("jssa/results/stage-profile-20261023/per-case.csv")
    columns = ("search_time_s", "refinement_time_s", "identification_verification_time_s", "rescue_time_s", "initial_probe_time_s")
    totals = {c: sum(float(r[c]) for r in stages) for c in columns}
    wall = sum(float(r["wall_time_s"]) for r in stages)
    output["production_stages"] = dict(n=len(stages), correct=sum(r["correct"]=="True" for r in stages),
        median_wall_s=float(np.median([float(r["wall_time_s"]) for r in stages])),
        totals=totals, wall_total_s=wall, recorded_phase_total_s=sum(totals.values()),
        refinement_share_of_wall=totals["refinement_time_s"]/wall,
        refinement_share_of_recorded_phases=totals["refinement_time_s"]/sum(totals.values()),
        search_share_of_wall=totals["search_time_s"]/wall,
        example=[r for r in stages if r["case_id"]=="AIME-2021-I-11" and r["seed"]=="0"])
    attribution = read_csv("jssa/results/mechanism-attribution/attribution.csv")
    output["attribution"] = dict(
        algebraic_unique_all_seeds=len({r["case_id"] for r in attribution if r["answer_source_uid_prefix"]=="search/exact_polynomial"}),
        algebraic_unique_seed0=len({r["case_id"] for r in attribution if r["seed"]=="0" and r["answer_source_uid_prefix"]=="search/exact_polynomial"}),
        fallback_seed0=sum(r["seed"]=="0" and r["second_attempt_selected"]=="fallback" for r in attribution),
        fallback_correct_seed0=sum(r["seed"]=="0" and r["second_attempt_selected"]=="fallback" and r["matched"]=="True" for r in attribution))
    factors = read_csv("jssa/difficulty/dissociation/factors.csv")
    a, b = (np.array([float(r[k]) for r in factors]) for k in ("A","B"))
    var_total = float(np.var(a+b))
    output["cost_variance"] = dict(n=len(factors), var_log_c=float(np.var(a)),
        var_log_n_over_p=float(np.var(b)), var_log_t_over_p=var_total,
        share_log_c=float(np.var(a)/var_total), share_log_n_over_p=float(np.var(b)/var_total),
        share_covariance=float(2*np.cov(a,b,ddof=0)[0,1]/var_total),
        zero_p_n=sum(float(r["p"])==0 for r in factors))

    endpoints = read_csv("jssa/difficulty/ghost-1023/endpoints_v1.csv")
    failed = [r for r in endpoints if r["cls"]!="hit"]
    hit = [r for r in endpoints if r["cls"]=="hit"]
    assert all(r["coinc"] and math.isfinite(float(r["coinc"])) for r in endpoints)
    output["ghost_endpoints"] = dict(cases=len({r["id"] for r in endpoints}), n=len(endpoints),
        failed_n=len(failed), hit_n=len(hit),
        failed_coinc_lt_1e4=sum(float(r["coinc"])<1e-4 for r in failed),
        failed_coinc_lt_1e6=sum(float(r["coinc"])<1e-6 for r in failed),
        failed_share_lt_1e4=mean(float(r["coinc"])<1e-4 for r in failed),
        failed_share_lt_1e6=mean(float(r["coinc"])<1e-6 for r in failed),
        hit_coinc_lt_1e4=sum(float(r["coinc"])<1e-4 for r in hit))
    ghost = read_csv("jssa/difficulty/ghost-exact/per-problem.csv")
    output["ghost_detection"] = dict(n=len(ghost), found_cases=sum(int(r["n_pairs_found"])>0 for r in ghost))
    ghost_by_id = {r["id"]: r for r in ghost}
    strata = []
    for level in range(1, 6):
        groups = [[r for r in seed0 if min(5, int(r["n_vars"])) == level
                   and (int(ghost_by_id[r["id"]]["n_pairs_found"]) > 0) == found]
                  for found in (True, False)]
        strata.append(dict(nvars_stratum=str(level) if level < 5 else "5+",
                           found_n=len(groups[0]), not_found_n=len(groups[1]),
                           found_p_median=float(np.median([float(r["p"]) for r in groups[0]])),
                           not_found_p_median=float(np.median([float(r["p"]) for r in groups[1]]))))
    output["ghost_detection"]["strata"] = strata
    outcomes = read_csv("jssa/difficulty/new2026-predict/outcomes.csv")
    output["heldout20"] = dict(n=len(outcomes),
        full_rho=rho([float(r["pred_logit_full"]) for r in outcomes],[float(r["p"]) for r in outcomes]),
        nvars_rho=rho([float(r["pred_logit_nvars_only"]) for r in outcomes],[float(r["p"]) for r in outcomes]),
        full_logit_sse=sum(float(r["squared_error_full"]) for r in outcomes),
        nvars_logit_sse=sum(float(r["squared_error_nvars_only"]) for r in outcomes))
    common = read_csv("jssa/difficulty/common-start/summary.csv")
    output["common_start"] = dict(n=len(common), medians={c:float(np.median([float(r[c]) for r in common])) for c in ("pE","pY","pZ")})
    scored = read_csv("jssa/difficulty/holdout-1023/out/scored.csv")
    output["holdout_EYZ"] = {k:dict(Counter(r[k] for r in scored)) for k in ("P1","P2")}
    report = read_bytes("jssa/draft/report-draft-v8.md").decode()
    count = lambda s: len("".join(s.split()))
    output["character_count"] = dict(
        all_no_whitespace=count(report),
        abstract_through_conclusion_no_whitespace=count(report[report.index("## 要旨"):report.index("## 生成AI")]),
        note="Markdown記号・画像パス・見出し込み。応募要項の字数定義ではない。")
    write_json("audit-summary.json", output)
    write_json("source-manifest.json", MANIFEST)
    print(json.dumps({"outputs": ["audit-summary.json", "seed2-audit.csv", "human-correlations.csv", "local-search-methods.csv", "source-manifest.json"],
                      "input_files":len(MANIFEST), "raw_seed2_probabilities_match_csv":True,
                      "mean_delta":output["seed2"]["mean_delta"], "rho":output["seed2"]["prediction_spearman"],
                      "MAE":output["seed2"]["prediction_mae"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
