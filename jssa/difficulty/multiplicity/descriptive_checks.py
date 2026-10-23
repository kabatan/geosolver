"""Post-run descriptive sensitivity and independent checks; no new refinement.

80 digits is the registered primary threshold. 120/320 are reported to avoid
hiding precision regressions; they are not substituted into the predictions.
"""
import json
import csv
from pathlib import Path
from collections import Counter
import platform
import numpy
import scipy
import mpmath
import sympy
import experiment as e

e.verify_lock()
manifest = json.loads((e.HERE / 'manifest.json').read_text())
rows = [json.loads(p.read_text()) for p in sorted((e.HERE / 'runs').glob('*.json'))]
summary = json.loads((e.HERE / 'summary.json').read_text())
out = []
for threshold in (50, 80, 120, 320):
    for variant in e.VARIANTS:
        cases, candidate_pass, failure = set(), 0, Counter()
        for r in rows:
            if r['variant'] != variant:
                continue
            passable = not (r['status'] != 'returned' or r.get('deadline_hit') or r.get('score_error'))
            eligible = [o for o in r['outputs'] if (o['digits'] is not None and o['digits'] >= threshold
                        and o['guard'] and o['hard'] and o['bounds'] and o['answer_finite'])]
            if passable and eligible:
                candidate_pass += 1
                cases.add(r['id'])
            if r.get('deadline_hit'):
                failure['deadline'] += 1
            elif not eligible:
                failure['below_threshold_or_invalid'] += 1
        out.append(dict(digits=threshold, variant=variant, cases=len(cases), all_cases=len(manifest),
                        candidates=candidate_pass, all_candidates=sum(r['variant']==variant for r in rows),
                        case_ids=';'.join(sorted(cases))))
        if threshold == 80:
            expected = next(v for v in summary['aggregate'] if v['variant']==variant)
            assert expected['case_pass'] == len(cases)
            assert expected['candidate_pass'] == candidate_pass
e.csv_write(e.HERE / 'precision-sensitivity.csv', out)
statuses = Counter((r['variant'], o['internal_status']) for r in rows for o in r['outputs'])
e.csv_write(e.HERE / 'internal-status-counts.csv', [dict(variant=v,status=s,count=c) for (v,s),c in sorted(statuses.items())])
case_results = []
for c in manifest:
    data = [r for r in rows if r['id']==c['id']]
    if not data:
        continue
    best = {v:max((o['digits'] for r in data if r['variant']==v for o in r['outputs'] if o['digits'] is not None),default=None) for v in e.VARIANTS}
    if best['A'] is not None and best['O'] is not None and best['A'] < best['O'] - 1:
        case_results.append(dict(id=c['id'],O_best=best['O'],A_best=best['A'],lost_digits=best['O']-best['A']))
e.csv_write(e.HERE / 'precision-regressions.csv',case_results)
case_table = list(csv.DictReader((e.HERE / 'per-case.csv').open()))
dimensions = []
for n in sorted({int(r['n_vars']) for r in case_table if int(r['n_candidates'])}):
    for q in ('True', 'False'):
        selected = [r for r in case_table if int(r['n_vars']) == n and int(r['n_candidates']) and r['q_active'] == q]
        dimensions.append(dict(n_vars=n, q_active=q, n=len(selected), O_stalls=sum(r['O_stall']=='True' for r in selected)))
e.csv_write(e.HERE / 'strata-by-dimension.csv',dimensions)
environment = dict(utc=e.now(),python=platform.python_version(),numpy=numpy.__version__,scipy=scipy.__version__,
                   mpmath=mpmath.__version__,sympy=sympy.__version__,machine=platform.machine(),
                   platform=platform.platform(),src_sha256=e.source_fingerprint()[0],
                   primary_independently_checked=True)
e.dump(e.HERE / 'environment.json', environment)
print(json.dumps(dict(sensitivity=[{k:v for k,v in r.items() if k!='case_ids'} for r in out],precision_regressions=case_results),ensure_ascii=False,indent=2))
