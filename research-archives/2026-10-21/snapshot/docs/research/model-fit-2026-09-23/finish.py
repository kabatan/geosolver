"""Freeze the completed inference diagnostic and its manually audited results."""
import hashlib,json
from pathlib import Path
from qwen.answer_check import extract_answer,answers_equal
D=Path(__file__).resolve().parent
R=Path('qwen/.runtime/model_fit_20260923_8b')
g=json.loads((D/'grades.json').read_text())
adj=json.loads((D/'adjudications.json').read_text())
primary=json.loads((D/'graded-results.json').read_text())
assert len(primary)==56 and all(x['grade'] is not None for x in primary)
receipt=json.loads((R/'receipt.json').read_text());assert receipt['status']=='complete'
records=[];out=[]
for p in sorted(R.glob('group-*.json')):
 for x in json.loads(p.read_text()):
  key=f"original_8b:{x['id']}:{x['sample']}"
  assert key in g and not x['training_eligible']
  row={k:x[k] for k in ['id','model','sample','stratum','problem','reference','final_text','tokens','finish_reason','training_eligible']}
  row.update(grade=g[key],source=str(p),source_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
  if x['stratum']!='foundation':
   value=extract_answer(x['raw_text']);correct=answers_equal(value,x['reference']) is True
   row['numeric_parser']={'extracted':value,'correct':correct,'manual_agrees':correct==g[key]['numeric_correct']}
   assert row['numeric_parser']['manual_agrees']
  records.append(row)
  out.append('## '+x['id']+' / '+str(x['sample'])+'\n\n'+x['problem']+'\n\n'+x['final_text'].replace('<|im_end|>','')+'\n')
assert len(records)==6
shared=['B06','DA05_unassisted','DA15_unassisted']
matched={}
for model in ['original_4b','thinking_2507','original_8b']:
 rows=[r for r in primary+records if r['model']==model and r['id'] in shared]
 assert len(rows)==6
 matched[model]={}
 for task in shared:
  rr=[r for r in rows if r['id']==task]
  matched[model][task]={'n':len(rr),'valid':sum(r['grade']['valid'] for r in rr),'valid_including_local_errors':sum(bool(r['grade']['valid'] or r['grade'].get('local_error_sensitivity')) for r in rr),'numeric_correct':sum(r['grade'].get('numeric_correct',False) for r in rr),'strong':sum(r['grade']['valid'] and r['grade']['usefulness']=='strong' for r in rr),'truncated':sum(r['finish_reason']!='stop' for r in rr),'tokens':sum(r['tokens'] for r in rr)}
summary=json.loads((D/'summary.json').read_text())
combined={'answers':62,'updates':0,'primary':summary['results'],'matched_subset':matched,'cost':{'primary_successful_worker_seconds':summary['receipt']['elapsed_seconds'],'additional_8b_worker_seconds':receipt['elapsed_seconds'],'failed_setup_worker_seconds':sum(x['elapsed_seconds'] for x in summary['setup_failures']),'model_download_wall_seconds':json.loads((D/'8b-model.json').read_text())['elapsed_seconds']},'strong_successes':sum(r['grade']['valid'] and r['grade']['usefulness']=='strong' for r in primary+records),'notes':['GPU-worker wall time includes loading and teardown, not instrumented active GPU utilization','8B adaptive three-task screen is not comparable to entire four-task 4B benchmark','All outputs quarantined from training','Final answers audited, not every token of internal reasoning']}
combined['cost']['total_worker_wall_hours_including_failed_setup']=sum(combined['cost'][k] for k in ['primary_successful_worker_seconds','additional_8b_worker_seconds','failed_setup_worker_seconds'])/3600
(D/'original_8b-answers.md').write_text('\n'.join(out))
(D/'8b-graded-results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
(D/'combined-summary.json').write_text(json.dumps(combined,ensure_ascii=False,indent=2)+'\n')
files=[D/'protocol.json',D/'jobs.json',D/'8b-protocol.json',D/'8b-jobs.json',D/'grades.json',D/'adjudications.json',D/'combined-summary.json',D/'graded-results.json',D/'8b-graded-results.json']
files += sorted(Path('qwen/.runtime/model_fit_20260923_attempt04').glob('*/group-*.json'))+sorted(R.glob('group-*.json'))
(D/'manifest.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files},indent=2)+'\n')
print(json.dumps(combined,ensure_ascii=False,indent=2))
