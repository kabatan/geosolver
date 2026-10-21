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
(root/args.directory/'comparison.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({key:value for key,value in out.items() if key!='pairs'},indent=2))
