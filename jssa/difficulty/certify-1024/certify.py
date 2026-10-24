#!/usr/bin/env python3
"""Stage A only: dev5 radical membership, one bounded attempt per input.

No solver search, elimination order, benchmark grading, or retries. See README.md.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
STRONG = HERE.parent / 'exact-strong-1024'
ROOT = HERE.parents[2]
TOOLS = Path('/tmp/q6-tools')
CONVERTER = TOOLS / 'exact_comparison/benchmarks/exact_comparison'
MEM = 8 << 30
MAX_FILE = 2_900_000
WALL = 600
# Fixed serial schedule (one CPU / problem); never more than two workers.


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, obj):
    data = json.dumps(obj, ensure_ascii=False, indent=2, default=str) + '\n'
    if len(data.encode()) > MAX_FILE:
        raise ValueError('ARTIFACT_SIZE_LIMIT')
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(data)
    temp.replace(path)


def dev5():
    return (STRONG / 'dev5-ids.txt').read_text().splitlines()


def environment():
    os.environ.update(PATH=str(TOOLS / 'bin') + ':' + os.environ['PATH'],
                      PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1',
                      OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    os.environ.pop('EXACT_CAPTURE_DIR', None)
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(STRONG), str(CONVERTER)]


def dependencies():
    # Imports only. No copy, no mutation, no frozen solver execution.
    environment()
    import run_strong
    import strong_translate
    return run_strong, strong_translate


def source_hashes():
    paths = [HERE / 'certify.py', HERE / 'verify_certificate.py',
             STRONG / 'strong_translate.py', STRONG / 'run_strong.py',
             STRONG / 'rules.md', STRONG / 'dev5-ids.txt', STRONG / 'dev5-inputs.jsonl',
             CONVERTER / 'algebraize.py', TOOLS / 'bin/Singular',
             TOOLS / 'root/usr/bin/Singular', TOOLS / 'root/usr/share/singular/LIB/elim.lib']
    return {str(p): sha(p) for p in paths}


def entries(obj, path=()):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == 'answer_hp' and isinstance(v, str):
                yield path + (k,), v
            else:
                yield from entries(v, path + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from entries(v, path + (i,))


def select_branch(poly, descriptor, raw):
    """Numerical root selection only; never an input equation or proof."""
    import sympy as sp
    T = sp.Symbol('T')
    decimal = descriptor.get('decimal')
    if decimal is None:
        return {'status': 'missing_solver_value', 'proof': False}
    d = sp.Rational(decimal)
    hp_path, hp = ('solver_result', 'answers', 0, 'value', 'decimal'), decimal
    for path, value in entries(raw):
        try:
            if abs(sp.N(sp.Rational(value) - d, 70)) < sp.Float('1e-40'):
                hp_path, hp = path, value
                break
        except (ValueError, TypeError):
            pass
    roots = sp.Poly(poly, T).real_roots()
    if not roots:
        return {'status': 'no_real_root', 'proof': False}
    distances = [abs(sp.N(r - sp.Rational(hp), 90)) for r in roots]
    order = sorted(range(len(roots)), key=lambda i: distances[i])
    i = order[0]
    separated = len(order) == 1 or distances[order[1]] > 100 * distances[i]
    return {'status': 'selected' if separated and distances[i] < sp.Float('1e-40') else 'unresolved',
            'proof': False, 'root_exact': str(roots[i]), 'real_root_index_selected': i,
            'solver_real_root_index': descriptor.get('real_root_index'),
            'solver_value': hp, 'solver_value_path': list(hp_path),
            'distance_90d': str(distances[i]), 'method': 'nearest real root to recorded solver high precision value'}


def prepare_records():
    """Read existing records for dev5 only and freeze candidate provenance."""
    environment()
    import sympy as sp
    T = sp.Symbol('T')
    destination = HERE / 'candidates.json'
    if destination.exists() or (HERE / 'runs').exists():
        raise SystemExit('Candidate freeze already exists; no overwrite or retry')
    cases = [json.loads(l) for l in (STRONG / 'dev5-inputs.jsonl').read_text().splitlines()]
    if [c['id'] for c in cases] != dev5():
        raise ValueError('DEV5_INPUT_MISMATCH')
    exact = json.loads((STRONG / 'dev5-results.json').read_text())
    records = {}
    for case in cases:
        cid = case['id']
        # R3 forbids pi. Do not seek an alternative target or polynomial.
        if cid == 'AIME-2005-I-01':
            records[cid] = {'source_kind': 'not_applicable', 'reason_code': 'NONALGEBRAIC_PI'}
            continue
        group = 'a' if cid.startswith('AIME') else 'b'
        paths = sorted((HERE.parent / f'unseen-2/{group}/execution/runs' / cid).glob('*.json'))
        found = None
        searched = []
        for p in paths:
            searched.append(str(p.relative_to(ROOT)))
            raw = json.loads(p.read_text())
            answers = raw.get('solver_result', {}).get('answers', [])
            if raw.get('case_id') != cid or raw.get('solver_result', {}).get('status') != 'solved':
                continue
            if len(answers) != 1:
                continue
            descriptor = answers[0].get('value', {})
            coefficients = descriptor.get('minimal_polynomial') if isinstance(descriptor, dict) else None
            if not coefficients:
                continue
            poly = sp.Poly.from_list(list(map(sp.Rational, coefficients)), T).primitive()[1]
            if poly.degree() < 1 or not poly.is_irreducible:
                raise ValueError('INVALID_RECORDED_MINPOLY')
            found = {'source_kind': 'solver_record', 'source': str(p.relative_to(ROOT)),
                     'source_sha256': sha(p), 'seed': raw.get('seed'),
                     'json_path': ['solver_result', 'answers', 0, 'value', 'minimal_polynomial'],
                     'coefficient_order': 'descending', 'coefficients': list(map(str, poly.all_coeffs())),
                     'polynomial': str(poly.as_expr()),
                     'descriptor': descriptor, 'branch': select_branch(poly.as_expr(), descriptor, raw)}
            break
        if found is None:
            # Permitted fallback only: an irreducible factor of the already saved
            # exact elimination polynomial, containing the exact method's answer.
            old = next(r for r in exact['results'] if r['id'] == cid)
            values = old.get('verified_values', [])
            elimination = sp.sympify(old['target_polynomial_factored'])
            if len(values) != 1 or len(elimination.free_symbols) != 1:
                raise ValueError('NO_UNAMBIGUOUS_EXACT_FALLBACK')
            elimination = elimination.subs(next(iter(elimination.free_symbols)), T)
            value = sp.sympify(values[0])
            factors = [f for f, _ in sp.factor_list(elimination)[1] if sp.simplify(f.subs(T, value)) == 0]
            if len(factors) != 1:
                raise ValueError('NO_UNIQUE_EXACT_FACTOR')
            poly = sp.Poly(factors[0], T).primitive()[1]
            found = {'source_kind': 'exact_elimination_factor',
                     'source': str((STRONG / 'dev5-results.json').relative_to(ROOT)),
                     'source_sha256': sha(STRONG / 'dev5-results.json'),
                     'polynomial': str(poly.as_expr()), 'coefficients': list(map(str, poly.all_coeffs())),
                     'coefficient_order': 'descending', 'exact_method_value': str(value),
                     'branch': {'status': 'no_solver_high_precision_value', 'proof': False}}
        found['searched_solver_records'] = searched
        found['dsl_sha256'] = hashlib.sha256(json.dumps(case['dsl'], sort_keys=True).encode()).hexdigest()
        records[cid] = found
    write_json(destination, {'scope': 'dev5 only; candidate preparation is read-only, no solver execution',
                             'records': records, 'inputs_sha256': sha(STRONG / 'dev5-inputs.jsonl')})
    print('candidate provenance frozen', flush=True)


def singular_text(equations, factors, used, target, polynomial):
    """dp in every ring. Sequential sat copied in meaning from run_strong.

    Positive certificates are lifted to ORIGINAL equations plus inverse guards, so
    independent verification does not have to trust Singular's saturation.
    """
    import sympy as sp
    ren = {v: sp.Symbol(f'x{i+1}') for i, v in enumerate(used)}
    names = ','.join(map(str, ren.values()))
    renamed = [sp.expand(e.xreplace(ren)) for e in equations]
    factor_exprs = [f.xreplace(ren) for f in factors]
    p = sp.expand(polynomial.subs(sp.Symbol('T'), ren[target]))
    # Preserve rational scaling exactly for certificates (poly_str normalizes it).
    def fmt(e):
        e = sp.expand(e)
        variables = sorted(e.free_symbols, key=str)
        if variables:
            denominator, numerator = sp.Poly(e, *variables, domain=sp.QQ).clear_denoms()
            numerator = numerator.as_expr()
        else:
            numerator, denominator = sp.fraction(e)
        # Singular parses x^2/4 as x^(2/4). Parenthesize the entire
        # integer polynomial BEFORE division, preserving its exact scale.
        return '(' + str(numerator).replace('**', '^') + ')/(' + str(denominator) + ')'
    F = ',\n'.join(map(fmt, renamed)) or '0'
    inverse_symbols = [sp.Symbol(f'z{i+1}') for i in range(len(factor_exprs))]
    guards = [1-z*f for z, f in zip(inverse_symbols, factor_exprs)]
    extended_names = ','.join(list(map(str, ren.values())) + list(map(str, inverse_symbols)) + ['yy'])
    extended_F = ',\n'.join(map(fmt, renamed + guards)) or '0'
    def dump(label, name):
        return [f'print("BLOCK {label} BEGIN");',
                f'for(ii=1;ii<=size({name});ii++){{print({name}[ii]);}}',
                f'print("BLOCK {label} END");']
    lines = ['LIB "elim.lib";', 'option(redSB);', 'system("--ticks-per-sec",1000);',
             f'ring R=0,({names}),dp;', 'short=0;', f'ideal F={F};', 'ideal J=F;',
             'int ii;', 'print("EVENT saturation begin");', 'int clock0=rtimer;']
    for i, f in enumerate(factor_exprs):
        lines += [f'J=sat(J,ideal({fmt(f)}));', f'print("EVENT saturation factor {i+1}");']
    lines += ['print("METRIC saturation_ms "+string(rtimer-clock0));', 'print("EVENT saturation end");']
    lines += dump('J', 'J')
    lines += ['print("EVENT power begin");', 'clock0=rtimer;', 'ideal G=std(J);',
              'print("METRIC power_basis_ms "+string(rtimer-clock0));',
              'print("METRIC power_basis_size "+string(size(G)));',
              'poly unitnf=reduce(1,G);', 'print("METRIC unit_ideal "+string(unitnf==0));']
    lines += dump('G', 'G')
    lines += [f'poly p={fmt(p)};', 'int firstm=0;', 'poly rem;', 'int mm;', 'clock0=rtimer;']
    for m in range(1, 5):
        lines += [f'rem=reduce(p^{m},G);', f'print("METRIC nf_{m}_zero "+string(rem==0));',
                  f'print("BLOCK NF{m} BEGIN");', 'print(rem);', f'print("BLOCK NF{m} END");',
                  f'if(rem==0 && firstm==0){{firstm={m};}}']
    lines += ['print("METRIC power_nf_ms "+string(rtimer-clock0));', 'print("EVENT power end");',
              f'ring S=0,({names},yy),dp;', 'short=0;', 'ideal J=imap(R,J);', 'poly p=imap(R,p);',
              'ideal I=J,1-yy*p;', 'print("EVENT rabinowitsch begin");', 'clock0=rtimer;',
              'ideal G=std(I);', 'print("METRIC rab_basis_ms "+string(rtimer-clock0));',
              'print("METRIC rab_basis_size "+string(size(G)));', 'clock0=rtimer;',
              'poly rem=reduce(1,G);', 'int rb=(rem==0);',
              'print("METRIC rab_unit "+string(rb));',
              'print("METRIC rab_nf_ms "+string(rtimer-clock0));']
    lines += dump('RAB_G', 'G')
    lines += ['print("BLOCK RAB_NF BEGIN");', 'print(rem);', 'print("BLOCK RAB_NF END");',
              'print("EVENT rabinowitsch end");', 'setring R;',
              'int powm=firstm;', 'setring S;', 'int rabok=rb;',
              'if(powm>0 || rabok){',
              f'ring C=0,({extended_names}),dp;', 'short=0;', f'ideal K={extended_F};',
              'poly p=imap(R,p);', 'matrix A;', 'int jj;']
    # lift is proof extraction, never a repeat of the membership attempt.
    lines += ['if(powm>0){', 'print("EVENT power_certificate begin");', 'clock0=rtimer;',
              'A=lift(K,ideal(p^powm));', 'print("BLOCK POWER_COEFF BEGIN");',
              'for(jj=1;jj<=nrows(A);jj++){print(A[jj,1]);}',
              'print("BLOCK POWER_COEFF END");',
              'print("METRIC power_certificate_ms "+string(rtimer-clock0));',
              'print("EVENT power_certificate end");', '}',
              'if(rabok){', 'print("EVENT rab_certificate begin");', 'clock0=rtimer;',
              'ideal L=K,1-yy*p;', 'A=lift(L,ideal(1));', 'print("BLOCK RAB_COEFF BEGIN");',
              'for(jj=1;jj<=nrows(A);jj++){print(A[jj,1]);}', 'print("BLOCK RAB_COEFF END");',
              'print("METRIC rab_certificate_ms "+string(rtimer-clock0));',
              'print("EVENT rab_certificate end");', '}', '}', 'print("EVENT finished end");', 'quit;']
    model = {'variables': list(map(str, ren.values())) + list(map(str, inverse_symbols)) + ['yy'],
             'variable_mapping': {str(ren[v]): str(v) for v in used},
             'target_variable': str(ren[target]), 'equations': list(map(str, renamed)),
             'saturation_factors': list(map(str, factor_exprs)), 'polynomial': str(p),
             'saturation_encoding': 'factorwise_inverses',
             'inverse_variables': list(map(str, inverse_symbols)),
             'certificate_extension': 'K=<original equations, 1-z_i*h_i for each saturation factor>',
             'order': 'dp (degree reverse lexicographic)'}
    script = '\n'.join(lines) + '\n'
    if len(script.encode()) > MAX_FILE:
        raise ValueError('ARTIFACT_SIZE_LIMIT')
    return script, model


def parse_log(log):
    metrics = {k: int(v) for k, v in re.findall(r'^METRIC (\w+) (-?\d+)\s*$', log, re.M)}
    blocks = {k: [l.strip() for l in v.splitlines() if l.strip()]
              for k, v in re.findall(r'^BLOCK (\w+) BEGIN\n(.*?)^BLOCK \1 END\s*$', log, re.M | re.S)}
    events = re.findall(r'^EVENT (.*)$', log, re.M)
    power = {'status': 'not_run', 'independent_verification': 'not_applicable'}
    rab = {'status': 'not_run', 'independent_verification': 'not_applicable'}
    for obj, prefix in ((power, 'power'), (rab, 'rab')):
        obj['basis_size'] = metrics.get(prefix + '_basis_size')
        obj['basis_seconds'] = metrics.get(prefix + '_basis_ms', 0) / 1000 if prefix + '_basis_ms' in metrics else None
        obj['normal_form_seconds'] = metrics.get(prefix + '_nf_ms', 0) / 1000 if prefix + '_nf_ms' in metrics else None
        obj['certificate_seconds'] = metrics.get(prefix + '_certificate_ms', 0) / 1000 if prefix + '_certificate_ms' in metrics else None
    power['normal_forms_zero'] = {str(m): bool(metrics[f'nf_{m}_zero']) for m in range(1, 5) if f'nf_{m}_zero' in metrics}
    zero = [int(m) for m, value in power['normal_forms_zero'].items() if value]
    if zero:
        power.update(status='member', first_zero_power=min(zero), independent_verification='not_verified')
    elif len(power['normal_forms_zero']) == 4:
        power['status'] = 'inconclusive_m_le_4'
    if 'rab_unit' in metrics:
        rab['status'] = 'member' if metrics['rab_unit'] else 'nonmember'
        rab['independent_verification'] = 'not_verified' if metrics['rab_unit'] else 'not_checked'
    if rab['status'] == 'member':
        status = 'member'
    elif rab['status'] == 'nonmember':
        status = 'nonmember'
    elif power['status'] == 'member':
        status = 'member'
    else:
        status = 'unresolved'
    if zero and rab['status'] == 'nonmember':
        status = 'inconsistent_methods'
    if metrics.get('unit_ideal'):
        status = 'algebraically_empty'
    errors = re.findall(r'^\s*\?.*$', log, re.M)
    if errors:
        # Singular can continue after an error, leaving rem initialized to 0.
        # Such output is never evidence, even if it prints zero-NF markers.
        status = 'error'
        for obj in (power, rab):
            obj.clear()
            obj.update(status='invalid_singular_output', independent_verification='not_available')
    return {'status': status, 'power': power, 'rabinowitsch': rab,
            'saturation_seconds': metrics.get('saturation_ms', 0) / 1000 if 'saturation_ms' in metrics else None,
            'unit_ideal': bool(metrics['unit_ideal']) if 'unit_ideal' in metrics else None,
            'last_algebra_event': events[-1] if events else None,
            'singular_errors': errors}, blocks


def extract_certificates(work, model, result, blocks):
    paths = []
    for method, block in (('power', 'POWER_COEFF'), ('rabinowitsch', 'RAB_COEFF')):
        if block not in blocks:
            continue
        certificate = dict(model, method=method, coefficients=blocks[block],
                           exponent=result['power'].get('first_zero_power') if method == 'power' else None)
        path = work / f'{method}-certificate.json'
        write_json(path, certificate)
        paths.append((method, path))
    return paths


def worker(cid):
    run, translate = dependencies()
    work = HERE / 'runs' / (cid + '.work')
    case = json.loads((work / 'input.json').read_text())
    candidate = json.loads((work / 'candidate.json').read_text())
    started = time.monotonic()
    result = {'id': cid, 'status': 'running', 'stage': 'translate', 'candidate': candidate,
              'limits': {'wall_seconds': WALL, 'memory_bytes': MEM, 'max_file_bytes': MAX_FILE,
                         'attempts': 1, 'threads': 1, 'parallelism': 1},
              'implementation_sha256': source_hashes(), 'proof_verified': False}
    def checkpoint(stage):
        result.update(stage=stage, worker_wall_seconds=time.monotonic() - started)
        write_json(work / 'progress.json', result)
    try:
        checkpoint('translate')
        system, target = translate.translate(case['dsl'])
        # R4's direct answer shortcut is deliberately not used: certify needs J.
        equations, factors, used = run.prepare(system, target)
        import sympy as sp
        polynomial = sp.sympify(candidate['polynomial'], locals={'T': sp.Symbol('T')})
        script, model = singular_text(equations, factors, used, target, polynomial)
        result.update(translation_seconds=time.monotonic() - started, nvars=len(used),
                      nequations=len(equations), saturation_factors=len(factors), order='dp')
        write_json(work / 'translation.json', dict(model, guards=system.receipts,
                   algebraic_constants=system.constants, original_target_variable=str(target)))
        (work / 'input.sing').write_text(script)
        checkpoint('singular')
        t = time.monotonic()
        with (work / 'singular.log').open('w') as output:
            proc = subprocess.run(['Singular', '-q', str(work / 'input.sing')],
                                  stdout=output, stderr=subprocess.STDOUT)
        result['singular_wall_seconds'] = time.monotonic() - t
        result['singular_returncode'] = proc.returncode
        parsed, blocks = parse_log((work / 'singular.log').read_text())
        result.update(parsed)
        write_json(work / 'algebra-output.json', blocks)
        if proc.returncode or result['singular_errors'] or parsed['last_algebra_event'] != 'finished end':
            raise RuntimeError('SINGULAR_ERROR_OR_INCOMPLETE_OUTPUT')
        paths = extract_certificates(work, model, result, blocks)
        # This code has no Singular dependency. It expands exact QQ identities
        # against the Python-generated ORIGINAL equations, not the returned J.
        from verify_certificate import verify
        for method, path in paths:
            checkpoint('verify_' + method)
            t = time.monotonic()
            try:
                verification = verify(json.loads(path.read_text()), model)
            except Exception as exc:
                verification = {'verified': False, 'reason': type(exc).__name__ + ':' + str(exc)[:500]}
            verification['wall_seconds'] = time.monotonic() - t
            write_json(work / (method + '-verification.json'), verification)
            result[method]['independent_verification'] = 'verified' if verification['verified'] else 'failed_or_unavailable'
            result[method]['verification_seconds'] = verification['wall_seconds']
            result[method]['certificate'] = str(path.relative_to(HERE))
            checkpoint('verified_' + method)
        result['proof_verified'] = (result['status'] == 'member' and
                                    any(result[m]['independent_verification'] == 'verified'
                                        for m in ('power', 'rabinowitsch')))
        result['stage'] = 'finished'
    except translate.ConversionError as exc:
        result.update(status='unsupported', reason_code=exc.code, reason=str(exc))
    except Exception as exc:
        result.update(status='error', reason_code=type(exc).__name__, reason=str(exc)[:1200])
    result['worker_wall_seconds'] = time.monotonic() - started
    write_json(HERE / 'runs' / (cid + '.json'), result)


def child_limits():
    resource.setrlimit(resource.RLIMIT_AS, (MEM, MEM))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE, MAX_FILE))
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})


def supervise(cid, case, candidate, frozen):
    if cid not in dev5():
        raise ValueError('STAGE_A_DEV5_ONLY')
    if source_hashes() != frozen:
        raise ValueError('IMPLEMENTATION_CHANGED_AFTER_FREEZE')
    work = HERE / 'runs' / (cid + '.work')
    work.mkdir(exist_ok=False)  # atomic persistent ledger: never retry
    start = time.monotonic()
    write_json(work / 'input.json', case)
    write_json(work / 'candidate.json', candidate)
    peak, reason = 0, None
    run, _ = dependencies()
    with (work / 'worker.log').open('w') as log:
        process = subprocess.Popen([sys.executable, str(HERE / 'certify.py'), '--worker', cid],
                                   env=dict(os.environ), stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True, preexec_fn=child_limits)
        try:
            while process.poll() is None:
                peak = max(peak, run.own_tree_rss(process.pid))
                if time.monotonic() - start >= WALL:
                    reason = 'TIME_LIMIT'
                elif peak >= MEM:
                    reason = 'MEMORY_LIMIT'
                if reason:
                    break
                time.sleep(.1)
        finally:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    output = HERE / 'runs' / (cid + '.json')
    if reason or not output.exists():
        progress = work / 'progress.json'
        result = json.loads(progress.read_text()) if progress.exists() else {'id': cid, 'candidate': candidate}
        if (work / 'singular.log').exists():
            parsed, blocks = parse_log((work / 'singular.log').read_text())
            # Keep earlier successful verification data at a later timeout.
            for m in ('power', 'rabinowitsch'):
                parsed[m].update({k: v for k, v in result.get(m, {}).items()
                                  if k in ('independent_verification', 'verification_seconds', 'certificate')})
            result.update(parsed)
            write_json(work / 'algebra-output.json', blocks)
        result.update(status='timeout' if reason == 'TIME_LIMIT' else 'resource_limit' if reason else 'worker_error',
                      reason_code=reason or f'WORKER_EXIT_{process.returncode}', proof_verified=False)
    else:
        result = json.loads(output.read_text())
    result.update(wall_seconds=time.monotonic() - start, peak_tree_rss_bytes=peak,
                  supervisor_returncode=process.returncode, attempts=1)
    write_json(output, result)
    print(json.dumps({k: result.get(k) for k in ('id', 'status', 'proof_verified', 'wall_seconds')}, ensure_ascii=False), flush=True)


def campaign():
    environment()
    candidates = json.loads((HERE / 'candidates.json').read_text())
    if sha(STRONG / 'dev5-inputs.jsonl') != candidates['inputs_sha256']:
        raise ValueError('INPUT_CHANGED_AFTER_CANDIDATE_FREEZE')
    (HERE / 'runs').mkdir(exist_ok=False)
    cases = [json.loads(l) for l in (STRONG / 'dev5-inputs.jsonl').read_text().splitlines()]
    if [c['id'] for c in cases] != dev5() or set(candidates['records']) != set(dev5()):
        raise ValueError('DEV5_SCOPE_MISMATCH')
    frozen = source_hashes()
    version = subprocess.check_output(['Singular', '--version'], text=True, stderr=subprocess.STDOUT)
    write_json(HERE / 'run-manifest.json', {'scope': dev5(), 'parallelism': 1,
               'attempts_per_problem': 1, 'wall_seconds_per_problem': WALL, 'memory_bytes_per_problem': MEM,
               'sources': frozen, 'candidate_sha256': sha(HERE / 'candidates.json'),
               'python': sys.executable, 'singular_version': version, 'copies': [],
               'began_unix': time.time()})
    for case in cases:
        supervise(case['id'], case, candidates['records'][case['id']], frozen)
    report()


def finish_unattempted():
    """Development continuation only; existing attempt ledgers never rerun.

    Used after a source freeze stops the original serial campaign on a fix.
    An active/incomplete prior attempt blocks this action.
    """
    environment()
    manifest = HERE / 'continuation-manifest.json'
    if manifest.exists() or not (HERE / 'run-manifest.json').exists():
        raise SystemExit('Continuation requires the original manifest and no prior continuation')
    candidates = json.loads((HERE / 'candidates.json').read_text())
    old_manifest = json.loads((HERE / 'run-manifest.json').read_text())
    if sha(HERE / 'candidates.json') != old_manifest['candidate_sha256']:
        raise ValueError('CANDIDATE_CHANGED_AFTER_FREEZE')
    if sha(STRONG / 'dev5-inputs.jsonl') != candidates['inputs_sha256']:
        raise ValueError('INPUT_CHANGED_AFTER_FREEZE')
    cases = [json.loads(l) for l in (STRONG / 'dev5-inputs.jsonl').read_text().splitlines()]
    if [c['id'] for c in cases] != dev5():
        raise ValueError('DEV5_SCOPE_MISMATCH')
    pending = []
    for case in cases:
        cid = case['id']
        ledger = (HERE / 'runs' / (cid + '.work')).exists()
        output = (HERE / 'runs' / (cid + '.json')).exists()
        if ledger != output:
            raise ValueError('ACTIVE_OR_INCOMPLETE_ATTEMPT:' + cid)
        if not ledger:
            pending.append(case)
    if not pending:
        raise SystemExit('No unattempted dev5 inputs; refusing to rerun')
    frozen = source_hashes()
    write_json(manifest, {'scope': [c['id'] for c in pending], 'sources': frozen,
               'candidate_sha256': sha(HERE / 'candidates.json'), 'parallelism': 1,
               'attempts_per_problem': 1, 'wall_seconds_per_problem': WALL,
               'memory_bytes_per_problem': MEM, 'began_unix': time.time(),
               'reason': 'Development fix; only previously unattempted dev5 inputs. No retries.'})
    for case in pending:
        supervise(case['id'], case, candidates['records'][case['id']], frozen)
    report()


def report():
    records = [json.loads((HERE / 'runs' / (cid + '.json')).read_text()) for cid in dev5()]
    for r in records:
        if r.get('singular_errors'):
            # Reinterpret stored ERROR output safely, without executing algebra.
            # Original per-attempt JSON/log remain unchanged for audit.
            for method in ('power', 'rabinowitsch'):
                r[method] = {'status': 'invalid_singular_output',
                             'independent_verification': 'not_available'}
            r.update(status='error', proof_verified=False)
    fields = ['id', 'status', 'category_ja', 'polynomial', 'polynomial_source_kind', 'proof_verified',
              'wall_seconds', 'peak_tree_rss_bytes', 'translation_seconds', 'saturation_seconds',
              'power_status', 'power_first_zero', 'power_basis_seconds', 'power_nf_seconds', 'power_basis_size',
              'power_certificate_seconds', 'power_independent_verification', 'power_verification_seconds',
              'rabinowitsch_status', 'rabinowitsch_basis_seconds', 'rabinowitsch_nf_seconds', 'rabinowitsch_basis_size',
              'rabinowitsch_certificate_seconds', 'rabinowitsch_independent_verification', 'rabinowitsch_verification_seconds',
              'branch_status', 'reason_code', 'attempts']
    categories = {'member': '属した', 'nonmember': '属さない', 'timeout': 'タイムアウト',
                  'unsupported': '変換不能', 'resource_limit': '資源上限', 'algebraically_empty': '代数的に空',
                  'error': '実装・計算エラー'}
    with (HERE / 'per-problem.csv').open('w') as handle:
        writer = csv.DictWriter(handle, fields)
        writer.writeheader()
        for r in records:
            c, p, q = r.get('candidate', {}), r.get('power', {}), r.get('rabinowitsch', {})
            row = {k: r.get(k) for k in fields if k in r}
            row.update(category_ja=categories.get(r['status'], '未解決・エラー'), polynomial=c.get('polynomial'),
                       polynomial_source_kind=c.get('source_kind'), branch_status=c.get('branch', {}).get('status'),
                       power_status=p.get('status', 'not_run'), power_first_zero=p.get('first_zero_power'),
                       power_nf_seconds=p.get('normal_form_seconds'), rabinowitsch_nf_seconds=q.get('normal_form_seconds'),
                       rabinowitsch_status=q.get('status', 'not_run'))
            for prefix, obj in (('power', p), ('rabinowitsch', q)):
                for key in ('basis_seconds', 'basis_size', 'certificate_seconds', 'independent_verification', 'verification_seconds'):
                    row[prefix + '_' + key] = obj.get(key)
            writer.writerow(row)
    write_json(HERE / 'summary.json', {'scope': 'development dev5 only, not evaluation',
              'statuses': {s: sum(r['status'] == s for r in records) for s in sorted({r['status'] for r in records})},
              'proof_verified': sum(bool(r.get('proof_verified')) for r in records),
              'attempts': sum(r['attempts'] for r in records), 'ids': dev5()})
    if any(p.stat().st_size > MAX_FILE for p in HERE.rglob('*') if p.is_file()):
        raise ValueError('ARTIFACT_SIZE_LIMIT')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--prepare', action='store_true')
    action.add_argument('--run-dev5', action='store_true')
    action.add_argument('--finish-unattempted-dev5', action='store_true')
    action.add_argument('--report', action='store_true')
    action.add_argument('--worker', choices=dev5(), help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.prepare:
        prepare_records()
    elif args.run_dev5:
        campaign()
    elif args.finish_unattempted_dev5:
        finish_unattempted()
    elif args.report:
        report()
    else:
        worker(args.worker)


if __name__ == '__main__':
    main()
