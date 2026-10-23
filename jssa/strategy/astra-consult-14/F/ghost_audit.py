"""Exploratory numerical and statistical audit of the reported G indicator.

Read-only repository inputs. All generated artifacts stay beside this script.
No geometry search is performed here; best_x witnesses are evaluated unchanged.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
import audit as a
import numpy as np
from mpmath import mp
from scipy.special import logit
from scipy.stats import rankdata

from ghost_exact import augmented_evaluator
from ghost_scan import point_names
from probe_basins import construction_coordinates
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode

GP = a.ROOT / "jssa/difficulty/ghost-exact/per-problem.csv"
PP = a.ROOT / "jssa/difficulty/ghost-exact/per-pair.csv"


def witnesses():
    started = time.monotonic()
    cases = a.cases()
    pairs = a.csvread(PP)
    by_id = defaultdict(list)
    for p in pairs:
        if int(p["found"]):
            by_id[p["id"]].append(p)
    out = []
    for cid, group in by_id.items():
        b, ev, box = a.context(cases[cid])
        refs = a.reference_values(cases[cid]["answer"])
        coords = construction_coordinates(cases[cid]["dsl"], sorted(point_names(cases[cid]["dsl"])))
        for pair in group:
            x = json.loads(pair["best_x"])
            aug = augmented_evaluator(b, coords, pair["P"], pair["Q"])
            r = dict(id=cid, P=pair["P"], Q=pair["Q"], best_res=float(pair["best_res"]),
                     within_box=bool(np.all((np.array(x)>=box[:,0]) & (np.array(x)<=box[:,1]))),
                     max_abs_x=max(abs(t) for t in x), hp_res=None, hp_pass=False,
                     eq_hp_res=None, pair_hp_res=None, hp_error="", hard_feasible=None, hard_tags="",
                     original_class="", original_answer=None)
            try:
                with mp.workdps(80):
                    # mp.mpf(float) preserves the binary64 value, rather than
                    # improving it by a decimal re-interpretation or refinement.
                    values = [mp.mpf(t) for t in x]
                    with high_precision_mode():
                        hp = aug.evaluate_hp_residual(values, precision=80)
                        v = hp.residual_vector
                        eqnorm = mp.sqrt(sum(z*z for z in v[:-2]))
                        pairnorm = mp.sqrt(sum(z*z for z in v[-2:]))
                        passed = bool(hp.is_finite and hp.residual_norm_hp <= mp.mpf("1e-10"))
                    r["hp_res"] = float(hp.residual_norm_hp)
                    r["eq_hp_res"] = float(eqnorm)
                    r["pair_hp_res"] = float(pairnorm)
                    r["hp_pass"] = passed
            except Exception as exc:
                r["hp_error"] = repr(exc)
            try:
                snap = ev.evaluate_float_hard_feasibility(x, include_margins=False)
                r["hard_feasible"] = bool(snap.hard_feasible)
                r["hard_tags"] = json.dumps(list(snap.failure_tags), ensure_ascii=False)
            except Exception as exc:
                r["hard_tags"] = repr(exc)
            try:
                checked = a.classify(b,ev,box,refs,np.array(x),0,a.smb._SearchTelemetry())
                r["original_class"] = checked["cls"]
                r["original_answer"] = checked.get("answer")
            except Exception as exc:
                r["original_class"] = "error: " + repr(exc)
            out.append(r)
        if len(out) % 20 < len(group):
            print("witnesses",len(out),"/ 648",flush=True)
    a.csvwrite("ghost-witnesses.csv",out)
    good = [r for r in out if r["hp_pass"]]
    by_problem = defaultdict(list)
    for r in out:
        by_problem[r["id"]].append(r)
    summary = {
        "pairs_found":len(out), "problems_found":len(by_problem),
        "hp_pass_pairs":len(good), "hp_pass_problems":len({r["id"] for r in good}),
        "hp_nonfinite_or_error_pairs":sum(r["hp_res"] is None or not math.isfinite(r["hp_res"]) for r in out),
        "within_box_pairs":sum(r["within_box"] for r in out),
        "within_box_problems":len({r["id"] for r in out if r["within_box"]}),
        "hard_feasible_pairs":sum(r["hard_feasible"] is True for r in out),
        "hard_feasible_problems":len({r["id"] for r in out if r["hard_feasible"] is True}),
        "original_classes":dict(Counter(r["original_class"] for r in out)),
        "original_hit_problems":len({r["id"] for r in out if r["original_class"]=="hit"}),
        "all_saved_witnesses_fail_hp":[cid for cid,rs in by_problem.items() if not any(r["hp_pass"] for r in rs)],
        "seconds":time.monotonic()-started,
    }
    a.dump("ghost-witness-summary.json",summary)
    print(json.dumps(summary,indent=2),flush=True)


def strata_summary(d, g, p):
    out=[]
    for k in (1,2,3,4,5):
        mask=np.minimum(d,5)==k
        one=p[mask & (g==1)]; zero=p[mask & (g==0)]
        out.append(dict(d=k,n1=len(one),n0=len(zero),median1=float(np.median(one)),
                        median0=float(np.median(zero)),mean1=float(np.mean(one)),mean0=float(np.mean(zero))))
    return out


def strat_perm(d, g, p, count=10000):
    rng=np.random.default_rng(1402314)
    strata=[np.where(np.minimum(d,5)==k)[0] for k in (1,2,3,4,5)]
    pr=rankdata(p)
    gr=rankdata(g)
    for idx in strata:
        pr[idx]-=pr[idx].mean(); gr[idx]-=gr[idx].mean()
    obs=a.corr(gr,pr)
    den=np.linalg.norm(gr)*np.linalg.norm(pr)
    lesser=0
    for _ in range(count):
        dot=sum(np.dot(rng.permutation(gr[ii]),pr[ii]) for ii in strata)
        lesser+=dot/den<=obs
    return dict(rank_residual_rho=obs,one_sided_p=(1+lesser)/(1+count),permutations=count)


def stats():
    started=time.monotonic()
    rows=a.csvread(a.OUT/"features.csv"); n=len(rows)
    gp={r["id"]:r for r in a.csvread(GP)}
    pairs=a.csvread(PP)
    by_problem=defaultdict(list)
    for pair in pairs:
        by_problem[pair["id"]].append(pair)
    for cid,r in gp.items():
        assert int(r["n_pairs_found"])==sum(int(p["found"]) for p in by_problem[cid])
        assert int(r["n_pairs"])==len(by_problem[cid])
    vals=lambda name:np.array([float(r[name]) for r in rows])
    gvals=lambda name:np.array([float(gp[r["id"]][name]) for r in rows])
    p,p1,phi,phi0,d=(vals(k) for k in ("p0","p1","phi256","phi0","n_vars"))
    g=(gvals("n_pairs_found")>0).astype(float)
    has_hits=gvals("has_hits")>0
    n_pairs=gvals("n_pairs"); n_failed=gvals("n_pairs_all_failed")
    controls=[vals(k) for k in ("n_ineq","n_checks","n_eq","dsl_len")]
    out={"n":n,"G1":int(g.sum()),"with_hits":int(has_hits.sum()),
        "pair_counts":dict(pairs=len(pairs),excluded=int(gvals("n_pairs_excluded").sum()),
             all_failed=int(n_failed.sum()),problems_with_all_failed_pairs=int((n_failed>0).sum()),
             G0_problems_with_all_failed_pairs=int(((g==0)&(n_failed>0)).sum()),
             n_starts=int(gvals("n_starts").sum()),n_failed=int(gvals("n_failed").sum())),
        "strata_all":strata_summary(d,g,p),
        "strata_with_hits":strata_summary(d[has_hits],g[has_hits],p[has_hits]),
        "stratified_permutation":strat_perm(d,g,p),
        "stratified_permutation_with_hits":strat_perm(d[has_hits],g[has_hits],p[has_hits]),
        "correlations":{}}
    for name,x,y in (("G_phi0",g,phi0),("G_phi256",g,phi),("G_p0",g,p),("G_p1",g,p1),
                     ("G_n_pairs",g,n_pairs),("G_n_vars",g,d),("G_n_points",g,gvals("n_points"))):
        out["correlations"][name]=a.stat(lambda ii:a.rho(x[ii],y[ii]),n)
    for name,cov in (("d",[]),("d_counts",controls),("d_counts_phi",controls+[phi]),
                     ("d_counts_phi_pair_effort",controls+[phi,n_pairs,n_failed])):
        out["correlations"]["G_p1_partial_"+name]=a.stat(
            lambda ii:a.partial(g[ii],p1[ii],d[ii],[z[ii] for z in cov]),n)
    out["sensitivity"]={}
    for name,mask in (("has_hits",has_hits),("no_pair_all_failed",n_failed==0),
                      ("at_least_100_starts_both",(vals("n0")>=100)&(vals("n1")>=100))):
        ii=np.where(mask)[0]
        out["sensitivity"][name]=dict(n=len(ii),G1=int(g[ii].sum()),
            partial_G_p1=a.partial(g[ii],p1[ii],d[ii],[z[ii] for z in controls+[phi,n_pairs]]))
    wr=a.csvread(a.OUT/"ghost-witnesses.csv")
    out["witness_based_indicators"]={}
    for name,rule in (("G_hp",lambda r:r["hp_pass"]=="True"),
                      ("G_within_box",lambda r:r["within_box"]=="True"),
                      ("G_hp_within_box",lambda r:r["hp_pass"]=="True" and r["within_box"]=="True")):
        included={r["id"] for r in wr if rule(r)}
        gi=np.array([float(r["id"] in included) for r in rows])
        out["witness_based_indicators"][name]=dict(n1=int(gi.sum()),rho_p0=a.rho(gi,p),
            partial_p1=a.partial(gi,p1,d,controls+[phi,n_pairs]),strat_perm=strat_perm(d,gi,p))
    # Fully documented logit transform. Do not call this an exact reproduction
    # of score.md, which does not specify its transform at p=0 or 1.
    y=logit((vals("h0")+.5)/(vals("n0")+1))
    r2={}
    for name,x in (("d_linear",d[:,None]),("d_linear_G",np.column_stack([d,g])),
                   ("d_linear_phi0",np.column_stack([d,phi0])),("d_linear_G_phi0",np.column_stack([d,g,phi0]))):
        xx=np.column_stack([np.ones(n),x]); pred=xx@np.linalg.lstsq(xx,y,rcond=None)[0]
        r2[name]=float(1-np.sum((y-pred)**2)/np.sum((y-y.mean())**2))
    out["in_sample_logit_Jeffreys_R2"]=r2
    # Human uncertainty is at the problem level, stratified by contest.
    hout={}
    for contest in ("all","AIME","HMMT","within_contest"):
        ii=np.array([i for i,r in enumerate(rows) if r["human"] and (contest in ("all","within_contest") or r["contest"]==contest)])
        h=np.array([float(rows[i]["human"]) for i in ii]); gg=g[ii]
        cc=np.array([rows[i]["contest"] for i in ii]); groups=[np.where(cc==c)[0] for c in sorted(set(cc))]
        if contest=="within_contest":
            fun=lambda jj:a.corr(a.within_ranks(gg[jj],cc[jj]),a.within_ranks(h[jj],cc[jj]))
            pfun=lambda jj:a.corr(a.within_ranks(gg[jj],cc[jj]),a.within_ranks(p[ii][jj],cc[jj]))
        else:fun=lambda jj:a.rho(gg[jj],h[jj])
        if contest!="within_contest":pfun=lambda jj:a.rho(gg[jj],p[ii][jj])
        hout[contest]=a.stat(fun,len(ii),groups)
        hout[contest]["G1"]=int(gg.sum())
        hout[contest]["G_p0_same_cases"]=a.stat(pfun,len(ii),groups)
        hout[contest]["abs_rho_G_p_minus_abs_rho_G_human"]=a.stat(
            lambda jj:abs(pfun(jj))-abs(fun(jj)),len(ii),groups)
    out["human_G"]=hout
    base=np.column_stack([a.dcats(d)]+[vals(k) for k in ("n_ineq","n_checks","n_eq")]+[np.log(vals("dsl_len"))])
    models={"d":a.dcats(d),"d_G":np.column_stack([a.dcats(d),g]),
            "d_phi":np.column_stack([a.dcats(d),phi]),"d_phi_G":np.column_stack([a.dcats(d),phi,g]),
            "counts":base,"counts_G":np.column_stack([base,g]),
            "counts_phi":np.column_stack([base,phi]),"counts_phi_G":np.column_stack([base,phi,g]),
            "counts_phi_G_interaction":np.column_stack([base,phi,g,phi*g])}
    preds={m:np.zeros((10,n)) for m in models}
    for repeat in range(10):
        order=np.random.default_rng([1402303,repeat]).permutation(n)
        for test in np.array_split(order,5):
            train=np.setdiff1d(np.arange(n),test)
            for name,x in models.items():
                preds[name][repeat,test]=a.logistic_predict(x[train],p[train],x[test])
    losses={m:-p1[None,:]*np.log(v)-(1-p1[None,:])*np.log1p(-v) for m,v in preds.items()}
    cv={m:dict(log_loss=float(losses[m].mean()),rmse=float(np.sqrt(np.mean((v-p1[None,:])**2)))) for m,v in preds.items()}
    for old,new in (("d","d_G"),("d_phi","d_phi_G"),("counts","counts_G"),
                    ("counts_phi","counts_phi_G"),("counts","counts_phi_G"),
                    ("counts_phi_G","counts_phi_G_interaction")):
        diff=(losses[new]-losses[old]).mean(axis=0)
        cv[f"{new}_minus_{old}"]=dict(log_loss_delta=float(diff.mean()),
            ci95_descriptive=a.boot_stat(lambda ii:float(diff[ii].mean()),n))
    out["cv"]=cv
    out["four_groups"]=[]
    for gg in (0,1):
        for low in (False,True):
            m=(g==gg)&((phi<.5)==low)
            out["four_groups"].append(dict(G=gg,phi256_lt_half=low,n=int(m.sum()),
                median_p0=float(np.median(p[m])),median_p1=float(np.median(p1[m])),median_d=float(np.median(d[m]))))
    counter=[]
    for i,r in enumerate(rows):
        reason=[]
        if g[i]==0 and phi[i]>=.95 and p[i]<.3:reason.append("G0_phi256_ge.95_p0_lt.3")
        if g[i]==1 and p[i]>=.9:reason.append("G1_p0_ge.9")
        if reason:counter.append(dict(id=r["id"],G=int(g[i]),phi256=phi[i],p0=p[i],p1=p1[i],n_vars=int(d[i]),reason=";".join(reason)))
    a.csvwrite("ghost-counterexamples.csv",counter)
    out["counterexamples"]=dict(G0_phi_ge95_low_p=sum(r["G"]==0 for r in counter),G1_p_ge90=sum(r["G"]==1 for r in counter))
    cvrows=[]
    for i,r in enumerate(rows):
        row=dict(id=r["id"],G=int(g[i]),p0=p[i],p1=p1[i],phi256=phi[i],n_pairs=int(n_pairs[i]))
        for m in models:
            row[f"pred_{m}"]=float(preds[m][:,i].mean());row[f"loss_{m}"]=float(losses[m][:,i].mean())
        cvrows.append(row)
    a.csvwrite("ghost-cv.csv",cvrows)
    out["seconds"]=time.monotonic()-started
    a.dump("ghost-stats.json",out)
    a.dump("ghost-manifest.json",dict(inputs={str(p.relative_to(a.ROOT)):a.sha(p) for p in (GP,PP,a.OUT/"features.csv",a.OUT/"audit.py",a.OUT/"protocol.md")},code_sha256=a.sha(__file__)))
    print(json.dumps(a.clean(out),indent=2),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("command",choices=("witnesses","stats"))
    globals()[parser.parse_args().command]()
