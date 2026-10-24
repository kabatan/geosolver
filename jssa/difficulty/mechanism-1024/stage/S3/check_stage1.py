"""Residual-only S3 preflight. Never search, refine, verify, or evaluate an answer.

Run with the S1 Python. Each child uses a fresh evaluator and one CPU/thread.
Only initial.pkl is read under S1/runs; no refined candidates or measurements.
"""
import ast
import hashlib
import inspect
import json
import os
import pickle
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT = Path(__file__).resolve().parent
BASE = Path('/tmp/mechanism-7b-lkdjle5l/final/src')
IMPL = Path('/tmp/s3-impl/src')
FROZEN = Path('/tmp/mech-inv-clean/src')
S1 = Path('/tmp/mechanism-S1-1m9aomj8')
RAW = Path('/tmp/s3-impl/check')
BASE_HASH = 'sha256:03a44bfbb743b972d95306c63a14c04b78c7d12b96a1ba83d147c56eea7f86a3'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def encode(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2,
                       allow_nan=False) + '\n').encode()


def files(root):
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*'))
            if p.is_file() and '__pycache__' not in p.parts}


def sourcehash(root):
    h = hashlib.sha256()
    for relative in files(root):
        p = root / relative
        if p.suffix in {'.py', '.json', '.toml'} and p.name != 'engine-lock.json' and 'frontend' not in p.parts:
            h.update(relative.encode() + b'\0' + p.read_bytes().replace(b'\r\n', b'\n') + b'\0')
    return 'sha256:' + h.hexdigest()


def child():
    from mpmath import mp
    from geosolver.engine.standard.evaluation.ir_evaluator import build_ir_evaluator
    from geosolver.engine.standard.evaluation.high_precision_expressions import build_solution_context_high_precision
    from geosolver.engine.standard.precision.type_guards.high_precision_mode import high_precision_mode
    from geosolver.engine.standard.precision.type_guards.boundary_float_to_mpf import boundary_float_to_mpf, BoundaryOrigin
    from geosolver.engine.standard.problem.load_problem_bundle import load_problem_bundle
    from geosolver.engine.standard.problem.tangency_contacts import contact_tangency_source, distance_contact_sources
    from geosolver.engine.standard.refinement import mpmath_refiner as refiner
    from geosolver.problem.ir.compiler import safe_eval_expr_hp
    from geosolver.problem.models import GeometryProblem
    from geosolver.runtime.integrity import source_tree_hash

    # Abort if this preflight accidentally crosses into an answer/optimizer path.
    def forbidden(*args, **kwargs):
        raise AssertionError('Stage 1 forbids optimization and answer evaluation')

    refiner.MpmathRefiner.refine_candidates = forbidden
    refiner.MpmathRefiner._refine_single_candidate = forbidden
    refiner.MpmathRefiner._run_stage = forbidden
    refiner.MpmathRefiner._evaluate_answer = forbidden
    mp.findroot = forbidden
    manifest = json.loads((S1 / 'manifest.json').read_text())
    result = {'source_hash': source_tree_hash(), 'cases': []}
    mode = os.environ.get('GEOSOLVER_S3_TANGENCY_MODE', 'T2')
    # Observe the actual append branch, without altering the residual code.
    function = refiner._smooth_zero_constraint_residuals
    lines, first_line = inspect.getsourcelines(function)
    tree = ast.parse(''.join(lines))
    branches = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Expr) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name) or call.func.value.id != 'rewritten':
            continue
        text = ast.unparse(call)
        if call.func.attr == 'append':
            if 'signed_tangency(' in text:
                label = 'circle_circle_signed_nearest'
            elif 'signed_distance' in text:
                label = 'line_circle_squared'
            elif 'safe_eval_expr_hp(contact_source' in text:
                label = 'source_expression'
            else:
                label = 'original'
        elif 'left.x' in text:
            label = 'point_point_coordinate_difference'
        else:
            continue
        branches[first_line + node.lineno - 1] = label

    for task in manifest['inputs']:
        case = task['case_id']
        input_path = Path(task['input_copy'])
        assert sha(input_path) == task['sha256']
        initial = S1 / 'runs' / case / 'initial.pkl'
        with initial.open('rb') as handle:
            candidates, config = pickle.load(handle)
        candidate = candidates[0]
        document = GeometryProblem.model_validate_json(input_path.read_text()).engine_document()
        bundle = load_problem_bundle(document)
        evaluator = build_ir_evaluator(bundle)
        type(evaluator).evaluate_answer_hp = forbidden
        constructions = tuple((item.name, item.expr) for item in bundle.spec.construction)
        equalities = tuple(zip(bundle.spec.constraints, map(str, bundle.targets), strict=True))
        plans = refiner._zero_constraint_plans(tuple(bundle.spec.constraints), tuple(bundle.targets))
        distance_contacts = distance_contact_sources(constructions, equalities)
        observed = {}

        def trace(frame, event, arg):
            if frame.f_code is function.__code__ and event == 'line' and frame.f_lineno in branches:
                index = frame.f_locals.get('index')
                label = branches[frame.f_lineno]
                row = {'type': label}
                if label == 'source_expression':
                    row['expression'] = frame.f_locals['contact_source']
                    row['type'] = ('line_circle_squared' if mode == 'T1' else
                                   'circle_circle_contact_cross' if '/Radius(' in row['expression'] else
                                   'line_circle_contact_dot')
                observed[index] = row
            return trace

        with mp.workdps(max(200, max(config.schedule_dps))):
            if candidate.initial_point_decimal and len(candidate.initial_point_decimal) == len(candidate.x_float):
                point = [mp.mpf(value) for value in candidate.initial_point_decimal]
                point_source = 'initial_point_decimal'
            else:
                point = [boundary_float_to_mpf(value, origin=BoundaryOrigin.INITIAL_POINT) for value in candidate.x_float]
                point_source = 'exact_binary_float'
        dps = 180
        obj = refiner.MpmathRefiner(config)
        with mp.workdps(dps), high_precision_mode():
            raw = obj._residual_vector_for_stage(bundle, evaluator, point, dps)
            assert raw is not None
            sys.settrace(trace)
            try:
                vector = obj._residual_vector_for_stage(bundle, evaluator, point, dps, smooth_zero_constraints=True)
            finally:
                sys.settrace(None)
            assert vector is not None
            # Build expected rows independently, including coordinates and auxiliary rows.
            context = build_solution_context_high_precision(bundle.spec, list(bundle.var_names), point,
                bundle.base_context, dps,
                expressions=[*bundle.spec.constraints,
                    *(str(target) for target in bundle.targets),
                    *(expr for _, pair in plans.values() for expr in pair),
                    *distance_contacts.values()])
            constraints = []
            expected = []
            for index, residual in enumerate(raw):
                plan = plans.get(index)
                if index in distance_contacts:
                    # The fixed twelve cases have no Distance(center,line)=radius rows.
                    raise AssertionError('unexpected Distance contact in fixed S1 cases')
                if plan is None:
                    expected.append(residual)
                    continue
                kind, (left_expr, right_expr) = plan
                left, right = (safe_eval_expr_hp(expr, context) for expr in (left_expr, right_expr))
                if kind == 'distance':
                    if all(hasattr(value, 'x') and hasattr(value, 'y') for value in (left, right)):
                        expected.extend([mp.mpf(left.x)-mp.mpf(right.x), mp.mpf(left.y)-mp.mpf(right.y)])
                    else:
                        expected.append(residual)
                    continue
                source = contact_tangency_source(left_expr, right_expr, constructions, equalities)
                left, right = getattr(left, 'circle', left), getattr(right, 'circle', right)
                circles = hasattr(left, 'radius') and hasattr(right, 'radius')
                geometry_kind = 'circle_circle' if circles else 'line_circle'
                if mode == 'T0':
                    label, value = 'original', residual
                elif mode == 'T2' and source is not None:
                    label = geometry_kind + ('_contact_cross' if circles else '_contact_dot')
                    value = mp.mpf(safe_eval_expr_hp(source, context))
                elif circles:
                    label = 'circle_circle_signed_nearest'
                    distance = left.center.distance_to(right.center)
                    if distance == 0 or left.radius <= 0 or right.radius <= 0:
                        value = residual
                    else:
                        outer = distance - (left.radius + right.radius)
                        inner = distance - abs(left.radius - right.radius)
                        value = outer if abs(outer) <= abs(inner) else inner
                else:
                    label = 'line_circle_squared'
                    line, circle = (left, right) if hasattr(left, 'a') else (right, left)
                    delta = mp.mpf(line.a)*mp.mpf(circle.center.x) + mp.mpf(line.b)*mp.mpf(circle.center.y) + mp.mpf(line.c)
                    value = delta*delta - mp.mpf(circle.radius)*mp.mpf(circle.radius)
                assert observed[index]['type'] == label, (case, index, observed.get(index), label)
                start = len(expected)
                expected.append(value)
                assert vector[start]._mpf_ == value._mpf_, (case, index, label)
                constraints.append({'constraint_index': index, 'lhs': bundle.spec.constraints[index],
                    'rhs': str(bundle.targets[index]), 'geometry': geometry_kind,
                    'contact_demonstrable': source is not None,
                    'contact_source': source, 'observed': observed[index],
                    'residual_row': start, 'residual_value': mp.nstr(vector[start], dps + 8),
                    'formula_value_exact_binary_match': True})
            from geosolver.engine.standard.problem.positive_radius_contacts import positive_radius_contact_sources
            radius_sources = positive_radius_contact_sources(tuple(bundle.var_names), constructions, equalities)
            expected.extend(mp.mpf(safe_eval_expr_hp(source, context)) for source in radius_sources)
            assert [x._mpf_ for x in expected] == [x._mpf_ for x in vector], case
            binary = [list(map(int, x._mpf_)) for x in vector]
            result['cases'].append({'case_id': case, 'candidate_index': 0, 'candidate_uid': candidate.candidate_uid,
                'candidate_count': len(candidates), 'initial_pickle_sha256': sha(initial),
                'input_sha256': sha(input_path), 'point_source': point_source, 'dps': dps,
                'constraints': constraints, 'residual_vector_binary': binary,
                'residual_vector_sha256': hashlib.sha256(encode(binary)).hexdigest(),
                'coordinate_difference_indices': [i for i,r in observed.items() if r['type']=='point_point_coordinate_difference'],
                'radius_auxiliary_sources': list(radius_sources), 'residual_rows': len(vector)})
    print(encode(result).decode(), end='')


def main():
    assert sourcehash(BASE / 'geosolver') == BASE_HASH
    protected_before = {'base': files(BASE), 'frozen': files(FROZEN),
                        'preregistration': sha(OUT / 'preregistration-10.md')}
    RAW.mkdir(exist_ok=True)
    cpu = min(os.sched_getaffinity(0))
    snapshots = {}
    for name, source, mode in [('BASE', BASE, None), ('unset', IMPL, None),
                               ('T0', IMPL, 'T0'), ('T1', IMPL, 'T1'), ('T2', IMPL, 'T2')]:
        env = {k:v for k,v in os.environ.items() if not k.startswith('GEOSOLVER_')}
        env.update({k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')})
        env.update(PYTHONPATH=str(source), PYTHONDONTWRITEBYTECODE='1')
        if mode is not None:
            env['GEOSOLVER_S3_TANGENCY_MODE'] = mode
        completed = subprocess.run(['taskset','-c',str(cpu),sys.executable,'-B',str(Path(__file__).resolve()),'--child'],
            env=env, capture_output=True, timeout=50)
        (RAW / (name + '.stderr')).write_bytes(completed.stderr)
        assert completed.returncode == 0, (name, completed.stderr.decode())
        (RAW / (name + '.json')).write_bytes(completed.stdout)
        snapshots[name] = json.loads(completed.stdout)
        print(name, '12 residual-only candidates checked', flush=True)
    # Residual/Jacobian boundary probes remain serial with the twelve-case checks.
    env.pop('GEOSOLVER_S3_TANGENCY_MODE', None)
    completed = subprocess.run(['taskset', '-c', str(cpu), sys.executable, '-B',
        str(OUT / 'check_boundaries.py')], env=env, capture_output=True, timeout=30)
    (RAW / 'boundaries.stderr').write_bytes(completed.stderr)
    assert completed.returncode == 0, completed.stderr.decode()
    (RAW / 'boundaries.json').write_bytes(completed.stdout)
    boundaries = json.loads(completed.stdout)
    base_cases = snapshots['BASE']['cases']
    assert encode(base_cases) == encode(snapshots['unset']['cases']) == encode(snapshots['T2']['cases'])
    contacts = {'criterion':'frozen tangency_contacts.py, syntax only, not numerical incidence',
                'indexing':'0-based loaded bundle constraints',
                'classifier_source_sha256':sha(FROZEN / 'geosolver/engine/standard/problem/tangency_contacts.py'),
                'groups':{'A':[], 'B':[]}, 'cases':[]}
    comparison = []
    for index, base_case in enumerate(base_cases):
        contact_rows = [{key:row[key] for key in ('constraint_index','lhs','rhs','geometry','contact_demonstrable','contact_source')}
                        for row in base_case['constraints']]
        group = 'A' if any(row['contact_demonstrable'] for row in contact_rows) else 'B'
        contacts['groups'][group].append(base_case['case_id'])
        contacts['cases'].append({'case_id':base_case['case_id'], 'group':group,
                                  'input_sha256':base_case['input_sha256'], 'constraints':contact_rows})
        arms = {name:snapshots[name]['cases'][index] for name in ('T0','T1','T2')}
        t1_t2_equal = arms['T1']['residual_vector_binary'] == arms['T2']['residual_vector_binary']
        if group == 'B':
            assert t1_t2_equal
        common = ('coordinate_difference_indices','radius_auxiliary_sources','residual_rows')
        assert all(arms['T0'][key] == arms['T1'][key] == arms['T2'][key] for key in common)
        comparison.append({'case_id':base_case['case_id'], 'group':group,
            'candidate_index':0, 'candidate_uid':base_case['candidate_uid'],
            'initial_pickle_sha256':base_case['initial_pickle_sha256'],
            'candidate_count':base_case['candidate_count'], 'point_source':base_case['point_source'],
            'dps':base_case['dps'], 'T2_unset_baseline_bytes_identical':True,
            'T1_T2_residual_vector_bytes_identical':t1_t2_equal,
            **{key:base_case[key] for key in common},
            'modes':{name:{'constraints':arm['constraints'], 'residual_vector_sha256':arm['residual_vector_sha256']}
                     for name,arm in arms.items()}})
    assert contacts['classifier_source_sha256'] == sha(BASE / 'geosolver/engine/standard/problem/tangency_contacts.py')
    contacts['distance_center_line_radius_count'] = sum(
        len(indices) for indices in boundaries['S1_distance_center_line_radius_indices'].values())
    assert contacts['distance_center_line_radius_count'] == 0
    assert len(contacts['groups']['A']) == len(contacts['groups']['B']) == 6
    unchanged = [relative for relative in files(BASE) if sha(IMPL / relative) == sha(BASE / relative)]
    final_paths = [p for p in unchanged if '/evaluation/' in p or '/exact_assembly/' in p or '/exact/' in p]
    assert all(p in unchanged for p in files(BASE) if '/evaluation/' in p or '/exact_assembly/' in p or '/exact/' in p)
    assert all(sha(IMPL / p) == sha(FROZEN / p) for p in final_paths)
    assert protected_before == {'base':files(BASE), 'frozen':files(FROZEN),
                                'preregistration':sha(OUT / 'preregistration-10.md')}
    # Keep the full fixed-point residual vectors in /tmp; publish hashes + tangency values.
    summary = {'created_utc':datetime.now(timezone.utc).isoformat(), 'stage':1,
        'source_hash':snapshots['T2']['source_hash'], 'baseline_source_hash':BASE_HASH,
        'parallel':1,'cpu_affinity':[cpu], 'thread_count':1,
        'search_executed':False,'refinement_executed':False,'final_verification_executed':False,
        'answer_evaluation_executed':False,'target_error_examined_or_recorded':False,
        'T2_unset_baseline_byte_comparison':{'scope':'canonical full cases payload, including exact mpf tuples and observed branches; source identity excluded',
            'bytes':len(encode(base_cases)), 'sha256':hashlib.sha256(encode(base_cases)).hexdigest(), 'identical':True},
        'all_expected_formula_values_exact_binary_match':True,
        'boundary_checks':boundaries,
        'baseline_copy_check':json.loads((IMPL.parent / 'baseline-copy-check.json').read_text()),
        'protected_sources_and_preregistration_unchanged':True,
        'final_evaluation_identification_files_unchanged':{p:sha(BASE/p) for p in final_paths},
        'raw_snapshots':{name:{'path':str(RAW/(name+'.json')), 'sha256':sha(RAW/(name+'.json'))} for name in snapshots},
        'groups':contacts['groups'],'cases':comparison}
    (OUT/'contacts.json').write_bytes(encode(contacts))
    (OUT/'switch-check.json').write_bytes(encode(summary))
    print(json.dumps({'groups':contacts['groups'], 'T2_unset_baseline_bytes_identical':True}))


if __name__ == '__main__':
    child() if sys.argv[1:] == ['--child'] else main()
