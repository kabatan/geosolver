"""Read-only, post-hoc audit. No solver runs; all outputs stay beside this script."""
from pathlib import Path
import csv
import hashlib
import json
import math
import os
from collections import Counter

for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"

import numpy as np
from scipy.stats import spearmanr
import sympy as sp

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
DATA = ROOT / "jssa/difficulty/start-feasibility-1023"
SOURCES = {}


def read(path):
    raw = path.read_bytes()
    SOURCES[str(path.relative_to(ROOT))] = hashlib.sha256(raw).hexdigest()
    return raw.decode()


def csv_rows(path):
    return list(csv.DictReader(read(path).splitlines()))


def mean(xs):
    return float(np.mean(xs)) if len(xs) else None


def interval(xs):
    a = np.asarray(xs, dtype=float)
    rng = np.random.default_rng(17023)
    samples = a[rng.integers(0, len(a), size=(10000, len(a)))].mean(axis=1)
    return [float(x) for x in np.quantile(samples, [0.025, 0.975])]


seed0 = {r["id"]: r for r in csv_rows(DATA / "per-problem.csv")}
seed1 = {r["id"]: r for r in csv_rows(DATA / "per-problem-seed1.csv")}
pred = {r["id"]: r for r in csv_rows(DATA / "predictions.csv")}
seed2 = csv_rows(DATA / "seed2-summary.csv")
rows = []
pilots = []
endpoints = {}

for r in seed2:
    case_id = r["id"]
    a, b = seed0[case_id], seed1[case_id]
    nf, ni = int(a["n_feas"]), int(a["n_infeas"])
    pf0 = int(a["hit_feas"]) / nf if nf else None
    pi0 = int(a["hit_infeas"]) / ni if ni else None
    delta0 = float(r["pred_delta"]) if r["pred_delta"] else None
    if delta0 is not None and not math.isfinite(delta0):
        delta0 = None
    plain, feasible = float(r["p_plain"]), float(r["p_feasible"])
    adaptive = plain if delta0 is not None and delta0 < 0 else feasible
    phi = nf / int(a["starts"])
    row = dict(id=case_id, n_vars=int(a["n_vars"]), n_feas0=nf, n_infeas0=ni,
               phi0=phi, p_feas0=pf0, p_infeas0=pi0, pred_delta=delta0,
               p_plain=plain, p_feasible=feasible, delta2=feasible-plain,
               starts_plain=int(r["starts_plain"]), starts_feasible=int(r["starts_feasible"]),
               p_seed0_selector=adaptive, p_observed_oracle=max(plain, feasible),
               no_feasible_in_20=(1-phi)**20,
               only_one_class_in_20=(1-phi)**20 + phi**20)
    nf1, ni1 = int(b["n_feas"]), int(b["n_infeas"])
    row["gap1"] = int(b["hit_feas"])/nf1 - int(b["hit_infeas"])/ni1 if nf1 and ni1 else None
    rows.append(row)
    raw = json.loads(read(DATA / "seed2-plain" / (case_id + ".json")))
    raw_f = json.loads(read(DATA / "seed2-feasible" / (case_id + ".json")))
    records = sorted(raw["records"], key=lambda x: x["k"])
    assert len(records) == row["starts_plain"]
    assert abs(sum(x["cls"] == "hit" for x in records) / len(records) - plain) < 1e-12
    assert len(raw_f["records"]) == row["starts_feasible"]
    assert abs(sum(x["cls"] == "hit" for x in raw_f["records"]) / len(raw_f["records"]) - feasible) < 1e-12
    endpoints[case_id] = {
        name: dict(Counter(x["cls"] for x in records if bool(x["start_feasible"]) == flag))
        for name, flag in [("feasible_start", True), ("infeasible_start", False)]
    }
    if len(records) <= 20:
        continue
    first, later = records[:20], records[20:]
    f = [x for x in first if x["start_feasible"]]
    i = [x for x in first if not x["start_feasible"]]
    pf = mean([x["cls"] == "hit" for x in f])
    pi = mean([x["cls"] == "hit" for x in i])
    choose_plain = pf is not None and pi is not None and pf < pi
    pp = mean([x["cls"] == "hit" for x in later])
    pilots.append(dict(id=case_id, pilot_n_feasible=len(f), pilot_n_infeasible=len(i),
                       pilot_p_feasible=pf, pilot_p_infeasible=pi,
                       choose_plain=choose_plain, remaining_plain=pp, separate_feasible=feasible,
                       selected_p=pp if choose_plain else feasible,
                       pilot_sec_sum=sum(x["sec"] for x in first),
                       later_n=len(later)))


def summary(rs):
    differences = [r["delta2"] for r in rs]
    gain = [r["p_seed0_selector"]-r["p_feasible"] for r in rs]
    oracle_gain = [r["p_observed_oracle"]-r["p_feasible"] for r in rs]
    return dict(n=len(rs), mean_plain=mean([r["p_plain"] for r in rs]),
                mean_feasible=mean([r["p_feasible"] for r in rs]),
                mean_delta=mean(differences), delta_exploratory_95ci=interval(differences),
                improved=sum(x > 0 for x in differences), worsened=sum(x < 0 for x in differences),
                tied=sum(x == 0 for x in differences),
                mean_seed0_selector=mean([r["p_seed0_selector"] for r in rs]),
                seed0_selector_gain_over_feasible=mean(gain),
                selector_gain_exploratory_95ci=interval(gain),
                mean_observed_oracle=mean([r["p_observed_oracle"] for r in rs]),
                observed_oracle_gain_over_feasible=mean(oracle_gain))


def pooled(table):
    rs = list(table.values())
    return dict(n=len(rs), starts=sum(int(r["starts"]) for r in rs),
                n_feas=sum(int(r["n_feas"]) for r in rs),
                n_infeas=sum(int(r["n_infeas"]) for r in rs),
                hit_feas=sum(int(r["hit_feas"]) for r in rs),
                hit_infeas=sum(int(r["hit_infeas"]) for r in rs))


neg = [r for r in rows if r["pred_delta"] is not None and r["pred_delta"] < 0]
supported = [r for r in rows if r["n_feas0"] >= 10 and r["n_infeas0"] >= 10]
strong = [r for r in supported if r["pred_delta"] < -0.1]
known = [r for r in rows if r["pred_delta"] is not None]
tp = sum(r["delta2"] < 0 for r in neg)
fn = sum(r["delta2"] < 0 for r in rows if r not in neg)
fp = len(neg) - tp
tn = len(rows) - tp - fn - fp
pilot_gains = [r["selected_p"]-r["separate_feasible"] for r in pilots]
metrics = {
    "scope": "Post-hoc existing data only; no solver runs; question-weighted unless pooled.",
    "seed0_pooled": pooled(seed0), "seed1_pooled": pooled(seed1),
    "all150": summary(rows),
    "both200": summary([r for r in rows if r["starts_plain"] == 200 and r["starts_feasible"] == 200]),
    "both_classes_at_least10_seed0": summary(supported),
    "prediction_available": len(known),
    "prediction_vs_delta2_spearman": float(spearmanr([r["pred_delta"] for r in known], [r["delta2"] for r in known]).statistic),
    "negative_prediction": dict(n=len(neg), worsened=tp,
                                improved=sum(r["delta2"] > 0 for r in neg),
                                tied=sum(r["delta2"] == 0 for r in neg),
                                both_classes_at_least10=sum(r in supported for r in neg),
                                n_feas_le5=sum(r["n_feas0"] <= 5 for r in neg),
                                strong_supported_ids=[r["id"] for r in strong],
                                strong_supported_results=[dict(id=r["id"], delta0=r["pred_delta"], delta2=r["delta2"], gap1=r["gap1"]) for r in strong]),
    "same_problem_seed0_selector_negative_detection": dict(tp=tp, fn=fn, fp=fp, tn=tn,
                accuracy=(tp+tn)/len(rows), constant_nonnegative_accuracy=(tn+fp)/len(rows),
                balanced_accuracy=0.5*(tp/(tp+fn)+tn/(tn+fp))),
    "pilot20_with_reference_answers": dict(n=len(pilots),
                one_class_only=sum(r["pilot_n_feasible"] == 0 or r["pilot_n_infeasible"] == 0 for r in pilots),
                both_classes_at_least5=sum(r["pilot_n_feasible"] >= 5 and r["pilot_n_infeasible"] >= 5 for r in pilots),
                choose_plain=sum(r["choose_plain"] for r in pilots),
                mean_remaining_plain=mean([r["remaining_plain"] for r in pilots]),
                mean_separate_feasible=mean([r["separate_feasible"] for r in pilots]),
                mean_selected=mean([r["selected_p"] for r in pilots]),
                selected_gain_over_feasible=mean(pilot_gains),
                exploratory_95ci=interval(pilot_gains),
                median_pilot_secs=float(np.median([r["pilot_sec_sum"] for r in pilots])),
                no_cost_included=True),
    "pilot20_phi0_model": dict(mean_no_feasible=mean([r["no_feasible_in_20"] for r in rows]),
                mean_only_one_class=mean([r["only_one_class_in_20"] for r in rows]),
                phi0_zero=sum(r["phi0"] == 0 for r in rows)),
    "strong_negative_endpoint_classes_seed2_plain": {r["id"]: endpoints[r["id"]] for r in strong},
}

# Exact algebraic counterexamples, not numerical search.
x, y, t = sp.symbols("x y t")
circle = x*x + y*y - 1
gb = sp.groebner([circle, t-x*x-y*y], x, y, t, order="lex")
superset = sp.expand((x*x-1) - (x-1)*(x+1))
complex_real = sp.groebner([x*x+y*y], x, y)
metrics["exact_examples"] = dict(
    moving_circle_elimination_basis=[str(f) for f in gb.polys],
    moving_circle_target_constant=bool(t-1 in list(gb)),
    superset_certificate_remainder=str(superset),
    superset_explanation="F=x-1, tau=x, P=t^2-1; P(tau)=(x+1)F, but real image={1}, not {-1,1}.",
    complex_positive_dimension=not complex_real.is_zero_dimensional,
    complex_real_explanation="x^2+y^2=0 has positive complex dimension but real locus={(0,0)}.",
    empty_real_certificate="F=x^2+1, tau=x^2: (tau+1)=F; no real witness exists.",
    tangent_test_insufficient="F=y, tau=x^2; d(tau)=0 at origin, but tau(1,0)=1.")

evidence = OUT / "evidence"
evidence.mkdir(exist_ok=True)
prior_sources = ROOT / "jssa/strategy/astra-consult-17/H/sources"
if (evidence / "prior-batch-summary.csv").exists() or (prior_sources / "prior-batch-summary.csv").exists():
    for name in ("prior-batch-summary.csv", "prior-README.md"):
        if not (evidence / name).exists():
            (evidence / name).write_text(read(prior_sources / name))
        else:
            read(evidence / name)
    batch = csv_rows(evidence / "prior-batch-summary.csv")
    if (prior_sources / "prior-certify.py").exists():
        read(prior_sources / "prior-certify.py")
    sample = next(r for r in batch if r["id"] == "AIME-2007-II-15")
    poly = sp.sympify(sample["elim"], locals={"x4": t})
    metrics["existing_certificate_records_not_reverified"] = {
        "n": len(batch), "statuses": dict(Counter(r["status"] for r in batch)),
        "status_and_check": dict(Counter(r["status"]+"/"+r["check"] for r in batch)),
        "example_id": sample["id"], "example_P_coeffs": sample["P_coeffs"],
        "example_E": str(poly), "example_E_real_roots": [str(v) for v in sp.Poly(poly, t).real_roots()],
        "limits": "CSV and generator code inspected; original cofactor certificates and all guard eliminations were not reverified.",
    }

tc = csv_rows(ROOT / "jssa/results/tangency-signed/per-case.csv")
tr = [r for r in tc if r["order"] == "off_first"]
low = [r for r in tr if float(r["without_best_digits"]) < 50]
metrics["existing_tangency_records"] = {
    "n_questions": len(tr), "n_orders": len(tc),
    "off_lt50": len(low),
    "off_lt50_on_ge100": sum(float(r["with_best_digits"]) >= 100 for r in low),
    "off_lt50_on_ge120": sum(float(r["with_best_digits"]) >= 120 for r in low),
    "some_candidate_converged_on": sum(int(r["with_converged"]) > 0 for r in tr),
    "some_candidate_converged_off": sum(int(r["without_converged"]) > 0 for r in tr),
    "limits": "Best residual digits, not guaranteed digits or full-solver final accuracy; 3 rewrites disabled together.",
}

for name, rs in [("per-problem-audit.csv", rows), ("pilot20-audit.csv", pilots)]:
    with (OUT / name).open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rs[0]))
        writer.writeheader()
        writer.writerows(rs)
(OUT / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2)+"\n")
(OUT / "source-hashes.json").write_text(json.dumps(SOURCES, ensure_ascii=False, indent=2, sort_keys=True)+"\n")
print(json.dumps(metrics, ensure_ascii=False, indent=2))
