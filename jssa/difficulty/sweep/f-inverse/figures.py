"""Substitute saved coordinates only; compare observed figures without another solve."""
from __future__ import annotations
import os
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.dont_write_bytecode=True
sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):
    os.environ[k]='1'
import argparse
import itertools
import json
import math
from collections import defaultdict
from mpmath import mp
from geosolver import GeometryProblem
from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
from geosolver.engine.standard.evaluation.high_precision_expressions import build_solution_context_high_precision
from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
from geosolver.runtime.integrity import source_tree_hash
from analyze import collect,load,save,write_csv

def signature_distance(a,b):
    if a['distance_names']!=b['distance_names']:return None
    x,y=a['distances'],b['distances']
    if not x:return None
    return max(abs(u-v) for u,v in zip(x,y))/max(1.,max(x),max(y))

def dedup_figures(figs,tolerance=1e-6):
    out=[]
    for f in figs:
        if all(signature_distance(f,o) is None or signature_distance(f,o)>tolerance for o in out):out.append(f)
    return out

def build_input(inp):
    dsl=load(HERE/inp['path']);b=load_problem_bundle(GeometryProblem.model_validate(dsl).engine_document())
    return dsl,b,build_ir_evaluator(b)

def evaluate_figure(bundle,evaluator,original_evaluator,candidate):
    with mp.workdps(80),high_precision_mode():
        values=[mp.mpf(v) for v in candidate['x_hp']]
        res=evaluator.evaluate_hp_residual(values,precision=80)
        hard=evaluator.evaluate_hp_hard_feasibility(values,precision=80,include_margins=False)
        ans=evaluator.evaluate_answer_hp(values,precision=80).answer_hp
        original=original_evaluator.evaluate_hp_residual(values,precision=80)
        original_ans=original_evaluator.evaluate_answer_hp(values,precision=80).answer_hp
        context=build_solution_context_high_precision(bundle.spec,list(bundle.var_names),values,bundle.base_context,80)
        points={}
        for c in bundle.spec.construction:
            obj=context.get(c.name)
            if hasattr(obj,'x') and hasattr(obj,'y'):
                x,y=float(obj.x),float(obj.y)
                if math.isfinite(x) and math.isfinite(y):points[c.name]=[x,y]
        pairs=list(itertools.combinations(sorted(points),2))
        distances=[math.dist(points[a],points[b]) for a,b in pairs]
        eq=float(res.residual_norm_hp);orig=float(original.residual_norm_hp)
        return dict(candidate_uid=candidate.get('candidate_uid'),candidate_id=candidate.get('candidate_id'),
            solver_accepted=bool(candidate.get('accepted')),stored_residual=candidate.get('residual_norm_hp'),
            residual_80dps=mp.nstr(res.residual_norm_hp,12),hard_feasible_80dps=hard.hard_feasible,
            hard_tags=list(hard.failure_tags),
            verified_numerically=bool(math.isfinite(eq) and eq<=1e-30 and hard.hard_feasible),
            original_residual_80dps=mp.nstr(original.residual_norm_hp,12),
            satisfies_original_equalities=bool(math.isfinite(orig) and orig<=1e-30),
            target_value=mp.nstr(ans,30) if ans is not None else None,
            original_target_value=mp.nstr(original_ans,30) if original_ans is not None else None,
            variables={name:mp.nstr(v,40) for name,v in zip(bundle.var_names,values)},
            points=points,distance_names=[a+'|'+b for a,b in pairs],distances=distances,
            diameter=max(distances,default=0.),minimum_distance=min(distances,default=0.))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ids',nargs='*');args=parser.parse_args()
    manifest,rows,results=collect();assert source_tree_hash()==manifest['source_hash']
    assert all(r['status']!='not_completed' for r in rows),'wait until all searches finish'
    groups=defaultdict(list)
    for inp in manifest['inputs']:groups[inp['id']].append(inp)
    all_run_figures=[];per_arm=[];structure=[];errors=[]
    for cid,inputs in groups.items():
        if args.ids and cid not in args.ids:continue
        baseline=next(i for i in inputs if i['arm']=='forward');base_dsl,base_bundle,base_ev=build_input(baseline)
        figures_by_arm={}
        for inp in inputs:
            dsl,bundle,evaluator=build_input(inp)
            assert bundle.var_names==base_bundle.var_names
            bounds=infer_problem_bounds(bundle)
            structure.append(dict(id=cid,group=inp['group'],arm=inp['arm'],variables=list(bundle.var_names),
                n_vars=len(bundle.var_names),n_equalities=len(bundle.spec.constraints),bounds=bounds,
                target=dsl['target'],constraints=list(bundle.spec.constraints)))
            run_figs=[]
            for seed in manifest['solver_seeds']:
                result=results[(cid,inp['arm'],seed)]
                candidates=result.get('diagnostics',{}).get('candidate_records',[])
                # Identical coordinates at displayed numerical precision need only one substitution.
                # Retain different answer branches even when coordinates round similarly.
                seen=set();figs=[]
                for c in candidates:
                    if not c.get('accepted'):continue
                    try:key=tuple(round(float(v),10) for v in c['x_hp'])
                    except Exception:key=tuple(c.get('x_hp',[]))
                    if key in seen:continue
                    seen.add(key)
                    try:
                        f=evaluate_figure(bundle,evaluator,base_ev,c)
                        f.update(id=cid,arm=inp['arm'],seed=seed)
                        figs.append(f)
                    except Exception as exc:
                        errors.append(dict(id=cid,arm=inp['arm'],seed=seed,candidate=c.get('candidate_uid'),error=repr(exc)))
                figs=dedup_figures(figs)
                rejected=[]
                for c in [c for c in candidates if not c.get('accepted')][:3]:
                    try:
                        f=evaluate_figure(bundle,evaluator,base_ev,c)
                        f.update(id=cid,arm=inp['arm'],seed=seed,
                                 refinement_status=c.get('refinement_status'))
                        rejected.append(f)
                    except Exception as exc:
                        rejected.append(dict(candidate_uid=c.get('candidate_uid'),
                            refinement_status=c.get('refinement_status'),error=repr(exc),
                            variables={n:v[:65] for n,v in zip(bundle.var_names,c.get('x_hp',[]))}))
                run_figs.extend(figs)
                all_run_figures.append(dict(id=cid,arm=inp['arm'],seed=seed,
                    solver_accepted_candidates=sum(c.get('accepted',False) for c in candidates),
                    unique_coordinate_candidates=len(seen),observed_figure_count=len(figs),
                    verified_figure_count=sum(f['verified_numerically'] for f in figs),
                    original_figure_count=sum(f['satisfies_original_equalities'] for f in figs),
                    figures=figs,rejected_examples=rejected))
            figures_by_arm[inp['arm']]=dedup_figures(run_figs)
        basefig=figures_by_arm['forward']
        for inp in inputs:
            figs=figures_by_arm[inp['arm']]
            novel=[]
            for f in figs:
                distances=[d for b in basefig if (d:=signature_distance(f,b)) is not None]
                nearest=min(distances) if distances else None
                f['nearest_forward_figure_distance']=nearest
                if nearest is not None and nearest>1e-6:novel.append(f)
            per_arm.append(dict(id=cid,group=inp['group'],arm=inp['arm'],figures_observed=len(figs),
                verified_figures=sum(f['verified_numerically'] for f in figs),
                original_equalities_figures=sum(f['satisfies_original_equalities'] for f in figs),
                novel_figures=len(novel),min_diameter=min((f['diameter'] for f in figs),default=None),
                max_diameter=max((f['diameter'] for f in figs),default=None)))
        print(cid,'figures',sum(len(f) for f in figures_by_arm.values()),flush=True)
    (HERE/'figures').mkdir(exist_ok=True)
    index=[]
    for cid in groups:
        subset=[r for r in all_run_figures if r['id']==cid]
        if not subset:continue
        path=HERE/'figures'/f'{cid}.json';save(path,subset)
        index.append(dict(id=cid,path=str(path.relative_to(HERE)),runs=len(subset),bytes=path.stat().st_size))
    save(HERE/'figure-index.json',index);save(HERE/'structure.json',structure)
    save(HERE/'figure-errors.json',errors);write_csv(HERE/'per-arm-figures.csv',per_arm)
    write_csv(HERE/'per-run-figures.csv',[{k:v for k,v in row.items() if k not in ('figures','rejected_examples')} for row in all_run_figures])
    print(json.dumps(dict(rows=len(all_run_figures),errors=len(errors))))

if __name__=='__main__':main()
