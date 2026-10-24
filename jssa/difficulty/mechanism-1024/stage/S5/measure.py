"""S4.12 measurement body extracted by build_reuse.py; S4 source hashes recorded."""
import json
from mpmath import mp
from geosolver.engine.standard.refinement.mpmath_refiner import _zero_constraint_plans, _smooth_zero_constraint_residuals
from geosolver.engine.standard.problem.positive_radius_contacts import positive_radius_contact_sources
from geosolver.engine.standard.evaluation.high_precision_expressions import evaluate_target_high_precision
from geosolver.engine.standard.evaluation.snapshots import evaluate_scalar_expression

def num(v):
    assert mp.isfinite(v)
    return mp.nstr(v,200,min_fixed=0,max_fixed=0) if v else '0.0e+0'

def spectrum(jac):
    m, n = jac.rows, jac.cols
    active = [i for i in range(m) if any(jac[i,j] != 0 for j in range(n))]
    a = mp.matrix([[jac[i,j] for j in range(n)] for i in active]) if active else None
    if not active:
        return [mp.mpf(0)] * n, 0, n, mp.mpf(0)
    u, singular, v = mp.svd_r(a, full_matrices=False)
    reconstruction = mp.norm(a - u * mp.diag(singular) * v) / max(1, mp.norm(a))
    assert reconstruction < mp.mpf('1e-170')
    zeros = max(0, n-len(active))
    values = sorted([mp.mpf(0)]*zeros + list(singular))
    assert len(values) == n and all(s >= 0 for s in values)
    return values, len(active), zeros, reconstruction


def measure(s4, item, reference, scales, initial_points, task):
    manifest = {'step_exponents':[70,60], 'agreement_relative_tolerance':'1e-40'}
    csv_rows=[]
    with mp.workdps(200), s4.high_precision_mode():
        bundle = s4.load_problem_bundle(s4.GeometryProblem.model_validate(item['dsl']).engine_document())
        evaluator = s4.build_ir_evaluator(bundle)
        assert list(bundle.var_names) == reference['var_names']
        point = [mp.mpf(s) for s in reference['coordinates']]
        assert len(point) > 0
        tangencies = s4.inventory(item, bundle)
        tangent_by_index = {}
        for row in tangencies:
            original = item['dsl']['conditions'][row['index']]
            found = [i for i,(lhs,rhs) in enumerate(zip(bundle.spec.constraints, bundle.targets))
                     if lhs == str(original['left']) and str(rhs) == str(original['right'])]
            assert len(found) == 1
            a,b = s4.objects(bundle, point, row, 200)
            if hasattr(a, 'radius') and hasattr(b, 'radius'):
                d = a.center.distance_to(b.center)
                row['branch'] = 'outer' if abs(d-a.radius-b.radius) <= abs(d-abs(a.radius-b.radius)) else 'inner'
            else:
                row['branch'] = 'line_circle'
            tangent_by_index[found[0]] = row
        plans = _zero_constraint_plans(tuple(bundle.spec.constraints), tuple(bundle.targets))
        assert {i for i,(kind,_) in plans.items() if kind == 'istangent'} <= set(tangent_by_index)
        construction = tuple((c.name,c.expr) for c in bundle.spec.construction)
        equalities = tuple(zip(bundle.spec.constraints, map(str,bundle.targets), strict=True))
        radius_sources = positive_radius_contact_sources(tuple(bundle.var_names), construction, equalities)
        distance_parts = {}
        for i,(kind,(left,right)) in plans.items():
            if kind != 'distance':
                continue
            ctx = s4.context(bundle, point, [left,right], 200)
            objects = [s4.safe_eval_expr_hp(e,ctx) for e in [left,right]]
            if all(hasattr(o,'x') and hasattr(o,'y') for o in objects):
                distance_parts[i] = (left,right)

        # The complete row layout is fixed before either Jacobian.
        layout = []
        for i,(lhs,rhs) in enumerate(zip(bundle.spec.constraints,bundle.targets,strict=True)):
            old_indices = [j for j,(a,b) in enumerate(zip(scales['constraints'],scales['targets']))
                           if a == lhs and str(b) == str(rhs)]
            assert len(old_indices) <= 1
            base = dict(bundle_index=i, original_lhs=lhs, original_rhs=str(rhs),
                        s1_index=old_indices[0] if old_indices else None)
            if i in distance_parts:
                left,right = distance_parts[i]
                for axis in ['x','y']:
                    layout.append(base | dict(kind='distance_coordinate',
                        source=f'({left}).{axis}-({right}).{axis}', target='0'))
            else:
                layout.append(base | dict(kind='tangency' if i in tangent_by_index else 'retained',
                                          source=lhs, target=str(rhs)))
        for source in radius_sources:
            layout.append(dict(kind='radius_auxiliary',source=source,target='0',s1_index=None))
        fixed_scales = []
        for row in layout:
            j = row['s1_index']
            fixed_scales.append(mp.mpf(scales['scales'][j]) if j is not None else mp.mpf(1))
        new_indices = [i for i,r in enumerate(layout) if r['s1_index'] is None]
        counts = [0]*len(layout)
        with mp.workdps(700):
            for start in initial_points[task['case_id']]:
                for i in new_indices:
                    row = layout[i]
                    try:
                        ctx = s4.context(bundle,start,[row['source'],row['target']],700)
                        lhs = mp.mpf(evaluate_scalar_expression(row['source'],ctx,constants_only=True))
                        rhs = evaluate_target_high_precision(row['target'],ctx,precision=700,index=i)
                        if mp.isfinite(lhs) and mp.isfinite(rhs):
                            fixed_scales[i] = max(fixed_scales[i],abs(lhs),abs(rhs))
                            counts[i] += 1
                    except Exception:
                        pass
            for i,row in enumerate(layout):
                row['fixed_divisor'] = mp.nstr(fixed_scales[i],710)
                row['divisor_source'] = 'S1_saved' if row['s1_index'] is not None else 'S1_initial_candidates_same_rule'
                if row['s1_index'] is None:
                    row['finite_initial_count'] = counts[i]
        frozen_checks = []
        frozen_fallbacks = []

        def residuals(at, method):
            evaluation = evaluator.evaluate_hp_residual(at,precision=200)
            assert evaluation.is_finite
            raw = evaluation.residual_vector
            expressions = [r['source'] for r in layout if r['kind'] in ['distance_coordinate','radius_auxiliary']]
            ctx = s4.context(bundle,at,expressions,200) if expressions else None
            values = []
            for row in layout:
                i = row.get('bundle_index')
                if row['kind'] == 'tangency':
                    descriptor = tangent_by_index[i]
                    value = s4.t2(bundle,at,descriptor) if method == 'T2' and descriptor['t2_source'] else s4.t1(bundle,at,descriptor)
                elif row['kind'] in ['distance_coordinate','radius_auxiliary']:
                    value = mp.mpf(s4.safe_eval_expr_hp(row['source'],ctx))
                else:
                    value = raw[i]
                assert mp.isfinite(value)
                values.append(value)
            if method == 'T2':
                frozen = _smooth_zero_constraint_residuals(bundle=bundle,point=at,dps=200,residuals=list(raw))
                assert len(values) == len(frozen)
                difference = max((abs(a-b)/max(1,abs(a),abs(b)) for a,b in zip(values,frozen,strict=True)),default=mp.mpf(0))
                # The frozen optimization aid can return all original
                # residuals when its expression context is incomplete.
                # Requested T2 expressions remain explicitly evaluated.
                fallback = len(frozen) == len(raw) and all(a == b for a,b in zip(frozen,raw,strict=True))
                assert difference < mp.mpf('1e-170') or fallback, (task['case_id'],difference)
                frozen_checks.append(difference)
                frozen_fallbacks.append(fallback and difference >= mp.mpf('1e-170'))
            return [v/d for v,d in zip(values,fixed_scales,strict=True)]

        entry = dict(case_id=task['case_id'],reference_file=task['reference'],
                     var_names=list(bundle.var_names),rows=layout,tangencies=tangencies,
                     distance_zero_auxiliaries='on',radius_auxiliaries='on',conditions={})
        for method in ['T1','T2']:
            samples = []
            for exponent in manifest['step_exponents']:
                jac = mp.matrix(len(layout),len(point))
                for j,x in enumerate(point):
                    h = mp.mpf(10)**(-exponent)*max(1,abs(x))
                    plus,minus = list(point),list(point)
                    plus[j],minus[j] = x+h,x-h
                    rp,rm = residuals(plus,method),residuals(minus,method)
                    for i,(a,b) in enumerate(zip(rp,rm,strict=True)):
                        jac[i,j] = (a-b)/(2*h)
                singular,nonzero,zeros,reconstruction = spectrum(jac)
                samples.append(dict(step_exponent=exponent,nonzero_rows=nonzero,
                    dimension_zero_count=zeros,singular_values=singular,
                    svd_reconstruction_error=num(reconstruction),
                    jacobian=[[num(jac[i,j]) for j in range(jac.cols)] for i in range(jac.rows)]))
            a,b = [s['singular_values'] for s in samples]
            absolute = max(abs(x-y) for x,y in zip(a,b,strict=True))
            relative = max(abs(x-y)/max(abs(x),abs(y)) if x or y else mp.mpf(0)
                           for x,y in zip(a,b,strict=True))
            agree = relative <= mp.mpf(manifest['agreement_relative_tolerance']) and samples[0]['nonzero_rows'] == samples[1]['nonzero_rows']
            for sample in samples:
                sample['singular_values'] = [num(s) for s in sample['singular_values']]
            entry['conditions'][method] = dict(samples=samples,agreement=agree,
                max_absolute_difference=num(absolute),max_relative_difference=num(relative))
            fallback = sum(not r['t2_source'] for r in tangencies)
            notes = '距離0の座標差・半径補助式あり; 非ゼロ行は中央差分値の厳密な非ゼロで数える'
            if method == 'T2':
                notes += f'; 接点式なしの{fallback}条件はT1'
            csv_rows.append({'問題ID':task['case_id'],'条件(T1/T2)':method,'行数':len(layout),
                '列数':len(point),'最小特異値':samples[0]['singular_values'][0],
                '特異値の昇順':json.dumps(samples[0]['singular_values']),
                '2つの幅での一致':'一致' if agree else '不一致','備考':notes,
                '非ゼロ行数':samples[0]['nonzero_rows'],'非ゼロ行数(照合幅)':samples[1]['nonzero_rows'],
                '次元によるゼロ特異値数':samples[0]['dimension_zero_count'],
                '次元によるゼロ特異値数(照合幅)':samples[1]['dimension_zero_count'],
                '最小特異値(照合幅)':samples[1]['singular_values'][0],
                '特異値の昇順(照合幅)':json.dumps(samples[1]['singular_values']),
                '最大絶対差':num(absolute),'最大相対差':num(relative)})
        csv_rows.append({'問題ID':task['case_id'],'条件(T1/T2)':'T0','備考':'T0：折れ目で微分できない'})
        entry['frozen_T2_comparison_max_relative_difference'] = num(max(frozen_checks))
        entry['frozen_T2_original_residual_fallback_count'] = sum(frozen_fallbacks)
        entry['frozen_T2_comparison_count'] = len(frozen_checks)
        return entry, csv_rows
