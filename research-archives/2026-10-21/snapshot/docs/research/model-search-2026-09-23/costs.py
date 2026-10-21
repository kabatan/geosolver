"""Summarize observed worker wall time and accepted-answer costs, not GPU utilization integrals."""
import json
from pathlib import Path
D=Path(__file__).resolve().parent
R=Path('qwen/.runtime/model_search_20260923_v2')
g=json.loads((D/'grades.json').read_text()) if (D/'grades.json').exists() else {}
rows=[]
for folder in sorted(R.iterdir()):
 if not folder.is_dir():continue
 sec=0;tokens=0;valid=0;strong=0;n=0
 for p in sorted(folder.glob('group-*.json')):
  answers=json.loads(p.read_text());sec+=answers[0]['elapsed_group_seconds']
  for a in answers:
   tokens+=a['tokens'];n+=1
   grade=g.get(f"{folder.name}:{a['id']}:{a['sample']}",{})
   if a['stratum']=='unassisted':
    valid+=bool(grade.get('valid'));strong+=bool(grade.get('valid') and grade.get('usefulness')=='strong')
 receipt=json.loads((folder/'receipt.json').read_text()) if (folder/'receipt.json').exists() else {}
 rows.append(dict(model=folder.name,status=receipt.get('status'),answers=n,generation_seconds=sec,worker_seconds=receipt.get('elapsed_seconds'),tokens=tokens,aggregate_output_tokens_per_second=tokens/sec if sec else None,valid_target_answers=valid,strong_target_answers=strong,screen_seconds_per_valid_target=sec/valid if valid else None))
(D/'costs.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(rows,indent=2))
