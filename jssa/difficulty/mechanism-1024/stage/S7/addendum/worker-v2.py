"""Measured one-sided Jacobians plus source-branch inventory and W3 row reversions."""
from common import *
import ast
import time
from mpmath import mp
import helpers as h
from measure import spectrum, kind
from geosolver.engine.standard.refinement.mpmath_refiner import _smooth_zero_constraint_residuals, _zero_constraint_plans
from geosolver.engine.standard.problem.positive_radius_contacts import positive_radius_contact_sources
from geosolver.engine.standard.problem.tangency_contacts import contact_tangency_source, distance_contact_sources

def num(x):
    text = h.num(x, 200)
    return text if 'e' in text else text+'e+0'

def matrix_json(a):
    return [[num(a[i,j]) for j in range(a.cols)] for i in range(a.rows)]

def matrix(values, columns):
    return mp.matrix([[mp.mpf(x) for x in row] for row in values]) if values else mp.matrix(0, columns)

def stats(a):
    values, active, zeros, error = spectrum(a)
    return dict(sigma=num(values[0]), singular_values=list(map(num, values)),
                classification=kind(values[0]), nonzero_rows=active, dimension_zero_count=zeros,
                svd_reconstruction_error=num(error))

def inventory(bundle, point, old):
    construction = tuple((c.name, c.expr) for c in bundle.spec.construction)
    eq = tuple(zip(bundle.spec.constraints, map(str, bundle.targets), strict=True))
    plans = _zero_constraint_plans(tuple(bundle.spec.constraints), tuple(bundle.targets))
    contacts = distance_contact_sources(construction, eq)
    radius = positive_radius_contact_sources(tuple(bundle.var_names), construction, eq)
    tangents = {r['bundle_index']: t for t in old['tangencies'] for r in old['layouts']['raw']
                if r['source']+' = '+r['target'] == t['condition']}
    # Tangencies are indexed by original DSL conditions; AST-equivalent mapping handles formatting.
    from measure import key
    tangents = {}
    for t in old['tangencies']:
        candidates = [i for i,(lhs,rhs) in enumerate(eq)
                      if key(lhs)==key(t['condition'].split(' = ')[0]) and key(rhs)==key(t['condition'].split(' = ')[1])]
        assert len(candidates)==1
        tangents[candidates[0]]=t
    base, raw, changes = [], [], []
    fallback = old['base_frozen_original_fallback']
    for i,(lhs,rhs) in enumerate(eq):
        item = dict(bundle_index=i, condition=f'{lhs} = {rhs}', type='original', expressions=[f'({lhs})-({rhs})'])
        rawitem = dict(item)
        if i in tangents:
            rawitem.update(type='tangency_T1_'+tangents[i]['branch'], t1_descriptor=tangents[i])
        raw.append(rawitem)
        if not fallback:
            if i in contacts:
                item.update(type='distance_radius_contact', expressions=[contacts[i]])
            elif i in plans:
                k, (left, right) = plans[i]
                ctx = h.context(bundle, point, [left, right], 200)
                a,b = [h.safe_eval_expr_hp(e,ctx) for e in (left,right)]
                if k == 'distance' and all(hasattr(o,'x') and hasattr(o,'y') for o in (a,b)):
                    item.update(type='distance_zero_coordinates', expressions=[f'({left}).{axis}-({right}).{axis}' for axis in ('x','y')])
                elif k == 'istangent':
                    contact = contact_tangency_source(left,right,construction,eq)
                    a,b = getattr(a,'circle',a),getattr(b,'circle',b)
                    if contact is not None:
                        cc = all(hasattr(o,'radius') for o in (a,b))
                        item.update(type='contact_circle_circle' if cc else 'contact_line_circle', expressions=[contact])
                    elif all(hasattr(o,'radius') for o in (a,b)):
                        item.update(type='signed_tangency_circle_circle', expressions=['frozen signed_tangency('+left+','+right+')'])
                    elif (hasattr(a,'a') and hasattr(b,'radius')) or (hasattr(b,'a') and hasattr(a,'radius')):
                        line,circle = (left,right) if hasattr(a,'a') else (right,left)
                        item.update(type='signed_tangency_line_circle', expressions=[f'signed_distance({line},Center({circle}))**2-Radius({circle})**2'])
        base.append(item)
        if item['type'] != 'original':
            changes.append(item)
    if not fallback:
        for expr in radius:
            item = dict(bundle_index=None, condition='positive radius necessary consequence', type='radius_auxiliary', expressions=[expr])
            base.append(item); changes.append(item)
    offset=0
    for item in base:
        size=len(item['expressions'])
        item['base_rows'] = list(range(offset,offset+size));offset+=size
    assert offset==len(old['layouts']['base'])
    # Validate the source-branch classification against frozen's actual marker behavior.
    markers=[mp.mpf(-10000000-i) for i in range(len(eq))]
    probe=_smooth_zero_constraint_residuals(bundle=bundle,point=point,dps=200,residuals=markers)
    assert len(probe)==offset
    expected_fallback=bool(plans or contacts or radius) and probe==markers
    assert expected_fallback==fallback
    for item in base:
        if item['type']=='original':
            assert probe[item['base_rows'][0]]==markers[item['bundle_index']]
        else:
            assert all(probe[j] not in markers for j in item['base_rows'])
    return dict(base=base,raw=raw,changes=changes,base_types=sorted({x['type'] for x in changes}),
                raw_types=sorted({x['type'] for x in raw if x['type']!='original'}),base_fallback=fallback)

def calculate(key,cpu):
    os.sched_setaffinity(0,{int(cpu)})
    started=time.monotonic()
    manifest=load(OUT/'pre-run-hashes.json')
    amendment=load(OUT/'implementation-amendment.json')
    for p,digest in amendment['files'].items():
        assert sha(p)==digest,p
    # Full immutable-input verification is done by driver; per-worker verify own inputs and code.
    for p,digest in manifest['files'].items():
        path=Path(p)
        if path.parent==OUT or key in path.parts or path.name==key+'.json' or path.name in {'helpers.py','measure.py'}:
            assert sha(path)==digest,p
    frozen_check()
    protocol=load(OUT/'protocol.json')
    item=load(S7/'inputs'/f'{key}.json')
    ref=load(S7/'results'/key/'reference.json')
    old=load(S7/'results'/key/'sigma-details.json')
    assert ref['status']=='ok'
    bundle=h.load_problem_bundle(h.GeometryProblem.model_validate(item['dsl']).engine_document())
    evaluator=h.build_ir_evaluator(bundle)
    with mp.workdps(200),h.high_precision_mode():
        point=[mp.mpf(v) for v in ref['coordinates']]
        assert list(bundle.var_names)==ref['var_names']==old['var_names']
        inv=inventory(bundle,point,old)
        tangent_by_index={r['bundle_index']:r['t1_descriptor'] for r in inv['raw'] if 't1_descriptor' in r}
        def residual(at,mode):
            ev=evaluator.evaluate_hp_residual(at,precision=200)
            assert ev.is_finite
            values=list(ev.residual_vector)
            if mode=='base':
                values=_smooth_zero_constraint_residuals(bundle=bundle,point=at,dps=200,residuals=values)
            else:
                for i,t in tangent_by_index.items():
                    values[i]=h.t1(bundle,at,t)
            assert len(values)==len(old['layouts'][mode])
            result=[v/mp.mpf(r['fixed_divisor']) for v,r in zip(values,old['layouts'][mode],strict=True)]
            assert all(mp.isfinite(v) for v in result)
            return result
        samples=[]
        for exponent in protocol['step_exponents']:
            m,n=len(old['layouts']['raw']),len(point)
            jp,jm=mp.matrix(m,n),mp.matrix(m,n)
            r0=residual(point,'raw')
            for j,x in enumerate(point):
                step=mp.mpf(10)**(-exponent)*max(1,abs(x))
                plus,minus=list(point),list(point)
                plus[j],minus[j]=x+step,x-step
                rp,rm=residual(plus,'raw'),residual(minus,'raw')
                for i in range(m):
                    jp[i,j]=(rp[i]-r0[i])/step
                    jm[i,j]=(r0[i]-rm[i])/step
            jc=(jp+jm)/2
            gap=mp.norm(jp-jm)/max(1,mp.norm(jp),mp.norm(jm))
            pstats,mstats,cstats=stats(jp),stats(jm),stats(jc)
            non=mp.mpf(pstats['sigma'])>mp.mpf('1e-10') or mp.mpf(mstats['sigma'])>mp.mpf('1e-10')
            mismatch=gap>mp.mpf('1e-20')
            both=mp.mpf(pstats['sigma'])<mp.mpf('1e-60') and mp.mpf(mstats['sigma'])<mp.mpf('1e-60')
            judgment='微分不能' if non or mismatch else ('特異' if both else '不定')
            saved=next(s for s in old['modes']['raw']['samples'] if s['step_exponent']==exponent)
            oldjac=matrix(saved['jacobian'],n)
            central_error=mp.norm(jc-oldjac)/max(1,mp.norm(oldjac))
            assert central_error<mp.mpf('1e-120'),num(central_error)
            rows=[]
            for i in range(m):
                pg=mp.sqrt(mp.fsum((jp[i,j]-jm[i,j])**2 for j in range(n)))
                denom=max(1,mp.sqrt(mp.fsum(jp[i,j]**2 for j in range(n))),mp.sqrt(mp.fsum(jm[i,j]**2 for j in range(n))))
                if pg/denom>mp.mpf('1e-20'):
                    rows.append(dict(raw_row=i,bundle_index=old['layouts']['raw'][i]['bundle_index'],
                                     condition=inv['raw'][i]['condition'],normalized_gap=num(pg/denom),
                                     affected_variables=[bundle.var_names[j] for j in range(n) if abs(jp[i,j]-jm[i,j])>mp.mpf('1e-20')]))
            sample=dict(step_exponent=exponent,plus=pstats,minus=mstats,central=cstats,normalized_matrix_gap=num(gap),
                        classification=judgment,reason=dict(one_side_nonsingular=non,matrix_mismatch=mismatch,both_singular=both),
                        stage1_central_relative_error=num(central_error),nonsmooth_rows=rows,
                        jacobian_plus=matrix_json(jp),jacobian_minus=matrix_json(jm),jacobian_central=matrix_json(jc))
            if key in protocol['w3']:
                # Recompute base centrally instead of merely trusting the archived matrix.
                jb=mp.matrix(len(old['layouts']['base']),n)
                for j,x in enumerate(point):
                    step=mp.mpf(10)**(-exponent)*max(1,abs(x))
                    plus,minus=list(point),list(point)
                    plus[j],minus[j]=x+step,x-step
                    rp,rm=residual(plus,'base'),residual(minus,'base')
                    for i,(a,b) in enumerate(zip(rp,rm,strict=True)):
                        jb[i,j]=(a-b)/(2*step)
                oldbase=next(s for s in old['modes']['base']['samples'] if s['step_exponent']==exponent)
                assert mp.norm(jb-matrix(oldbase['jacobian'],n))/max(1,mp.norm(jb))<mp.mpf('1e-120')
                reversions=[]
                for change in inv['changes']:
                    removed=set(change['base_rows'])
                    hybrid=[[jb[i,j] for j in range(n)] for i in range(jb.rows) if i not in removed]
                    ri=change['bundle_index']
                    if ri is not None:
                        hybrid.append([jc[ri,j] for j in range(n)])
                    reversions.append(dict(change=change,rows=len(hybrid),**stats(mp.matrix(hybrid))))
                sample.update(base=stats(jb),base_jacobian=matrix_json(jb),single_condition_reversions=reversions)
            samples.append(sample)
        classifications=[s['classification'] for s in samples]
        result=dict(case_id=key,status='ok',precision_dps=200,m_raw=len(old['layouts']['raw']),m_base=len(old['layouts']['base']),n=len(point),
                    var_names=list(bundle.var_names),inventory=inv,base_type_count=len(inv['base_types']),
                    combined_type_count=len(set(inv['base_types']+inv['raw_types'])),samples=samples,
                    classification=classifications[0] if len(set(classifications))==1 else '不定',width_classifications=classifications,
                    stage_2_executed=False,elapsed_seconds=time.monotonic()-started,pre_run_manifest_sha256=sha(OUT/'pre-run-hashes.json'))
    result['accessed_files']={p:sha(p) for p in sorted(READS) if Path(p).is_file() and not Path(p).is_relative_to(OUT)}
    path=OUT/'results'/f'{key}.json'
    assert not path.exists()
    save(path,result)
    print(key,result['classification'],f'{result["elapsed_seconds"]:.2f}s',flush=True)

if __name__=='__main__':
    calculate(*sys.argv[1:3])
