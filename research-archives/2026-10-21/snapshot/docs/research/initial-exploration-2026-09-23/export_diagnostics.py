"""Readable adaptive diagnostic outputs; separate from primary inference pilot."""
import json
from pathlib import Path
from qwen.common import write_json, file_hash
HERE=Path(__file__).resolve().parent
ROOT=Path('qwen/.runtime/exp04_exploration')
rows=[]; mapping=[]
for stage,prefix in [('clarification','R'),('meaningful','M')]:
    for i,p in enumerate(sorted((ROOT/('diagnostic-'+stage)/'generation').glob('group-*.json'))):
        for r in json.loads(p.read_text()):
            raw=r['raw_text'];final=raw.split('</think>',1)[1].replace('<|im_end|>','').strip() if '</think>' in raw else ''
            rid=f'{prefix}{i:02d}{r["sample"]}'
            rows.append({'review_id':rid,'stage':stage,'id':r['id'],'condition':r['condition'],'problem':r['source_problem'],'final_text':final,'finish_reason':r['finish_reason'],'tokens':len(r['completion_ids']),'source':str(p),'source_sha256':file_hash(p)})
            mapping.append({'review_id':rid,'C_auto':r['verdict'],'extracted_answer':r['extracted_answer']})
write_json(HERE/'diagnostic-responses.json',rows)
write_json(ROOT/'diagnostic-review-mapping.json',mapping)
for stage in dict.fromkeys(r['stage'] for r in rows):
    text=f'# Adaptive diagnostic: {stage}\n\nExploratory, not primary comparison; no model updates.\n\n'
    for r in rows:
        if r['stage']!=stage:continue
        text+=f'## {r["review_id"]} / {r["id"]} / {r["condition"]}\n\n{r["problem"]}\n\nFinish: {r["finish_reason"]}; tokens: {r["tokens"]}\n\n{r["final_text"] or "[No final solution]"}\n\n'
    (HERE/f'diagnostic-{stage}-answers.md').write_text(text)
print(json.dumps({'answers':len(rows),'stages':{s:sum(r['stage']==s for r in rows) for s in dict.fromkeys(r['stage'] for r in rows)}}))
