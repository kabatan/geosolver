import json, os, subprocess, time
from pathlib import Path
root = Path(__file__).resolve().parent
runtime = Path('/home/kabatan/work/solver/.venv/bin/python')
cases = ['HMMT-2013-FEB-GEO-04', 'AIME-2011-II-02', 'HMMT-2007-FEB-GEO-09', 'HMMT-2020-FEB-GEO-05', 'AIME-2010-II-14', 'HMMT-2025-FEB-GEO-09', 'JMO-2023-PRE-03', 'AIME-2006-I-01']
for repeat in range(2):
    for case in cases:
        variants = ['baseline-source', 'evaluation-slice-source']
        if repeat:
            variants.reverse()
        for variant in variants:
            env = os.environ.copy()
            env['PYTHONPATH'] = str(root/variant/'src')
            for name in ['OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS']:
                env[name] = '1'
            output = root/'evaluation-slice-source'/f'paired-{variant}-{case}-{repeat}.json'
            start = time.monotonic()
            result = subprocess.run([str(runtime), '-m', 'geosolver.application.cli', 'solve', str(root/variant/'benchmarks/dsl'/(case+'.json')), '--time-limit-seconds', '180', '--cores', '1', '--seed', '0', '--output', str(output)], env=env, cwd=root/variant, capture_output=True, text=True, timeout=190)
            outer = time.monotonic() - start
            if result.returncode:
                raise RuntimeError(result.stderr)
            solver = json.loads(output.read_text())
            summary = (solver.get('diagnostics') or {}).get('pipeline_summary') or {}
            print(json.dumps({'case':case,'variant':variant,'repeat':repeat,'outer_wall':outer,'solver_wall':solver['elapsed_seconds'],'source_hash':solver['engine']['source_hash'],'status':solver['status'],'answers':solver['answers'],'accepted_records':summary.get('exact_assembly',{}).get('accepted_count'),'verification_records':len(summary.get('verification_records',[])),'history_counts':[len(x['candidate']['verification_history']) for x in summary.get('exact_candidate_records',[])]}),flush=True)
