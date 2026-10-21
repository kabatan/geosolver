"""Export condition-masked final answers, keeping originals and mapping separate."""
import hashlib
import json
from pathlib import Path
from qwen.common import write_json
HERE=Path(__file__).resolve().parent
ROOT=Path('qwen/.runtime/exp04_exploration')
jobs=json.loads((HERE/'jobs.json').read_text())
keys=sorted([(i,s) for i in range(len(jobs)) for s in range(4)],key=lambda k: hashlib.sha256(f'exploration-review-{k}'.encode()).hexdigest())
ids={key:f'X{index+1:03d}' for index,key in enumerate(keys)}
rows=[]; mapping=[]
for i,job in enumerate(jobs):
    path=ROOT/'generation'/f'group-{i:03d}.json'
    if not path.exists():continue
    for r in json.loads(path.read_text()):
        rid=ids[i,r['sample']]
        raw=r['raw_text']
        final=raw.split('</think>',1)[1].replace('<|im_end|>','').strip() if '</think>' in raw else ''
        rows.append({'review_id':rid,'problem_id':r['id'],'problem':r['source_problem'],
                     'final_text':final,'finish_reason':r['finish_reason'],
                     'completion_tokens':len(r['completion_ids'])})
        mapping.append({'review_id':rid,'group':i,'sample':r['sample'],'condition':r['condition'],
                        'C_auto':r['verdict'],'extracted_answer':r['extracted_answer'],
                        'source':str(path)})
rows.sort(key=lambda r:(r['problem_id'],r['review_id']))
write_json(HERE/'review-blinded.json',rows)
write_json(ROOT/'review-mapping.json',mapping)
for pid in dict.fromkeys(r['problem_id'] for r in rows):
    subset=[r for r in rows if r['problem_id']==pid]
    text=f'# {pid} — condition-masked submitted solutions\n\n{subset[0]["problem"]}\n\n'
    for r in subset:
        text+=f'## {r["review_id"]}\n\nFinish: {r["finish_reason"]}; tokens: {r["completion_tokens"]}\n\n{r["final_text"] or "[No final solution]"}\n\n'
    (HERE/f'answers-{pid}.md').write_text(text)
print(json.dumps({'answers':len(rows),'by_problem':{p:sum(r['problem_id']==p for r in rows) for p in dict.fromkeys(r['problem_id'] for r in rows)}},ensure_ascii=False))
