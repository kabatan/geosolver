"""Summarize manually audited answers, recording parser agreement separately."""
import json,hashlib
from pathlib import Path
from collections import defaultdict
from qwen.answer_check import extract_answer,answers_equal
D=Path(__file__).resolve().parent
R=Path('qwen/.runtime/model_fit_20260923_attempt04')
g=json.loads((D/'grades.json').read_text())
adjudications=json.loads((D/'adjudications.json').read_text()) if (D/'adjudications.json').exists() else {}
sums=defaultdict(lambda:{'n':0,'graded':0,'valid':0,'valid_including_local_errors':0,'numeric_correct':0,'strong':0,'truncated':0,'tokens':0})
records=[]
for model in ['original_4b','thinking_2507']:
 for p in sorted((R/model).glob('group-*.json')):
  for x in json.loads(p.read_text()):
   key=f"{model}:{x['id']}:{x['sample']}";a=g.get(key)
   if a and key in adjudications:
    a={**a,**{k:v for k,v in adjudications[key].items() if k in ['valid','numeric_correct','usefulness']},'adjudication':adjudications[key]}
   c=sums[model+':'+x['stratum']];c['n']+=1;c['tokens']+=x['tokens'];c['truncated']+=x['finish_reason']!='stop'
   row={k:x[k] for k in ['id','model','sample','stratum','problem','reference','final_text','tokens','finish_reason','training_eligible']}
   row['grade']=a;row['source']=str(p);row['source_sha256']=hashlib.sha256(p.read_bytes()).hexdigest()
   if a:
    c['graded']+=1;c['valid']+=bool(a['valid']);c['valid_including_local_errors']+=bool(a['valid'] or a.get('local_error_sensitivity'));c['strong']+=bool(a['valid'] and a['usefulness']=='strong')
    if x['stratum']!='foundation':
     value=extract_answer(x['raw_text']);verdict=answers_equal(value,x['reference']) is True
     row['numeric_parser']={'extracted':value,'correct':verdict,'manual_agrees':verdict==a['numeric_correct']};c['numeric_correct']+=a['numeric_correct']
   records.append(row)
for k,v in sums.items():
 if k.endswith(':foundation'):v['numeric_correct']=None
receipt=json.loads((R/'receipt.json').read_text())
failed=[]
for sub in ['model_fit_20260923','model_fit_20260923_attempt02','model_fit_20260923_attempt03']:
 f=Path('qwen/.runtime')/sub/'receipt.json'
 if f.exists():failed.append({'source':str(f),**json.loads(f.read_text())})
summary={'results':dict(sums),'answer_count':len(records),'graded_count':sum(r['grade'] is not None for r in records),'updates':0,'receipt':receipt,'setup_failures':failed,'worker_wall_seconds_including_failed_setup':receipt.get('elapsed_seconds',0)+sum(x['elapsed_seconds'] for x in failed),'limitations':['two samples per item; selected diagnostic configurations','hint-assisted outputs are not self-discovered solutions','single reviewer, model identity visible','basic subskills do not certify general geometry competence','32K budget lower than official 2507 competition benchmark']}
(D/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(D/'graded-results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k in ['results','answer_count','graded_count','updates']},ensure_ascii=False,indent=2))
