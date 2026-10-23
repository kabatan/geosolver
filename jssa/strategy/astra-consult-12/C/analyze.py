"""Audit outcomes, compute statistics, and check AIME's analytic geometry. No solver runs."""
from collections import Counter
import hashlib
import json
import math
import platform
import statistics
import sys

import mpmath as mp
import numpy as np
from scipy.stats import spearmanr
import experiment as e


def boot_interval(values):
    values = np.array(values, dtype=float)
    rng = np.random.default_rng(102302)
    sample = values[rng.integers(0, len(values), size=(20000, len(values)))].mean(axis=1)
    return dict(mean=float(values.mean()), low=float(np.quantile(sample, .025)), high=float(np.quantile(sample, .975)))


def holm(rows):
    ordered = sorted(rows, key=lambda r: r["mcnemar_p"])
    running = 0.0
    for rank, row in enumerate(ordered):
        running = max(running, min(1.0, (len(rows)-rank)*row["mcnemar_p"]))
        row["holm_p_7_primary"] = running


e.summarize()
features = json.loads((e.HERE / "features.json").read_text())
feature_by_id = {r["case_id"]: r for r in features}
runs = {p.name: json.loads(p.read_text()) for p in (e.HERE / "runs").glob("*.json")}
costs, primary, audits = [], [], []
for name, d in sorted(runs.items()):
    case = e.Case(d["case_id"])
    assert d["completed"] == d["requested"] == 60, name
    assert len(d["rows"]) == 60
    for system in d["systems"]:
        recs = [row[system] for row in d["rows"] if system in row]
        assert len(recs) == 60, (name, system)
        hits = [r for r in recs if r["cls"] == "hit"]
        counts = Counter(r["cls"] for r in recs)
        mean_sec = statistics.mean(r["sec"] for r in recs)
        costs.append(dict(file=name, case_id=d["case_id"], system=system, n=len(recs), hits=len(hits),
                          hit=counts["hit"], left_region=counts["left_region"], stuck=counts["stuck"],
                          stuck_cap=counts["stuck_cap"], wrong_branch=counts["wrong_branch"],
                          wrong_answer=counts["wrong_answer"], undefined=counts["undefined"],
                          mean_sec=mean_sec, median_sec=statistics.median(r["sec"] for r in recs),
                          mean_nfev=statistics.mean(r["nfev"] for r in recs),
                          mean_sec_over_p=mean_sec*len(recs)/len(hits) if hits else None))
        original_res, physical_res = [], []
        for r in hits:
            original_res.append(float(np.linalg.norm(e.eq(case.ee, r["u"]))))
            physical_res.append(float(np.linalg.norm(e.eq(case.ye, case.ypoint(r["u"], r["h"])))))
        audits.append(dict(file=name, system=system, hits=len(hits),
                           max_original_res=max(original_res, default=None),
                           max_physical_Y_res=max(physical_res, default=None),
                           original_res_over_1e8=sum(v>1e-8 for v in original_res),
                           physical_res_over_1e8=sum(v>1e-8 for v in physical_res)))
    if name.endswith(".fresh.json"):
        primary.append(dict(case_id=d["case_id"], rule_R=feature_by_id[d["case_id"]]["rule_R"],
                            **e.paired(d["rows"], "E", "Y")))
holm(primary)
e.save_csv("costs_and_classes.csv", costs)
e.save_csv("primary_results.csv", primary)
e.save_csv("hit_audit.csv", audits)

wide = runs["AIME-2020-II-15.fresh.json"]
compact = runs["AIME-2020-II-15.compact.json"]
ablation = [dict(A="Y", B=s, **e.paired(wide["rows"], "Y", s)) for s in ["Ynorm", "ZG", "Z", "Eunit"]]
hit = lambda row, s: int(row[s]["cls"] == "hit")
interaction = boot_interval([hit(r,"Y")-hit(r,"Ynorm")-hit(r,"ZG")+hit(r,"Z") for r in wide["rows"]])
distribution_effect = boot_interval([hit(w,"Y")-hit(w,"E")-hit(c,"Y")+hit(c,"E")
                                     for w,c in zip(wide["rows"],compact["rows"])])
small = e.paired(compact["rows"], "E", "Y")
e.save("interventions.json", dict(ablation=ablation, factorial_interaction=interaction,
                                 wide_advantage_minus_compact_advantage=distribution_effect,
                                 compact=small, prediction_B_holds=small["pA"]>=.5 and small["delta"]<=.1))

old_rows, old_three = [], []
for path in sorted(e.OLD.glob("*.json")):
    d = json.loads(path.read_text())
    base = json.loads((e.ROOT / f"jssa/difficulty/minima/raw-323/{d['case_id']}.json").read_text())
    old_rows.append(dict(case_id=d["case_id"], left_fraction=base["counts"].get("left_box",0)/base["starts_done"],
                         delta=d["summary"]["Y"]["p"]-d["summary"]["E"]["p"]))
    if d["case_id"] in ["AIME-2020-II-15","HMMT-2017-FEB-GEO-10","HMMT-2021-FEB-GEO-04"]:
        old_three.append(dict(case_id=d["case_id"], **e.paired(d["rows"],"E","Y")))
rho = spearmanr([r["left_fraction"] for r in old_rows], [r["delta"] for r in old_rows])
e.save_csv("old_escape_vs_gain.csv", old_rows)
e.save("old_comparison.json", dict(three_examples=old_three, n=len(old_rows),
                                  escape_gain_spearman=float(rho.statistic), p_value=float(rho.pvalue)))

mp.mp.dps = 60
def geometry(a, b):
    t = -242*b/(a*a+b*b-121)
    s1 = (11*(a+11)+t*b)/((a+11)**2+b*b)
    s2 = (-11*(a-11)+t*b)/((a-11)**2+b*b)
    x = (-11+s1*(a+11), s1*b)
    y = (11+s2*(a-11), s2*b)
    f1 = mp.sqrt(121+t*t)-16
    f4 = x[0]**2+(x[1]-t)**2+y[0]**2+(y[1]-t)**2+(x[0]-y[0])**2+(x[1]-y[1])**2-1143
    return [mp.mpf(0), f1, f1, f4], (x[0],x[1],y[0],y[1]), t

plateau = []
for b0 in [25,50,500,5000,50000,500000]:
    a,b = mp.mpf(4),mp.mpf(b0)
    f,h,t=geometry(a,b)
    J=np.array([[float(mp.diff(lambda z: geometry(z,b)[0][i],a)),
                 float(mp.diff(lambda z: geometry(a,z)[0][i],b))] for i in range(4)])
    sv=np.linalg.svd(J,compute_uv=False)
    plateau.append(dict(ax=4,ay=b0,T_y=float(t),distance_XB=float(mp.sqrt((h[0]+11)**2+h[1]**2)),
                        residual_norm=float(mp.sqrt(sum(v*v for v in f))),
                        sigma_min=float(sv[-1]),sigma_max=float(sv[0])))
e.save_csv("analytic_plateau.csv",plateau)

case=e.Case("AIME-2020-II-15")
errs, identities, proxy=[],[],[]
for k in range(16):
    rng=np.random.default_rng([102300,k])
    u=case.box[:,0]+rng.random(2)*case.width
    f,h,t=geometry(mp.mpf(float(u[0])),mp.mpf(float(u[1])))
    errs.append(float(np.linalg.norm(e.eq(case.ee,u)-np.array(f,dtype=float))/max(1,np.linalg.norm(np.array(f,dtype=float)))))
    hh=case.h(u)
    offset=rng.normal(size=4)
    residual=e.eq(case.ye,case.ypoint(u,hh+offset))[case.new_rows]
    identity=((u[0]+11)**2+u[1]**2)*sum(offset[:2]**2)+((u[0]-11)**2+u[1]**2)*sum(offset[2:]**2)
    identities.append(abs(float(residual@residual)-identity)/max(1,identity))
    J=e.jac(lambda q:e.eq(case.ee,q),u); H=e.jac(case.h,u);de=np.linalg.norm(J,axis=0)
    proxy.append(float(np.median(np.sqrt(de**2+np.linalg.norm(H,axis=0)**2)/de)))
e.save("analytic_checks.json",dict(formula_vs_DSL_max_relative_error=max(errs),
       foot_penalty_identity_max_relative_error=max(identities),
       old_column_proxy_same_starts_median=float(np.median(proxy)),
       actual_Y_base_column_inflation=feature_by_id[case.cid]["inflation"],
       plateau_norm_limit=math.sqrt(2*25+417**2), geometric_ax_abs_max=176/math.sqrt(135),
       geometric_ay_max=297/math.sqrt(135)))

rule_positive=[r for r in primary if r["rule_R"]]
validation=dict(python=sys.version,numpy=np.__version__,scipy=e.scipy.__version__,platform=platform.platform(),
    local_solves=sum(r["n"] for r in costs),run_elapsed_sum=sum(d["elapsed"] for d in runs.values()),
    n_diagnostic_problems=len(features),diagnostic_starts=sum(r["n_valid"] for r in features),
    diagnostic_attempts=16*len(features),
    diagnostic_low_accuracy=[r["case_id"] for r in features if r["tangent_error"]>.05],
    diagnostic_missing_starts=[dict(case_id=r["case_id"],n=r["n_valid"]) for r in features if r["n_valid"]<16],
    fresh_rule_positives=len(rule_positive),fresh_rule_true_positive=sum(r["delta"]>=.1-1e-12 for r in rule_positive),
    fresh_rule_false_positive=sum(r["delta"]<.1-1e-12 for r in rule_positive),
    total_hits=sum(r["hits"] for r in audits),
    total_hit_original_eq_over_1e8=sum(r["original_res_over_1e8"] for r in audits),
    total_hit_physical_Y_eq_over_1e8=sum(r["physical_res_over_1e8"] for r in audits),
    max_original_hit_res=max(r["max_original_res"] or 0 for r in audits),
    max_physical_Y_hit_res=max(r["max_physical_Y_res"] or 0 for r in audits))
e.save("validation.json",validation)
inputs=[e.ROOT / "jssa/difficulty/probe_common.py",e.ROOT / "jssa/difficulty/probe_basins.py",
        e.ROOT / "jssa/difficulty/expand_k.py",e.ROOT / "jssa/difficulty/expand_z.py",
        e.ROOT / "src/geosolver/engine/standard/search/scipy_multistart_backend.py",
        e.ROOT / "src/geosolver/problem/domain_bounds.py",e.ROOT / "benchmarks/cases.jsonl"]
inputs+=list(e.DSL.glob("*.k0.json"))+list(e.DSL.glob("*.k2.json"))+list(e.OLD.glob("*.json"))
inputs+=[e.ROOT / f"jssa/difficulty/minima/raw-323/{r['case_id']}.json" for r in old_rows]
e.save("input_sha256.json",{str(p.relative_to(e.ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(inputs)})
meta=json.loads((e.HERE/"diagnostics_meta.json").read_text())
if "elapsed" in meta:
    meta["elapsed_this_invocation"]=meta.pop("elapsed")
    meta["cases_this_invocation"]=["HMMT-2020-FEB-GEO-04"]
    meta["elapsed_scope_note"]="Last repaired-case invocation only; total diagnostic runtime was not recorded."
    e.save("diagnostics_meta.json",meta)
print("VALIDATION",json.dumps(e.clean(validation),ensure_ascii=False))
