"""Smoke-only observation; no solver source edits and no answer/grade recording.

Inherited by EngineRunner and symbolic workers through PYTHONPATH. Profiling
records actual calls and ablated() return values; it does not replace functions.
"""
import atexit
import json
import os
import sys
from collections import Counter
from pathlib import Path

if os.environ.get('S8_SMOKE_TRACE'):
    root = os.environ['S8_SOURCE_ROOT'].rstrip('/') + '/src/geosolver/'
    dest = Path(os.environ['S8_SMOKE_TRACE'])
    dest.mkdir(exist_ok=True, parents=True)
    stream = (dest / (str(os.getpid()) + '.jsonl')).open('x', buffering=1)
    counts = Counter()
    seen = set()
    observed = {'_import_pynomad', 'run_search', '_run_scipy_search_pass',
        'run_rescue_search', 'search_algebraic_branches', 'search_positive_scale_chart',
        'select_residual_candidates', 'derivative_plan', 'evaluate_jacobian',
        '_smooth_zero_constraint_residuals', '_resolve_ordered_search_attempts',
        '_run_findroot_closure'}

    def emit(record):
        stream.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + '\n')

    emit(dict(event='process_start', pid=os.getpid(), ppid=os.getppid(), argv=sys.argv,
        environment={k: v for k, v in os.environ.items() if k.startswith('GEOSOLVER_ABLATE_')},
        affinity=sorted(os.sched_getaffinity(0))))

    def profile(frame, event, arg):
        if event not in ('call', 'return'):
            return
        file = frame.f_code.co_filename
        if not file.startswith(root):
            return
        relative = file[len(root):]
        name = frame.f_code.co_name
        if name == 'ablated' and event == 'return':
            caller = frame.f_back
            key = ('gate', frame.f_locals.get('name'), caller.f_code.co_filename,
                   caller.f_lineno, bool(arg))
            counts['gate:' + str(key[1]) + ':' + str(bool(arg))] += 1
            if key not in seen:
                seen.add(key)
                emit(dict(event='gate', switch=key[1], disabled=bool(arg),
                    caller=caller.f_code.co_filename.removeprefix(root), line=caller.f_lineno))
        elif name in observed:
            key = (event, relative, name)
            counts[':'.join(key)] += 1
            if key not in seen:
                seen.add(key)
                rec = dict(event=event, file=relative, function=name)
                if event == 'call' and 'search_mode' in frame.f_locals:
                    rec['search_mode'] = frame.f_locals['search_mode']
                if event == 'return' and name == '_resolve_ordered_search_attempts' and arg is not None:
                    rec['attempt_count'] = len(arg)
                if event == 'return' and name == 'derivative_plan':
                    rec['plan_available'] = arg is not None
                    if arg is not None:
                        rec['requires_smoothing'] = bool(arg.get('requires_smoothing'))
                if event == 'return' and name == 'select_residual_candidates' and arg is not None:
                    rec['selected_count'] = len(arg)
                if event == 'return' and name in ('search_algebraic_branches', 'search_positive_scale_chart'):
                    rec['produced_batch'] = arg is not None
                if event == 'return' and name == '_import_pynomad':
                    rec['import_succeeded'] = arg is not None
                emit(rec)

    sys.setprofile(profile)

    @atexit.register
    def finish():
        sys.setprofile(None)
        emit(dict(event='process_exit', counts=dict(counts)))
        stream.close()
