"""Aggregate adaptive diagnostics only after their final-answer grades are saved."""
import json
import statistics
from collections import Counter
from pathlib import Path
from qwen.common import write_json, file_hash, now

HERE=Path(__file__).resolve().parent
ROOT=Path('qwen/.runtime/exp04_exploration')
review=json.loads((HERE/'diagnostic-responses.json').read_text())
grades=[json.loads(l) for l in (HERE/'diagnostic-grades.jsonl').read_text().splitlines() if l.strip()]
assert len({r['review_id'] for r in grades})==len(grades)
assert {r['review_id'] for r in grades}=={r['review_id'] for r in review}
receipts={}
for stage in {r['stage'] for r in review}:
    receipt=json.loads((ROOT/('diagnostic-'+stage)/'worker_receipt.json').read_text())
    assert receipt['status']=='complete'
    receipts[stage]=receipt
assert sum(r['stage']=='meaningful' for r in review)==32
freeze={'grades_sha256':file_hash(HERE/'diagnostic-grades.jsonl'),'responses_sha256':file_hash(HERE/'diagnostic-responses.json'),'frozen_utc':now()}
if (HERE/'diagnostic-grading-freeze.json').exists():
    old=json.loads((HERE/'diagnostic-grading-freeze.json').read_text())
    assert old['grades_sha256']==freeze['grades_sha256'] and old['responses_sha256']==freeze['responses_sha256']
else:write_json(HERE/'diagnostic-grading-freeze.json',freeze)
content={r['review_id']:r for r in review}
mapping={r['review_id']:r for r in json.loads((ROOT/'diagnostic-review-mapping.json').read_text())}
rows=[{**content[r['review_id']],**r,**mapping[r['review_id']]} for r in grades]
for r in rows:
    r['accepted']=r['C_auto'] is True and r['V'] is True
    r['useful_accepted']=r['accepted'] and r['U_relation'] is True

def summarize(a):
    return {'n':len(a),'C':sum(r['C_auto'] is True for r in a),'CV':sum(r['accepted'] for r in a),'CVU':sum(r['useful_accepted'] for r in a),
            'CVU_strong':sum(r['useful_accepted'] and r['U_strength']=='strong' for r in a),
            'CV_including_local_errors_sensitivity':sum(r['C_auto'] is True and (r['V'] is True or r['status']=='local_error') for r in a),
            'truncated':sum(r['finish_reason']=='length' for r in a),'total_tokens':sum(r['tokens'] for r in a),
            'median_tokens':statistics.median(r['tokens'] for r in a),'status':dict(Counter(r['status'] for r in a))}

primary=json.loads((HERE/'graded-results.json').read_text())
combined=primary+[{**r,'problem_id':r['id']} for r in rows if r['stage']=='meaningful']
summary={'by_stage':{stage:summarize([r for r in rows if r['stage']==stage]) for stage in receipts},
         'comparison':{c:summarize([r for r in combined if r['condition']==c]) for c in ['normal','explore','meaningful']},
         'by_problem':{p:{c:summarize([r for r in combined if r['problem_id']==p and r['condition']==c]) for c in ['normal','explore','meaningful']} for p in sorted({r['problem_id'] for r in combined})},
         'useful_solution_problem_ids':sorted({r['problem_id'] for r in combined if r['useful_accepted']}),
         'within_problem_U_variation':[], 'within_problem_strong_variation':[],
         'updates':0,'adaptive_comparison':True,
         'gpu_worker_hours':(json.loads((ROOT/'worker_receipt.json').read_text())['elapsed_seconds']+sum(r['elapsed_seconds'] for r in receipts.values()))/3600}
if 'clarification' in receipts:
    summary['clarification_given_order_correct']=sum(r.get('given_order_correct') is True for r in rows if r['stage']=='clarification')
for p in summary['by_problem']:
    a=[r for r in combined if r['problem_id']==p and r['accepted']]
    if len({r['U_relation'] for r in a})>1:summary['within_problem_U_variation'].append(p)
    if len({r['U_strength']=='strong' for r in a})>1:summary['within_problem_strong_variation'].append(p)
write_json(HERE/'diagnostic-graded-results.json',rows)
write_json(HERE/'diagnostic-summary.json',summary)
write_json(HERE/'diagnostic-worker-receipts.json',receipts)
print(json.dumps(summary,ensure_ascii=False,indent=2))
