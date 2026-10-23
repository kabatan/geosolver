"""Read existing Q27c data; write only beside this script. No local search."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics as st
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
Q21 = ROOT / 'jssa/strategy/astra-consult-18/q21b-number-theory'
INPUTS = {}


def read(path):
    path = Path(path)
    if not path.is_absolute():
        path = ROOT / path
    assert 'unseen' not in str(path) and 'sealed' not in str(path)
    b = path.read_bytes()
    INPUTS[str(path.relative_to(ROOT))] = hashlib.sha256(b).hexdigest()
    return b.decode()


def rows(path):
    return list(csv.DictReader(read(path).splitlines()))


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def table(name, data):
    if not data:
        return
    fields = list(dict.fromkeys(k for r in data for k in r))
    with (OUT / name).open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(data)


def digits(s):
    v = abs(Decimal(str(s)))
    return None if v == 0 else -float(v.log10())


def main():
    summary = {}
    basins = rows('jssa/difficulty/minima/basins-323.csv')
    rawcases, inventories = [], []
    for seed, folder in [(0, 'raw-323'), (1, 'raw-323-seed1')]:
        nrec = 0
        nfiles = 0
        fieldcounts = Counter()
        statuses = Counter()
        for path in sorted((ROOT / 'jssa/difficulty/minima' / folder).glob('*.json')):
            nfiles += 1
            d = json.loads(read(path))
            records = d.get('records', [])
            nrec += len(records)
            for r in records:
                fieldcounts.update(r.keys())
                statuses[r.get('cls', '')] += 1
            rawcases.append(dict(id=d['case_id'], seed=seed, n_records=len(records),
                                 n_hit=sum(r.get('cls') == 'hit' for r in records),
                                 p=d.get('p_any'), n_vars=d.get('n_vars')))
        inventories.append(dict(seed=seed, files=nfiles, records=nrec,
                                record_field_counts=dict(fieldcounts), classes=dict(statuses)))
    table('basin-seed-audit.csv', rawcases)
    summary['raw_inventory'] = inventories

    stage = rows('jssa/results/stage-profile-20261023/per-case.csv')
    table('stage-problem-summary.csv', [dict(
        id=identifier, runs=len(z), correct=sum(r['correct'] == 'True' for r in z),
        refine_median=st.median(float(r['refinement_time_s']) for r in z),
        identify_median=st.median(float(r['identification_verification_time_s']) for r in z),
        wall_median=st.median(float(r['wall_time_s']) for r in z),
        sources=';'.join(r['final_answer_source'] for r in z))
        for identifier in sorted({r['case_id'] for r in stage})
        for z in [[r for r in stage if r['case_id'] == identifier]]])
    summary['full_solver'] = dict(runs=len(stage), problems=len({r['case_id'] for r in stage}),
        correct=sum(r['correct'] == 'True' for r in stage),
        attempted=sum(int(r['candidates_sent_to_refinement']) for r in stage),
        converged=sum(int(r['candidates_converged']) for r in stage),
        refinement_median=st.median(float(r['refinement_time_s']) for r in stage),
        identification_median=st.median(float(r['identification_verification_time_s']) for r in stage))

    prec = rows(Q21 / 'precision.csv')
    vals = rows(Q21 / 'precision-per-value.csv')
    degrees = []
    for degree in range(1, 5):
        subset = [r for r in vals if int(r['degree']) == degree]
        degrees.append(dict(degree=degree, values=len(subset), problems=len({r['id'] for r in subset}),
            stable_grid_counts=dict(Counter(r['stable_correct_grid'] or 'none' for r in subset)),
            median_heuristic=st.median(float(r['heuristic_digits']) for r in subset),
            nonmonotone_ids=[r['id'] for r in subset if r['nonmonotone'] == 'True']))
    summary['precision_degrees'] = degrees
    summary['pslq_80_wrong'] = [r for r in prec if r['precision'] == '80' and r['status'] == 'wrong']
    summary['precision_grid_total'] = len(prec)
    table('precision-degree-summary.csv', [{**r, 'stable_grid_counts':json.dumps(r['stable_grid_counts']),
        'nonmonotone_ids':';'.join(r['nonmonotone_ids'])} for r in degrees])

    read('jssa/difficulty/multiplicity/experiment.py')
    read('jssa/difficulty/multiplicity/preregistration.md')
    event_rows, runrows = [], []
    for path in sorted((ROOT / 'jssa/difficulty/multiplicity/runs').glob('*.json')):
        d = json.loads(read(path))
        for oi, out in enumerate(d.get('outputs', [])):
            parsed = []
            for hi, event in enumerate(out.get('history', [])):
                p = event.split(':')
                if len(p) != 3:
                    continue
                if p[0] == 'direct':
                    dp, method = int(p[1]), 'direct'
                elif p[0].isdigit():
                    dp, method = int(p[0]), p[1]
                else:
                    continue
                try:
                    nd = digits(p[2])
                except Exception:
                    continue
                entry = dict(id=d['id'], index=d['index'], variant=d['variant'], output=oi,
                             event_index=hi, dps=dp, method=method, norm=p[2], digits=nd,
                             zero=nd is None)
                parsed.append(entry)
                event_rows.append(entry)
            lm = {r['dps']:r for r in parsed if r['dps'] in [50,100,120]
                  and r['method'] not in ['promote','warm_newton','findroot','direct']}
            gain = None
            if 50 in lm and 100 in lm and all(lm[k]['digits'] is not None for k in [50,100]):
                gain = lm[100]['digits'] - lm[50]['digits']
            plateau = gain is not None and abs(gain) < 1 and 8 < lm[50]['digits'] < 30
            rebound = any(a['zero'] and not b['zero'] and b['dps'] > a['dps']
                          for i,a in enumerate(parsed) for b in parsed[i+1:])
            best = out.get('digits')
            runrows.append(dict(id=d['id'], index=d['index'], variant=d['variant'], output=oi,
                passed=bool(out.get('passed')), lm50_digits=lm.get(50,{}).get('digits'),
                lm100_digits=lm.get(100,{}).get('digits'), stage_gain= gain, plateau=plateau,
                final_digits=best, rescued_plateau=bool(plateau and out.get('passed') and best >=80),
                zero_rebound=rebound, history=json.dumps(out.get('history',[]))))
    table('refinement-events.csv', event_rows)
    table('refinement-observations.csv', runrows)
    orig = [r for r in runrows if r['variant']=='O']
    plateau = [r for r in orig if r['plateau']]
    rescued = [r for r in orig if r['rescued_plateau']]
    reb = [r for r in orig if r['zero_rebound']]
    summary['refinement'] = dict(total_outputs=len(runrows), original_outputs=len(orig),
        original_problems=len({r['id'] for r in orig}),
        finite_stage_pairs=sum(r['stage_gain'] is not None for r in orig),
        plateaus=len(plateau), plateau_problems=len({r['id'] for r in plateau}),
        plateau_gain_median=st.median(r['stage_gain'] for r in plateau),
        rescued=len(rescued), rescued_problems=len({r['id'] for r in rescued}),
        rescue_gain_median=st.median(r['final_digits']-r['lm100_digits'] for r in rescued),
        zero_rebounds=len(reb), zero_rebound_problems=len({r['id'] for r in reb}),
        zero_rebound_ids=sorted({r['id'] for r in reb}),
        plateau_by_problem={i:sum(r['id']==i for r in plateau) for i in sorted({r['id'] for r in plateau})})

    # Context checks; these tables do not supply per-iteration precision trajectories.
    msolve = rows('jssa/strategy/astra-consult-18/Q24/source-msolve-cases.csv')
    gmb = rows('jssa/results/gmb-success-definition/per-trial.csv')
    feasibility = [rows(f'jssa/difficulty/start-feasibility-1023/{name}') for name in
                   ['per-problem.csv','per-problem-seed1.csv']]
    extra = [json.loads(s) for s in read('benchmarks/extra-variables/cases.jsonl').splitlines() if s.strip()]
    summary['context_inventory'] = dict(msolve_rows=len(msolve),
        msolve_classes=dict(Counter(r['msolve_class'] for r in msolve)),
        gmb_rows=len(gmb), gmb_fields=list(gmb[0]),
        feasibility_rows=[len(x) for x in feasibility],
        extra_input_rows=len(extra),
        extra_measured_results_in_requested_folder=False)

    old = json.loads(read(Q21 / 'manifest.json'))
    matches = {}
    for p in ['src/geosolver/exact/polynomial_search.py',
              'src/geosolver/exact/polynomial_search_helpers.py',
              'src/geosolver/engine/standard/refinement/mpmath_refiner.py',
              'src/geosolver/engine/standard/refinement/refiner_config.py']:
        read(p)
        matches[p] = INPUTS[p] == old['source_hashes'].get(p)
    summary['q21_source_hash_matches'] = matches
    dump('exploration-summary.json', summary)
    dump('input-manifest.json', dict(utc=datetime.now(timezone.utc).isoformat(),
         python=sys.executable, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         inputs=INPUTS))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
