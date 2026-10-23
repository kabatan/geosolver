"""Post-run checks; no edits to solver or previous experimental records."""
from __future__ import annotations

import csv
import gzip
import itertools
import json
import math
import sys
from pathlib import Path

import coordinates as C
import experiment as E
import analyze as A


def equivalence():
    """Materialize dependencies before scalar comparisons (audit v2)."""
    import numpy as np
    from mpmath import mp
    from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    rows=[]
    for i,inp in enumerate(E.selected()):
        _,b,e=E.build(inp['dsl']);box=np.asarray(infer_problem_bounds(b))
        rng=np.random.default_rng([C.SELECT_SEED,i]);xs=[box[:,0]+rng.random(len(box))*(box[:,1]-box[:,0]) for _ in range(3)]
        for v in C.variants():
            dsl=C.transform(inp['dsl'],v);_,bb,ee=E.build(dsl)
            originals=[str(c[k]) for c in inp['dsl']['conditions'] for k in ('left','right') if k in c]+[inp['dsl']['target']]
            altered=[str(c[k]) for c in dsl['conditions'] for k in ('left','right') if k in c]+[dsl['target']]
            ncompare=0;neither=0;onesided=[];mismatches=[];maxerr=mp.mpf(0);guarddiff=0
            with mp.workdps(80),high_precision_mode():
                for x in xs:
                    vals=[mp.mpf(repr(float(z))) for z in x]
                    a=e.evaluation_store.get(vals);z=ee.evaluation_store.get(vals)
                    for aa,zz in zip(originals,altered,strict=True):
                        vv=[];errors=[]
                        for snap,src in [(a,aa),(z,zz)]:
                            try:
                                snap.for_expressions([src]);value=snap.evaluate(src)
                                if not mp.isfinite(value):raise ValueError('nonfinite')
                                vv.append(value);errors.append(None)
                            except Exception as ex:vv.append(None);errors.append(type(ex).__name__)
                        if vv[0] is None and vv[1] is None:neither+=1;continue
                        if any(q is None for q in vv):onesided.append(dict(a=aa,z=zz,errors=errors));continue
                        err=abs(vv[0]-vv[1])/max(1,abs(vv[0]));maxerr=max(maxerr,err);ncompare+=1
                        if err>mp.mpf('1e-45'):mismatches.append(dict(a=aa,z=zz,av=str(vv[0]),zv=str(vv[1]),error=str(err)))
                    ga=e.evaluate_hp_hard_feasibility(vals,precision=80).hard_feasible
                    gz=ee.evaluate_hp_hard_feasibility(vals,precision=80).hard_feasible
                    guarddiff+=ga!=gz
            rows.append(dict(id=inp['id'],variant=v['name'],comparisons=ncompare,both_undefined=neither,one_sided_errors=onesided[:8],
                             mismatches=mismatches[:8],max_relative_error=float(maxerr),hard_feasibility_differences=guarddiff,
                             base_box=box.tolist(),variant_box=[list(p) for p in infer_problem_bounds(bb)],
                             base_residual_count=len(b.spec.constraints),variant_residual_count=len(bb.spec.constraints)))
        print(json.dumps(dict(equivalence_complete=inp['id'],done=i+1)),flush=True)
    E.save(C.BASE/'equivalence-audit-v2.json',dict(source=E.source_check(),precision=80,points=3,seed=C.SELECT_SEED,
         correction='Initial audit used EvaluationSnapshot.evaluate before materialization for scalar equations; its affine point checks were materialized. This audit materializes each expression dependency first. No solver result is changed or replaced.',
         rows=rows,passed=all(not r['one_sided_errors'] and not r['mismatches'] for r in rows)))
    assert all(not r['one_sided_errors'] and not r['mismatches'] for r in rows),'equivalence mismatch'


def figures(stage):
    """Re-evaluate every distinct accepted coordinate tuple in original units."""
    from mpmath import mp
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    summary=[];allfigs=[]
    allrows=A.rows(stage)
    for inp in E.selected():
        _,b,e=E.build(inp['dsl']);fr=C.Frame(inp['dsl'],next(v for v in C.variants() if v['name']=='scale_+0'));fr.transform()
        names=[x['name'] for x in inp['dsl']['constructions'] if fr.types[x['name']]=='point']
        for r in [rr for rr in allrows if rr['id']==inp['id']]:
            raw=r.get('raw_path')
            if not raw:continue
            with gzip.open(raw,'rt') as f:artifact=json.load(f)
            accepted=[c for c in artifact['candidate_records'] if c.get('accepted')]
            seen=set();valid=0;errors=[];forms=[];values=[]
            for cand in accepted:
                coords=tuple(cand['x_hp'])
                if coords in seen:continue
                seen.add(coords)
                try:
                    with mp.workdps(80),high_precision_mode():
                        vals=[mp.mpf(z) for z in coords]
                        residual=e.evaluate_hp_residual(vals,precision=80)
                        feasible=e.evaluate_hp_hard_feasibility(vals,precision=80).hard_feasible
                        ans=e.evaluate_answer_hp(vals,precision=80).answer_hp
                        snap=e.evaluation_store.get(vals);ctx=snap.materialize(names)
                    # Plot serialization is outside the guarded HP computation.
                    points={n:[float(ctx[n].x),float(ctx[n].y)] for n in names}
                    eq_ok=bool(residual.is_finite and residual.residual_norm_hp<mp.mpf('1e-10'))
                    valid+=eq_ok and feasible
                    lengths=[math.dist(points[a],points[z]) for a,z in itertools.combinations(names,2)]
                    diameter=max(lengths,default=0)
                    normalized=[x/diameter for x in lengths] if diameter else lengths
                    # Relative geometry plus original diameter: distinguish size as well as shape.
                    signature=C.digest([round(x,6) for x in normalized]+[float(f'{diameter:.7g}')])
                    forms.append(signature);values.append(float(ans) if ans is not None else None)
                    fig=dict(id=r['id'],variant=r['variant'],seed=r['seed'],budget=r['budget'],stage=stage,
                             signature=signature,names=names,points=points,diameter=diameter,distances=lengths,
                             normalized_distances=normalized,answer=float(ans) if ans is not None else None,
                             original_residual=str(residual.residual_norm_hp),original_hard_feasible=bool(feasible),
                             original_equations_ok=eq_ok,candidate_uid=cand.get('candidate_uid'),x_hp=list(coords),raw_path=raw)
                    allfigs.append(fig)
                except Exception as ex:errors.append(dict(error=type(ex).__name__,message=str(ex)[:250]))
            summary.append(dict(id=r['id'],variant=r['variant'],seed=r['seed'],budget=r['budget'],stage=stage,
                 accepted_records=len(accepted),distinct_coordinates=len(seen),original_valid_witnesses=valid,
                 distinct_figures=len(set(forms)),figure_signatures=sorted(set(forms)),numeric_values=sorted(set(v for v in values if v is not None)),
                 errors=errors))
        print(json.dumps(dict(figures_complete=inp['id'],done=len(summary))),flush=True)
    dest=C.EXTERNAL/stage/'figures.json.gz';dest.parent.mkdir(parents=True,exist_ok=True)
    with gzip.open(dest,'wt') as f:json.dump(allfigs,f,ensure_ascii=False)
    E.save(C.BASE/f'{stage}-figures-summary.json',dict(source=E.source_check(),raw_figures=str(dest),figures=len(allfigs),rows=summary))
    A.csvsave(C.BASE/f'{stage}-figures.csv',summary,list(summary[0]) if summary else [])


if __name__=='__main__':
    if sys.argv[1]=='equivalence':equivalence()
    elif sys.argv[1]=='figures':figures(sys.argv[2])
    else:raise ValueError(sys.argv[1])
