"""Reveal conditions only after all primary solution grades have been recorded."""
import json
import statistics
from collections import Counter
from pathlib import Path
from qwen.common import write_json, file_hash, now
HERE=Path(__file__).resolve().parent
ROOT=Path('qwen/.runtime/exp04_exploration')
review=json.loads((HERE/'review-blinded.json').read_text())
grades=[json.loads(l) for l in (HERE/'grades.jsonl').read_text().splitlines() if l.strip()]
assert len(grades)==64 and len({r['review_id'] for r in grades})==64, 'Grade all 64 before condition comparison'
assert {r['review_id'] for r in grades}=={r['review_id'] for r in review}
receipt=json.loads((ROOT/'worker_receipt.json').read_text())
assert receipt['status']=='complete'
frozen={'grades_sha256':file_hash(HERE/'grades.jsonl'),'review_sha256':file_hash(HERE/'review-blinded.json'),'frozen_utc':now(),'grader':'Codex; exploratory single-reviewer audit, not independent blinded human review'}
if (HERE/'grading-freeze.json').exists():
    prior=json.loads((HERE/'grading-freeze.json').read_text())
    assert prior['grades_sha256']==frozen['grades_sha256'] and prior['review_sha256']==frozen['review_sha256']
else:write_json(HERE/'grading-freeze.json',frozen)
mapping={r['review_id']:r for r in json.loads((ROOT/'review-mapping.json').read_text())}
content={r['review_id']:r for r in review}
rows=[{**r,**mapping[r['review_id']], 'problem_id':content[r['review_id']]['problem_id'], 'tokens':content[r['review_id']]['completion_tokens'], 'finish_reason':content[r['review_id']]['finish_reason']} for r in grades]
for r in rows:
    r['accepted']=r['C_auto'] is True and r['V'] is True
    r['useful_accepted']=r['accepted'] and r['U_relation'] is True
    r['structural_aux_success']=r['useful_accepted'] and r['auxiliary']=='structural'
    r['target_aux_success']=r['structural_aux_success'] and r['target_auxiliary'] is True

def summarize(a):
    return {'n':len(a),'C':sum(r['C_auto'] is True for r in a),'CV':sum(r['accepted'] for r in a),
            'CV_including_local_errors_sensitivity':sum(r['C_auto'] is True and (r['V'] is True or r['status']=='local_error') for r in a),'CVU':sum(r['useful_accepted'] for r in a),
            'CVU_strong':sum(r['useful_accepted'] and r['U_strength']=='strong' for r in a),'structural_aux':sum(r['structural_aux_success'] for r in a),
            'target_aux':sum(r['target_aux_success'] for r in a),'truncated':sum(r['finish_reason']=='length' for r in a),
            'status':dict(Counter(r['status'] for r in a)),'total_tokens':sum(r['tokens'] for r in a),
            'median_tokens':statistics.median([r['tokens'] for r in a])}
summary={'all':summarize(rows),'by_condition':{c:summarize([r for r in rows if r['condition']==c]) for c in ['normal','explore']},
         'by_problem':{p:{c:summarize([r for r in rows if r['problem_id']==p and r['condition']==c]) for c in ['normal','explore']} for p in sorted({r['problem_id'] for r in rows})},
         'gpu_worker_hours':receipt['elapsed_seconds']/3600, 'updates':0,
         'useful_solution_problem_ids':sorted({r['problem_id'] for r in rows if r['useful_accepted']}),
         'structural_aux_problem_ids':sorted({r['problem_id'] for r in rows if r['structural_aux_success']}),
         'within_problem_U_variation':[], 'within_problem_strong_variation':[]}
for p in summary['by_problem']:
    a=[r for r in rows if r['problem_id']==p and r['accepted']]
    if len({r['U_relation'] for r in a})>1:summary['within_problem_U_variation'].append(p)
    if len({r['U_strength']=='strong' for r in a})>1:summary['within_problem_strong_variation'].append(p)
write_json(HERE/'graded-results.json',rows)
write_json(HERE/'summary.json',summary)
write_json(HERE/'worker-receipt.json',receipt)
print(json.dumps(summary,ensure_ascii=False,indent=2))
