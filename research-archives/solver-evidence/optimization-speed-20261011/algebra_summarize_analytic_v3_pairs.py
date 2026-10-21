import argparse
from collections import defaultdict
import json
from pathlib import Path
import statistics

from pydantic import TypeAdapter
from geosolver.problem.models import ExactAnswer

parser=argparse.ArgumentParser()
parser.add_argument('directory')
parser.add_argument('variant')
args=parser.parse_args()
root=Path(__file__).resolve().parent
rows=[json.loads(line) for line in (root/args.directory/'records.jsonl').read_text().splitlines()]
groups=defaultdict(lambda:defaultdict(list))
adapter=TypeAdapter(ExactAnswer)


def keys(row):
    return sorted({json.dumps(adapter.validate_python(a).canonical_key()) for a in row['answers']})


for row in rows:
    groups[row['case']][row['variant']].append(row)
complete={name:group for name,group in groups.items() if len(group['baseline-source'])==len(group[args.variant])==2}
pairs=[]
for name,group in complete.items():
    before=group['baseline-source'];after=group[args.variant]
    pairs.append({'id':name,'baseline_mean_seconds':statistics.mean(r['process_wall_seconds'] for r in before),
                  'candidate_mean_seconds':statistics.mean(r['process_wall_seconds'] for r in after),
                  'same_canonical_answers_all_four':len({tuple(keys(r)) for r in before+after})==1,
                  'answer_keys':[{'variant':r['variant'],'repeat':r['repeat'],'keys':keys(r)} for r in before+after],
                  'phase_means':{v:{phase:statistics.mean(row['phase_timings'].get(phase,0) for row in rs) for phase in ('search','refinement','exact_assembly')} for v,rs in group.items()}})
out={'record_count':len(rows),'complete_problem_count':len(pairs),'all_four_answer_set_agreement_count':sum(r['same_canonical_answers_all_four'] for r in pairs),
     'sum_of_baseline_problem_means':sum(r['baseline_mean_seconds'] for r in pairs),
     'sum_of_candidate_problem_means':sum(r['candidate_mean_seconds'] for r in pairs),
     'median_baseline_problem_means':statistics.median(r['baseline_mean_seconds'] for r in pairs) if pairs else None,
     'median_candidate_problem_means':statistics.median(r['candidate_mean_seconds'] for r in pairs) if pairs else None,
     'pairs':sorted(pairs,key=lambda r:r['candidate_mean_seconds']-r['baseline_mean_seconds'])}
for pair in pairs:
    before = pair['baseline_mean_seconds']; after = pair['candidate_mean_seconds']
    pair['saved_seconds'] = before - after
    pair['relative_reduction'] = 1 - after / before
    group = complete[pair['id']]
    by_repeat = {v: {r['repeat']: r for r in rs} for v, rs in group.items()}
    pair['repeat_reductions'] = [1 - by_repeat[args.variant][i]['process_wall_seconds'] / by_repeat['baseline-source'][i]['process_wall_seconds'] for i in (0,1)]
    pair['answer_deltas_by_repeat'] = [{'repeat': i, 'added': sorted(set(keys(by_repeat[args.variant][i])) - set(keys(by_repeat['baseline-source'][i]))), 'missing': sorted(set(keys(by_repeat['baseline-source'][i])) - set(keys(by_repeat[args.variant][i])))} for i in (0,1)]
    pair['both_repeats_faster'] = all(x > 0 for x in pair['repeat_reductions'])
    pair['counter_means'] = {v: {k: statistics.mean(row['counters'].get(k, 0) for row in rs) for k in sorted({key for row in rs for key in row['counters']})} for v, rs in group.items()}
    pair['candidate_analytic_evaluation_mean'] = pair['counter_means'][args.variant].get('analytic_jacobian_evaluations', 0)
    pair['statuses'] = [{'variant': r['variant'], 'repeat': r['repeat'], 'status': r['status']} for rs in group.values() for r in rs]
out['gain_count'] = sum(p['saved_seconds'] > 0 for p in pairs)
out['loss_count'] = sum(p['saved_seconds'] < 0 for p in pairs)
out['tie_count'] = sum(p['saved_seconds'] == 0 for p in pairs)
out['gain_at_least_10_percent_count'] = sum(p['relative_reduction'] >= .1 for p in pairs)
out['loss_at_least_10_percent_count'] = sum(p['relative_reduction'] <= -.1 for p in pairs)
out['both_repeats_faster_count'] = sum(p['both_repeats_faster'] for p in pairs)
out['sum_problem_means_reduction'] = 1 - out['sum_of_candidate_problem_means'] / out['sum_of_baseline_problem_means']
out['median_of_per_problem_relative_reductions'] = statistics.median(p['relative_reduction'] for p in pairs)
out['source_hashes'] = {v: sorted({r['source_hash'] for r in rows if r['variant'] == v}) for v in ('baseline-source', args.variant)}
out['process_status_counts'] = {s: sum(r['status'] == s for r in rows) for s in sorted({r['status'] for r in rows})}
out['all_complete'] = len(rows) == 96 and len(pairs) == 24
out['answer_gain_case_count'] = sum(any(d['added'] for d in p['answer_deltas_by_repeat']) for p in pairs)
out['answer_loss_case_count'] = sum(any(d['missing'] for d in p['answer_deltas_by_repeat']) for p in pairs)
out['candidate_analytic_used_case_count'] = sum(p['candidate_analytic_evaluation_mean'] > 0 for p in pairs)
out['gain_loss_definition'] = 'Compare candidate versus baseline mean of two fresh-process wall times per case; positive reduction is faster. Tiny differences include shared-host noise.'

(root/args.directory/'comparison.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({key:value for key,value in out.items() if key!='pairs'},indent=2))
