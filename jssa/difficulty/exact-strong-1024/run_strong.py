#!/usr/bin/env python3
"""One bounded, non-retrying exact pipeline. See rules.md for completeness limits."""
from __future__ import annotations

import argparse
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
ROOT = HERE.parent
CONVERTER = Path('/tmp/q6-tools/exact_comparison/benchmarks/exact_comparison')
CLEAN = Path('/tmp/exstrong-clean')
EXPECTED = 'sha256:d8fd9bb8392ad2984276bab3386e033669246ee79586317917c322d31b4541f5'
DEV5 = ('AIME-2005-I-01', 'AIME-2012-I-14', 'HMMT-2011-FEB-GUTS-01',
        'HMMT-2019-FEB-GUTS-17', 'HMMT-2023-FEB-GUTS-03')
MEM = 8 << 30
MAX_FILE = 2_900_000
SLICES = (0, 1, -1, 2, -2)  # fixed for every DSL, never chosen per problem
MAX_NODES = 4096


def write_json(path, obj):
    data = json.dumps(obj, ensure_ascii=False, indent=2, default=str) + '\n'
    if len(data.encode()) > MAX_FILE:
        raise ValueError('ARTIFACT_SIZE_LIMIT')
    path = Path(path)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(data)
    temp.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_case(args):
    sources = args.cases or [str(ROOT / f'unseen-2/{g}/cases.jsonl') for g in 'ab']
    found = []
    for source in sources:
        for line in Path(source).read_text().splitlines():
            case = json.loads(line)
            if case['id'] == args.case_id:
                # The solving worker receives only the ID and DSL. No answers,
                # source text, historic outputs or per-problem instructions.
                found.append({'id': case['id'], 'dsl': case['dsl']})
    if len(found) != 1:
        raise ValueError(f'expected one case, found {len(found)}')
    return found[0]


def environment():
    os.environ.update(PATH='/tmp/q6-tools/bin:' + os.environ['PATH'],
                      PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1',
                      OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    os.environ.pop('EXACT_CAPTURE_DIR', None)
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(CLEAN / 'src'), str(CLEAN), str(CONVERTER)]


def identity():
    from geosolver.runtime.integrity import source_tree_hash
    import geosolver.engine.standard.evaluation.final_verifier as fv
    commit = subprocess.check_output(['git', '-C', str(CLEAN), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(CLEAN), 'status', '--porcelain', '--untracked-files=all'], text=True)
    source_hash = source_tree_hash()
    if not commit.startswith('60db4b6') or dirty or source_hash != EXPECTED:
        raise RuntimeError('FROZEN_VERIFIER_IDENTITY_MISMATCH')
    if not Path(fv.__file__).resolve().is_relative_to(CLEAN):
        raise RuntimeError('WRONG_VERIFIER_IMPORT')
    return {'commit': commit, 'source_hash': source_hash, 'clean': True,
            'verifier_file': fv.__file__, 'converter_sha256': sha(CONVERTER / 'algebraize.py'),
            'run_exact_sha256': sha(CONVERTER / 'run_exact.py')}


def canonical(e):
    import sympy as sp
    variables = sorted(e.free_symbols, key=str)
    if variables:
        return sp.Poly(e, *variables, domain=sp.QQ).clear_denoms()[1].primitive()[1].monic().as_expr()
    return sp.sympify(e)


def prepare(system, target):
    import sympy as sp
    equations = list(dict.fromkeys(canonical(e) for e in system.eqs if e != 0))
    factors = set()
    for expression in system.nondeg:
        num, den = sp.fraction(sp.cancel(expression))
        for value in (num, den):
            for factor, _ in sp.factor_list(value)[1]:
                if factor.free_symbols:
                    factors.add(canonical(factor))
    factors = sorted(factors, key=lambda f: (sp.total_degree(f), str(f)))
    all_symbols = set().union(*(e.free_symbols for e in equations + factors))
    # The user variable order cannot become a per-case tuning knob.
    dsl = sorted(set(system.dsl_vars) - set(system.angle_vars), key=str)
    other = sorted(all_symbols - set(dsl) - {target}, key=str)
    used = dsl + other + [target]
    return equations, factors, used


def singular_script(equations, factors, used, target):
    import sympy as sp
    from run_exact import poly_str
    ren = {v: sp.Symbol(f'x{i+1}') for i, v in enumerate(used)}
    names = ','.join(str(ren[v]) for v in used)
    product = '*'.join(str(ren[v]) for v in used if v != target)
    lines = ['LIB "elim.lib";', 'option(redSB);', f'ring R=0,({names}),dp;', 'short=0;',
             'ideal J=' + ',\n'.join(poly_str(e.xreplace(ren)) for e in equations) + ';',
             'print("STRONG_SAT_BEGIN");']
    for i, f in enumerate(factors):
        lines += [f'J=sat(J,ideal({poly_str(f.xreplace(ren))}));',
                  f'print("STRONG_SAT_FACTOR_{i+1}");']
    lines += ['print("STRONG_SAT_DONE");',
              f'ideal E=eliminate(J,{product});' if product else 'ideal E=std(J);',
              'int i;', 'print("STRONG_ELIM_BEGIN");',
              'for(i=1;i<=size(E);i++){print(E[i]);}', 'print("STRONG_ELIM_END");',
              f'ring L=0,({names}),lp;', 'short=0;', 'ideal H=imap(R,J);',
              'ideal G=std(H);', 'print("STRONG_LEX_BEGIN");',
              'for(int j=1;j<=size(G);j++){print(G[j]);}',
              'print("STRONG_LEX_END");', 'quit;']
    return '\n'.join(lines) + '\n', ren


def parse_block(log, tag, inverse):
    import sympy as sp
    match = re.search('STRONG_' + tag + '_BEGIN\n(.*?)STRONG_' + tag + '_END', log, re.S)
    if not match:
        raise RuntimeError('MISSING_' + tag + '_OUTPUT')
    return [sp.sympify(line.replace('^', '**'), locals={str(v): v for v in inverse}).xreplace(inverse)
            for line in match[1].splitlines() if line.strip()]


def exact_roots(expr, variable):
    import sympy as sp
    p = sp.Poly(expr, variable, extension=True)
    if p.degree() <= 0:
        return []
    roots = p.real_roots(radicals=True)
    if any(r.is_real is None for r in roots):
        raise NotImplementedError('root reality not certified')
    return list(dict.fromkeys(r for r in roots if r.is_real is True))


def compare_zero(value, op):
    import sympy as sp
    value = sp.cancel(value)
    if value.free_symbols:
        return None
    relation = {'!=': sp.Ne, '>': sp.Gt, '<': sp.Lt, '>=': sp.Ge, '<=': sp.Le}[op](value, 0)
    if relation is sp.true:
        return True
    if relation is sp.false:
        return False
    return None


def lift_candidate(candidate, target, basis, equations, factors, used, system, case, bundle, evaluator):
    """One exact triangular traversal; rational samples only for free coordinates.

    A failed sample NEVER proves that the entire target fibre is infeasible.
    Only complete, non-sampled traversal can return excluded.
    """
    import sympy as sp
    from mpmath import mp
    from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate
    guards = [(e, op) for e, op, _ in system.guards] + [(f, '!=') for f in factors]
    embedding = {sp.Symbol(c['symbol']): sp.sympify(c['expression']) for c in system.constants}
    checks = {'nodes': 0, 'free_samples': 0, 'verifier_calls': 0, 'pruned': 0,
              'incomplete': False, 'failures': {}, 'witness': None}
    order = [v for v in reversed(used) if v != target]

    def failure(code):
        checks['failures'][code] = checks['failures'].get(code, 0) + 1

    def walk(index, assign):
        checks['nodes'] += 1
        if checks['nodes'] > MAX_NODES:
            checks['incomplete'] = True
            failure('LIFT_NODE_LIMIT')
            return False
        for expr, op in guards:
            e = expr.subs(assign)
            if not e.free_symbols and compare_zero(e, op) is False:
                checks['pruned'] += 1
                return False
        for expr in basis:
            e = sp.cancel(expr.subs(assign))
            if not e.free_symbols and e != 0:
                zero = e.equals(0)
                if zero is False:
                    checks['pruned'] += 1
                    return False
                if zero is not True:
                    checks['incomplete'] = True
                    return False
        if index == len(order):
            for variable, value in embedding.items():
                difference = sp.simplify(assign[variable] - value)
                try:
                    equal = difference == 0 or sp.to_number_field(difference).coeffs() == [0]
                except (NotImplementedError, sp.PolynomialError):
                    checks['incomplete'] = True
                    failure('CONSTANT_EMBEDDING_UNRESOLVED')
                    return False
                if not equal:
                    failure('CONJUGATE_CONSTANT')
                    return False
            if any(e.subs(assign).equals(0) is not True for e in equations):
                checks['incomplete'] = True
                failure('LIFT_EQUATION_UNRESOLVED')
                return False
            values = {}
            for v in system.dsl_vars:
                if v in system.angle_vars:
                    c, s = system.angle_vars[v]
                    values[str(v)[2:]] = sp.atan2(assign[s], assign[c])
                elif v in assign:
                    values[str(v)[2:]] = assign[v]
            if set(bundle.var_names) - set(values):
                checks['incomplete'] = True
                failure('FREE_DSL_VARIABLE')
                return False
            checks['verifier_calls'] += 1
            with mp.workdps(100):
                point = tuple(mp.mpf(str(sp.N(values[n], 95))) for n in bundle.var_names)
                result = verify_final_candidate(evaluator=evaluator, values=point)
                if result.verified and result.answer_hp is not None:
                    expected = mp.mpf(str(sp.N(candidate, 95)))
                    if abs(result.answer_hp - expected) <= mp.mpf('1e-50') * max(1, abs(expected)):
                        checks['witness'] = {'dsl_values_exact': {n: str(values[n]) for n in bundle.var_names},
                                             'answer': mp.nstr(result.answer_hp, 85),
                                             'normalized_residual': str(result.normalized_residual),
                                             'precision_dps': result.precision_dps,
                                             'status': result.status, 'hard_feasible': result.hard_feasible}
                        return True
            # A numerical final-verifier rejection is never a universal proof.
            checks['incomplete'] = True
            failure(result.status + ':' + ','.join(result.hard_failure_tags))
            return False
        variable = order[index]
        relations = [sp.cancel(e.subs(assign)) for e in basis
                     if variable in e.free_symbols]
        univariate = [e for e in relations if e.free_symbols == {variable}]
        if univariate:
            polynomial = min(univariate, key=lambda e: sp.degree(e, variable))
            try:
                values = exact_roots(polynomial, variable)
            except (NotImplementedError, sp.PolynomialError) as exc:
                checks['incomplete'] = True
                failure('ALGEBRAIC_LIFT_UNSUPPORTED:' + type(exc).__name__)
                return False
        else:
            values = list(map(sp.Integer, SLICES))
            checks['free_samples'] += 1
            # A finite sample of a free fibre is not exhaustive.
            checks['incomplete'] = True
        for value in values:
            if walk(index+1, {**assign, variable: value}):
                return True
            if checks['nodes'] > MAX_NODES:
                break
        return False

    success = walk(0, {target: candidate})
    checks['state'] = 'verified' if success else ('unresolved' if checks['incomplete'] else 'excluded')
    checks['candidate_exact'] = str(candidate)
    return checks


def worker(args):
    environment()
    import sympy as sp
    from mpmath import mp
    from run_exact import verifier_for
    from strong_translate import translate, ConversionError
    from geosolver.engine.standard.evaluation.final_verifier import verify_final_candidate

    output = Path(args.out)
    work = output.with_suffix('.work')
    case = json.loads((work / 'input.json').read_text())
    start = time.monotonic()
    record = {'id': args.case_id, 'status': 'running', 'stage': 'identity',
              'identity': identity(), 'dsl_sha256': hashlib.sha256(json.dumps(case['dsl'], sort_keys=True).encode()).hexdigest(),
              'limits': {'wall_seconds': 600, 'memory_bytes': MEM, 'max_file_bytes': MAX_FILE,
                         'threads': 1, 'attempts': 1},
              'implementation_sha256': {n: sha(HERE/n) for n in ('run_strong.py', 'strong_translate.py')}}

    def checkpoint(stage):
        record.update(stage=stage, worker_wall_seconds=time.monotonic()-start)
        write_json(work / 'progress.json', record)

    try:
        checkpoint('translate')
        system, target = translate(case['dsl'])
        record['translation_seconds'] = time.monotonic()-start
        write_json(work / 'translation.json', {'guards': system.receipts,
                   'algebraic_constants': system.constants, 'equations': list(map(str, system.eqs)),
                   'target': str(target)})
        bundle, evaluator = verifier_for(case)
        if not case['dsl']['variables']:
            checkpoint('direct_evaluation')
            with mp.workdps(100):
                result = verify_final_candidate(evaluator=evaluator, values=())
                record.update(status='direct_verified' if result.verified else 'direct_unresolved',
                              answers=[mp.nstr(result.answer_hp, 85)] if result.verified else [],
                              direct_verification={'status': result.status, 'verified': result.verified,
                                                   'normalized_residual': str(result.normalized_residual)})
            record['algebra_solver_calls'] = 0
        else:
            equations, factors, used = prepare(system, target)
            record.update(nvars=len(used), nequations=len(equations), saturation_factors=len(factors),
                          algebraic_constants=system.constants,
                          variable_order=list(map(str, used)), saturation_factor_expressions=list(map(str, factors)))
            script, ren = singular_script(equations, factors, used, target)
            if len(script.encode()) > MAX_FILE:
                raise ConversionError('ARTIFACT_SIZE_LIMIT', 'Singular input exceeds cap')
            (work / 'input.sing').write_text(script)
            checkpoint('saturate_eliminate_lex')
            t = time.monotonic()
            with (work / 'singular.log').open('w') as log:
                proc = subprocess.run(['Singular', '-q', str(work / 'input.sing')],
                                      cwd=CLEAN, stdout=log, stderr=subprocess.STDOUT)
            record.update(algebra_seconds=time.monotonic()-t, algebra_returncode=proc.returncode,
                          algebra_solver_calls=1)
            log = (work / 'singular.log').read_text()
            if proc.returncode or re.search(r'^\s*\?', log, re.M):
                raise RuntimeError('SINGULAR_ERROR')
            inverse = {v: k for k, v in ren.items()}
            elimination = parse_block(log, 'ELIM', inverse)
            basis = parse_block(log, 'LEX', inverse)
            record['elimination_polynomials'] = list(map(str, elimination))
            write_json(work / 'basis.json', {'lex_basis': list(map(str, basis))})
            nonzero = [e for e in elimination if e != 0]
            if any(not e.free_symbols for e in nonzero):
                record.update(status='algebraically_empty', answers=[], candidates=[])
            elif not nonzero:
                record.update(status='nonfinite_target', reason_code='NO_UNIVARIATE_TARGET', answers=[])
            elif any(e.free_symbols - {target} for e in nonzero):
                raise RuntimeError('INVALID_ELIMINATION_OUTPUT')
            else:
                polynomial = nonzero[0]
                for e in nonzero[1:]:
                    polynomial = sp.gcd(polynomial, e)
                candidates = exact_roots(polynomial, target)
                record['target_polynomial_factored'] = str(sp.factor(polynomial))
                record['candidates_exact'] = list(map(str, candidates))
                record['candidates'] = []
                checkpoint('lift_and_final_verify')
                t = time.monotonic()
                for c in candidates:
                    result = lift_candidate(c, target, basis, equations, factors, used, system, case, bundle, evaluator)
                    record['candidates'].append(result)
                    checkpoint('lift_and_final_verify')
                states = [c['state'] for c in record['candidates']]
                record['answers'] = [c['candidate_exact'] for c in record['candidates'] if c['state'] == 'verified']
                record['filter_seconds'] = time.monotonic()-t
                record['status'] = ('verified_complete' if 'unresolved' not in states else
                                    'verified_subset' if record['answers'] else 'lift_unresolved')
                record['set_complete'] = 'unresolved' not in states
        record['stage'] = 'finished'
    except ConversionError as exc:
        record.update(status='unsupported', reason_code=exc.code, reason=str(exc))
    except Exception as exc:
        record.update(status='error', reason_code=type(exc).__name__, reason=str(exc)[:1500])
    record['worker_wall_seconds'] = time.monotonic()-start
    write_json(output, record)


def own_tree_rss(pid):
    # Read only this worker and its descendants; never signal other jobs.
    total, pending, seen = 0, [pid], set()
    while pending:
        child = pending.pop()
        if child in seen:
            continue
        seen.add(child)
        try:
            fields = Path(f'/proc/{child}/statm').read_text().split()
            total += int(fields[1]) * os.sysconf('SC_PAGE_SIZE')
            pending.extend(map(int, Path(f'/proc/{child}/task/{child}/children').read_text().split()))
        except (FileNotFoundError, ProcessLookupError):
            pass
    return total


def child_limits():
    resource.setrlimit(resource.RLIMIT_AS, (MEM, MEM))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE, MAX_FILE))
    available = sorted(os.sched_getaffinity(0))
    slot = int(os.environ.get('EXSTRONG_SLOT', '0'))
    os.sched_setaffinity(0, {available[slot % len(available)]})


def supervise(args):
    if not args.stage_b and args.case_id not in DEV5:
        raise SystemExit('Stage A permits only dev5; use --stage-b for the future campaign')
    output = Path(args.out).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    work = output.with_suffix('.work')
    # mkdir is an atomic, persistent one-attempt ledger. Existing runs refuse.
    work.mkdir(exist_ok=False)
    start = time.monotonic()
    try:
        case = load_case(args)
        write_json(work / 'input.json', case)
    except Exception:
        write_json(output, {'id': args.case_id, 'status': 'input_error', 'attempts': 1})
        raise
    cmd = [sys.executable, str(HERE/'run_strong.py'), args.case_id, '--out', str(output), '--worker']
    peak, reason = 0, None
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1')
    with (work / 'worker.log').open('w') as log:
        process = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, env=env,
                                   start_new_session=True, preexec_fn=child_limits)
        try:
            while process.poll() is None:
                peak = max(peak, own_tree_rss(process.pid))
                if time.monotonic()-start >= 600:
                    reason = 'TIME_LIMIT'
                elif peak >= MEM:
                    reason = 'MEMORY_LIMIT'
                if reason:
                    break
                time.sleep(0.1)
        finally:
            # Also remove surviving descendants on normal worker completion.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
    if reason or not output.exists():
        progress = work / 'progress.json'
        record = json.loads(progress.read_text()) if progress.exists() else {'id': args.case_id}
        record.update(status='timeout' if reason == 'TIME_LIMIT' else 'resource_limit' if reason else 'worker_error',
                      reason_code=reason or f'WORKER_EXIT_{process.returncode}')
    else:
        record = json.loads(output.read_text())
    record.update(wall_seconds=time.monotonic()-start, peak_tree_rss_bytes=peak,
                  supervisor_returncode=process.returncode, attempts=1)
    singular_log = work / 'singular.log'
    if singular_log.exists():
        markers = re.findall(r'^STRONG_\w+', singular_log.read_text(), re.M)
        record['last_algebra_marker'] = markers[-1] if markers else None
    write_json(output, record)
    print(json.dumps({'id': args.case_id, 'status': record['status'], 'wall_seconds': record['wall_seconds']}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('case_id')
    parser.add_argument('--cases', action='append', help='JSONL input (repeatable)')
    parser.add_argument('--out', required=True)
    parser.add_argument('--stage-b', action='store_true')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    worker(args) if args.worker else supervise(args)


if __name__ == '__main__':
    main()
