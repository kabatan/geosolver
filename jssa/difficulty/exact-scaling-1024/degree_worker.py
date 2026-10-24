"""Degree/dimension only. Never imports or runs GeoSolver's solving engine."""
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
CONVERTER = Path('/tmp/q6-tools/exact_comparison/benchmarks/exact_comparison')
STRONG = HERE.parent / 'exact-strong-1024'
MAX_FILE = 2_900_000


def save(path, obj):
    text = json.dumps(obj, ensure_ascii=False, indent=2, default=str) + '\n'
    if len(text.encode()) > MAX_FILE:
        raise ValueError('ARTIFACT_SIZE_LIMIT')
    Path(path).write_text(text)


def alarm(_sig, _frame):
    raise TimeoutError('translation wall limit')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('input')
    ap.add_argument('mode', choices=['base', 'strong', 'base_target'])
    ap.add_argument('out')
    ap.add_argument('--cas-seconds', type=float, default=30)
    ap.add_argument('--translation-seconds', type=int, default=20)
    ap.add_argument('--eliminate', action='store_true')
    a = ap.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    os.environ.update(PATH='/tmp/q6-tools/bin:' + os.environ['PATH'],
                      OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                      MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
    os.environ.pop('EXACT_CAPTURE_DIR', None)
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(CONVERTER), str(STRONG)]
    resource.setrlimit(resource.RLIMIT_AS, (2 << 30, 2 << 30))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE, MAX_FILE))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    rec = dict(mode=a.mode, status='PENDING', degree_label='次数不明',
               cas_limit_s=a.cas_seconds, translation_limit_s=a.translation_seconds,
               memory_address_space_bytes=2 << 30)
    t0 = time.monotonic()
    phase = 'translation'
    try:
        signal.signal(signal.SIGALRM, alarm)
        signal.alarm(a.translation_seconds)
        import sympy as sp
        from algebraize import translate
        from run_exact import build, poly_str
        case = json.loads(Path(a.input).read_text())
        dsl = case.get('dsl', case)
        target = None
        if a.mode == 'strong':
            from strong_translate import translate as strong_translate
            from run_strong import prepare
            system, target = strong_translate(dsl)
            equations, factors, used = prepare(system, target)
            rec['r4_zero_dsl_variables'] = not bool(dsl['variables'])
        else:
            system, target = translate(dsl, mode='fresh', with_target=a.mode == 'base_target')
            equations, used, factors = build(system, rabinowitsch=True)
        rec.update(nvars=len(used), neqs=len(equations), nonzero_factors=len(factors),
                   omitted_dsl_variables=[str(v) for v in system.dsl_vars
                                          if v not in used and v not in system.angle_vars],
                   max_equation_degree=max((sp.Poly(e, *used).total_degree()
                                            for e in equations), default=0))
        ren = {v: sp.Symbol(f'x{i+1}') for i, v in enumerate(used)}
        if not used:
            rec.update(status='OK_ZERO_DIMENSIONAL', dimension=0, degree=1,
                       degree_label='1', cas_wall_s=0, translation_wall_s=time.monotonic()-t0,
                       note='Polynomial ring Q with no indeterminates/equations; omitted DSL variables listed separately.')
            save(out, rec)
            return
        lines = ['LIB "elim.lib";', 'option(redSB);',
                 'ring R=0,(' + ','.join(map(str, ren.values())) + '),dp;', 'short=0;',
                 'ideal J=' + (',\n'.join(poly_str(e.xreplace(ren)) for e in equations) or '0') + ';']
        if a.mode == 'strong':
            for i, f in enumerate(factors):
                lines += [f'J=sat(J,ideal({poly_str(f.xreplace(ren))}));',
                          f'print("SAT_FACTOR={i+1}");']
        lines += ['ideal G=std(J);', 'print("DIM="+string(dim(G)));',
                  'print("DEG="+string(mult(G)));', 'print("VDIM="+string(vdim(G)));']
        if a.eliminate and target is not None:
            others = '*'.join(str(ren[v]) for v in used if v != target)
            lines += [f'ideal E=eliminate(G,{others});' if others else 'ideal E=G;',
                      'print("ELIM_BEGIN");',
                      'for(int j=1;j<=size(E);j++){print("POLY_BEGIN");print(E[j]);print("POLY_END");}',
                      'print("ELIM_END");']
            rec['target_singular_variable'] = str(ren[target])
        lines += ['quit;']
        script = '\n'.join(lines) + '\n'
        if len(script.encode()) > MAX_FILE:
            raise ValueError('ARTIFACT_SIZE_LIMIT')
        inp = out.with_suffix('.sing')
        inp.write_text(script)
        rec.update(status='CAS_RUNNING', translation_wall_s=time.monotonic()-t0,
                   script_sha256=hashlib.sha256(script.encode()).hexdigest())
        save(out, rec)
        signal.alarm(0)
        phase = 'cas'
        start = time.monotonic()
        with out.with_suffix('.log').open('w') as log:
            p = subprocess.Popen(['Singular', '-q', str(inp)], stdout=log, stderr=subprocess.STDOUT)
            try:
                p.wait(timeout=a.cas_seconds)
            except subprocess.TimeoutExpired:
                # Only our direct child, never an unrelated process.
                p.kill()
                p.wait()
                rec.update(status='DEGREE_TIMEOUT', reason='Singular wall limit')
        rec['cas_wall_s'] = time.monotonic()-start
        text = out.with_suffix('.log').read_text(errors='replace')
        dim = re.search(r'^DIM=(-?\d+)\s*$', text, re.M)
        deg = re.search(r'^DEG=(-?\d+)\s*$', text, re.M)
        if dim and deg:
            d, n = int(dim[1]), int(deg[1])
            rec.update(status='OK_ZERO_DIMENSIONAL' if d == 0 else
                       'POSITIVE_DIMENSIONAL' if d > 0 else 'EMPTY_IDEAL',
                       dimension=d, degree=n, degree_label=str(n))
            if d > 0:
                rec['reason'] = 'NONFINITE_COMPLEX_CONFIGURATIONS'
            if a.eliminate:
                match = re.search(r'ELIM_BEGIN\n(.*?)ELIM_END', text, re.S)
                if match:
                    rec['elimination_polynomials'] = [re.sub(r'\s+', '', p) for p in
                        re.findall(r'POLY_BEGIN\n(.*?)POLY_END', match[1], re.S)]
                else:
                    rec['elimination_status'] = 'ELIMINATION_TIMEOUT' if p.returncode < 0 else 'ELIMINATION_ERROR'
        elif rec['status'] != 'DEGREE_TIMEOUT':
            rec.update(status='MEMORY_LIMIT' if 'memory' in text.lower() else 'CAS_ERROR',
                       reason=f'returncode={p.returncode}; ' + text[-900:])
    except TimeoutError as exc:
        rec.update(status='TRANSLATION_TIMEOUT', reason=str(exc))
    except MemoryError:
        rec.update(status='MEMORY_LIMIT', reason=phase)
    except Exception as exc:
        from algebraize import Unsupported
        code = getattr(exc, 'code', '')
        rec.update(status='TRANSLATION_UNSUPPORTED' if isinstance(exc, Unsupported)
                   else 'ARTIFACT_SIZE_LIMIT' if str(exc) == 'ARTIFACT_SIZE_LIMIT'
                   else 'TRANSLATION_ERROR' if phase == 'translation' else 'CAS_ERROR',
                   reason=code or type(exc).__name__, detail=str(exc)[:1000])
    finally:
        signal.alarm(0)
        rec['worker_wall_s'] = time.monotonic()-t0
        if phase == 'translation':
            rec['translation_wall_s'] = rec['worker_wall_s']
        save(out, rec)


if __name__ == '__main__':
    main()
