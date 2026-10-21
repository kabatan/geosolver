import json, statistics, sys
from pathlib import Path
root = Path(__file__).resolve().parent
variant = sys.argv[1]
rows = [json.loads(x) for x in (root / f'{variant}-paired.jsonl').read_text().splitlines()]
results = []
for case in dict.fromkeys(row['case'] for row in rows):
    base = [r for r in rows if r['case'] == case and r['variant'] == 'baseline-source']
    new = [r for r in rows if r['case'] == case and r['variant'] == f'{variant}-source']
    if len(base) != 2 or len(new) != 2:
        continue
    entries = []
    for a,b in zip(base,new):
        raw = [json.loads((root / f'{variant}-source' / f'paired-{r["variant"]}-{case}-{r["repeat"]}.json').read_text()) for r in (a,b)]
        entries.append({'repeat':a['repeat'],'baseline_wall':a['outer_wall'],'candidate_wall':b['outer_wall'], 'baseline_cpu':raw[0]['diagnostics']['process_info']['cpu_seconds'], 'candidate_cpu':raw[1]['diagnostics']['process_info']['cpu_seconds'], 'baseline_exact_assembly':raw[0]['diagnostics']['phase_timings']['exact_assembly'], 'candidate_exact_assembly':raw[1]['diagnostics']['phase_timings']['exact_assembly'], 'answers_equal':a['answers'] == b['answers'], 'record_counts_equal':(a['accepted_records'],a['verification_records'],a['history_counts']) == (b['accepted_records'],b['verification_records'],b['history_counts'])})
    results.append({'case':case,'baseline_median_process_wall':statistics.median(r['baseline_wall'] for r in entries),'candidate_median_process_wall':statistics.median(r['candidate_wall'] for r in entries),'pairs':entries})
receipt = {'variant':variant,'cases':results,'all_descriptor_json_equal':all(p['answers_equal'] for r in results for p in r['pairs']),'all_record_counts_equal':all(p['record_counts_equal'] for r in results for p in r['pairs']), 'baseline_sum_process_wall':sum(p['baseline_wall'] for r in results for p in r['pairs']),'candidate_sum_process_wall':sum(p['candidate_wall'] for r in results for p in r['pairs'])}
(root / f'{variant}-paired-summary.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
