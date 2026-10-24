"""Stage (1) only. Frozen residuals, with raw tangency-only T1 substitution."""
import ast
from mpmath import mp
import helpers as h
from geosolver.engine.standard.refinement.mpmath_refiner import _smooth_zero_constraint_residuals, _zero_constraint_plans
from geosolver.engine.standard.problem.positive_radius_contacts import positive_radius_contact_sources
from geosolver.engine.standard.evaluation.high_precision_expressions import evaluate_target_high_precision
from geosolver.engine.standard.evaluation.snapshots import evaluate_scalar_expression


def key(s):
    return ast.dump(ast.parse(str(s), mode='eval'), include_attributes=False)


def kind(v):
    return '特異' if v < mp.mpf('1e-60') else ('非特異' if v > mp.mpf('1e-10') else '不定')


def spectrum(jac):
    n = jac.cols
    active = [i for i in range(jac.rows) if any(jac[i,j] != 0 for j in range(n))]
    if not active:
        return [mp.mpf(0)]*n, 0, n, mp.mpf(0)
    a = mp.matrix([[jac[i,j] for j in range(n)] for i in active])
    u,s,v = mp.svd_r(a, full_matrices=False)
    error = mp.norm(a-u*mp.diag(s)*v)/max(1,mp.norm(a))
    assert error < mp.mpf('1e-170')
    zeros = max(0,n-len(active))
    values = sorted([mp.mpf(0)]*zeros+list(s))
    assert len(values) == n
    return values,len(active),zeros,error


def measure(item,bundle,evaluator,reference,scales,points):
    with mp.workdps(200),h.high_precision_mode():
        point = [mp.mpf(s) for s in reference['coordinates']]
        construction = tuple((c.name,c.expr) for c in bundle.spec.construction)
        equalities = tuple(zip(bundle.spec.constraints,map(str,bundle.targets),strict=True))
        plans = _zero_constraint_plans(tuple(bundle.spec.constraints),tuple(bundle.targets))
        contacts = h.distance_contact_sources(construction,equalities)
        radius = positive_radius_contact_sources(tuple(bundle.var_names),construction,equalities)
        tangencies = h.inventory(item,bundle)
        tangent_by_index = {}
        for row in tangencies:
            original = item['dsl']['conditions'][row['index']]
            found = [i for i,(a,b) in enumerate(equalities) if key(a)==key(original['left']) and key(b)==key(original['right'])]
            assert len(found)==1,(original,found)
            a,b = h.objects(bundle,point,row,200)
            if hasattr(a,'radius') and hasattr(b,'radius'):
                d = a.center.distance_to(b.center)
                row['branch'] = 'outer' if abs(d-a.radius-b.radius)<=abs(d-abs(a.radius-b.radius)) else 'inner'
            else:
                row['branch'] = 'line_circle'
            tangent_by_index[found[0]]=row
        assert {i for i,(k,_) in plans.items() if k=='istangent'} <= set(tangent_by_index)
        # Original rows use the S1 rule on the original IR; AST comparison
        # preserves mappings through harmless compiler parenthesization.
        original=[]
        for i,(lhs,rhs) in enumerate(equalities):
            old=[j for j,(a,b) in enumerate(zip(scales['constraints'],scales['targets'])) if key(a)==key(lhs) and key(b)==key(rhs)]
            assert len(old)<=1
            original.append(dict(bundle_index=i,source=lhs,target=rhs,kind='original',scale_index=old[0] if old else None))
        base=[]
        # Probe the actual frozen function with markers to distinguish its
        # all-original fallback, including fallbacks with unchanged row count.
        markers=[mp.mpf(-10000000-i) for i in range(len(original))]
        probe=_smooth_zero_constraint_residuals(bundle=bundle,point=point,dps=200,residuals=markers)
        fallback=bool(plans or contacts or radius) and probe==markers
        if fallback:
            base=[dict(r) for r in original]
        else:
            for i,row in enumerate(original):
                if i not in contacts and i in plans and plans[i][0]=='distance':
                    left,right=plans[i][1]
                    ctx=h.context(bundle,point,[left,right],200)
                    objects=[h.safe_eval_expr_hp(e,ctx) for e in (left,right)]
                    if all(hasattr(o,'x') and hasattr(o,'y') for o in objects):
                        for axis in ('x','y'):
                            base.append(row|dict(kind='distance_coordinate',source=f'({left}).{axis}-({right}).{axis}',target='0'))
                        continue
                base.append(dict(row))
            base.extend(dict(kind='radius_auxiliary',source=s,target='0',scale_index=None,bundle_index=None) for s in radius)
        assert len(base)==len(probe)
        raw=[dict(r)|dict(kind='tangency_T1' if i in tangent_by_index else 'original') for i,r in enumerate(original)]
        layouts={'base':base,'raw':raw}
        with mp.workdps(700):
            for layout in layouts.values():
                for row in layout:
                    j=row['scale_index']
                    divisor=mp.mpf(scales['scales'][j]) if j is not None else mp.mpf(1)
                    count=0
                    if j is None:
                        for start in points:
                            try:
                                ctx=h.context(bundle,start,[row['source'],row['target']],700)
                                lhs=mp.mpf(evaluate_scalar_expression(row['source'],ctx,constants_only=True))
                                rhs=evaluate_target_high_precision(row['target'],ctx,precision=700,index=0)
                                if mp.isfinite(lhs) and mp.isfinite(rhs):
                                    divisor=max(divisor,abs(lhs),abs(rhs));count+=1
                            except TimeoutError:
                                raise
                            except Exception:
                                pass
                    row.update(fixed_divisor=h.num(divisor,710),divisor_source='original_IR_first_search' if j is not None else 'new_row_first_search_same_rule',finite_initial_count=count if j is None else scales['finite_counts'][j])
        def residual(at,mode):
            ev=evaluator.evaluate_hp_residual(at,precision=200)
            assert ev.is_finite
            values=list(ev.residual_vector)
            if mode=='base':
                values=_smooth_zero_constraint_residuals(bundle=bundle,point=at,dps=200,residuals=values)
            else:
                for i,row in tangent_by_index.items():
                    values[i]=h.t1(bundle,at,row)
            assert len(values)==len(layouts[mode])
            assert all(mp.isfinite(v) for v in values)
            return [v/mp.mpf(r['fixed_divisor']) for v,r in zip(values,layouts[mode],strict=True)]
        details=dict(var_names=list(bundle.var_names),tangencies=tangencies,base_frozen_original_fallback=fallback,layouts=layouts,modes={})
        summary=dict(has_tangency=bool(tangencies),n_variables=len(point),base_rows=len(base),raw_rows=len(raw),base_frozen_original_fallback=fallback)
        for mode in ('base','raw'):
            samples=[]
            minima=[]
            for exponent in (70,60):
                jac=mp.matrix(len(layouts[mode]),len(point))
                for j,x in enumerate(point):
                    step=mp.mpf(10)**(-exponent)*max(1,abs(x))
                    plus,minus=list(point),list(point)
                    plus[j],minus[j]=x+step,x-step
                    rp,rm=residual(plus,mode),residual(minus,mode)
                    for i,(a,b) in enumerate(zip(rp,rm,strict=True)):
                        jac[i,j]=(a-b)/(2*step)
                singular,active,zeros,error=spectrum(jac)
                minima.append(singular[0])
                samples.append(dict(step_exponent=exponent,singular_values=[h.num(v) for v in singular],nonzero_rows=active,dimension_zero_count=zeros,svd_reconstruction_error=h.num(error),jacobian=[[h.num(jac[i,j]) for j in range(jac.cols)] for i in range(jac.rows)]))
            a,b=minima
            relative=abs(a-b)/max(abs(a),abs(b)) if a or b else mp.mpf(0)
            states=[kind(v) for v in minima]
            judgment=states[0] if states[0]==states[1] else '不定'
            details['modes'][mode]=dict(samples=samples,judgment=judgment,width_classifications=states,min_relative_difference=h.num(relative),min_absolute_difference=h.num(abs(a-b)),min_relative_agreement_1e40=relative<=mp.mpf('1e-40'))
            summary.update({f'sigma_{mode}':h.num(a),f'sigma_{mode}_check':h.num(b),f'{mode}_judgment':judgment,f'{mode}_width_agreement':states[0]==states[1],f'{mode}_relative_agreement':relative<=mp.mpf('1e-40')})
        summary['type']=f"base={summary['base_judgment']};raw={summary['raw_judgment']};tangency={int(summary['has_tangency'])}"
        summary['W3_target']=summary['raw_judgment']=='特異' and summary['base_judgment']=='非特異' and not summary['has_tangency']
        summary['reason']='両幅で同じ閾値区分' if summary['base_width_agreement'] and summary['raw_width_agreement'] else '幅間で閾値区分が異なるため不定'
        return details,summary
