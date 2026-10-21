"""Descriptive costs and question-level outcomes; no IID-answer significance test."""
import json,statistics
from pathlib import Path
D=Path(__file__).resolve().parent
R=Path('qwen/.runtime/foundation_pilot_20260923')
g=json.loads((D/'grades.json').read_text())
result={};cost=[]
for folder in sorted(R.iterdir()):
 if not folder.is_dir() or not (folder/'receipt.json').exists():continue
 rec=json.loads((folder/'receipt.json').read_text())
 if rec.get('elapsed_seconds') is not None:
  cost.append(dict(phase=folder.name,status=rec['status'],worker_wall_seconds=rec['elapsed_seconds'],included_in_performance=folder.name!='screen-r1_8b' and rec['status']=='complete' and bool(list(folder.glob('group-*.json')))))
 if folder.name=='screen-r1_8b':continue
 rows=[x for p in sorted(folder.glob('group-*.json')) for x in json.loads(p.read_text())]
 if not rows:continue
 byid={};valid=[];graded=0
 for r in rows:
  q=g.get(f"{folder.name}:{r['id']}:{r['sample']}")
  byid.setdefault(r['id'],[]).append(None if q is None else bool(q['valid']))
  graded+=q is not None
  if q is not None and q['valid']:valid.append(r)
 ancillary=sum(g[f"{folder.name}:{r['id']}:{r['sample']}"].get('ancillary_math_error',False) for r in valid)
 result[folder.name]=dict(status=rec['status'],answers=len(rows),graded=graded,valid=len(valid),additional_ancillary_error_exclusions=ancillary,valid_after_ancillary_exclusions=len(valid)-ancillary,question_valid_samples=byid,all_samples_valid=sum(all(v is True for v in x) for x in byid.values()),at_least_one_valid=sum(any(v is True for v in x) for x in byid.values()),total_tokens=sum(r['tokens'] for r in rows),median_tokens=statistics.median(r['tokens'] for r in rows),mean_tokens=statistics.mean(r['tokens'] for r in rows),valid_mean_tokens=statistics.mean(r['tokens'] for r in valid) if valid else None,worker_wall_seconds=rec.get('elapsed_seconds'))
(D/'detailed-metrics.json').write_text(json.dumps(result,indent=2)+'\n')
(D/'costs.json').write_text(json.dumps(dict(note='Worker wall time includes model loading; this is not an exact GPU-active-time measurement. Invalid tokenizer, first FT, and failed fidelity attempts are included in expenditure. CPU preparation/grading/downloads are excluded. One standalone adapter-reload diagnostic took approximately four additional seconds but has no timed receipt and is not included in this sum.',runs=cost,total_worker_hours=sum(r['worker_wall_seconds'] for r in cost)/3600),indent=2)+'\n')
print(json.dumps(result,indent=2))
