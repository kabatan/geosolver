"""Pre-generation structural checks supplement the given-to-predicate review."""
import json,re
from pathlib import Path
from formalize import HERE,ROOT,RUN,sha,write

def main():
    from transformers import AutoTokenizer
    meta=json.loads((ROOT/'docs/research/geometryzero-stage1-2026-09-30/model.json').read_text())
    tok=AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True)
    jobs=json.loads((RUN/'jobs.json').read_text());lens={}
    for j in jobs:
        prompt=tok.apply_chat_template(j['messages'],tokenize=False,add_generation_prompt=True)
        lens[j['id']]=len(tok.encode(prompt,add_special_tokens=False))
        assert 50<lens[j['id']]<=2048
        s=j['messages'][0]['content'];assert 'answer_exact' not in s and 'UseTheorem' not in s
        if j['arm']=='logic':assert '<auxiliary>' not in s.split('Here is the logic form')[1]
    rows=json.loads((HERE/'formalization-audit.json').read_text());checks=[]
    for row in rows:
        s='\n'.join(f['statement'] for f in row['facts'])
        assert all(f['source_given'] for f in row['facts']) and s.count('Find(')==1
        assert s.count('(')==s.count(')')
        if row['id']=='DA08':assert 'Perpendicular(Line(O,T)' not in s and 'Equals(LengthOf(Line(O,T))' not in s
        if row['id']=='DB08':assert 'Tangent(Line(P,X)' not in s
        if row['id']=='H01':assert 'PointLiesOnCircle(P' not in s
        checks.append(dict(id=row['id'],facts=len(row['facts']),review='Source-given-only manual review; original prose preserves remaining conditions.'))
    report=dict(status='pass',jobs=len(jobs),max_prompt_tokens=max(lens.values()),min_prompt_tokens=min(lens.values()),lens=lens,manual_reviews=checks,source_sha256=sha(HERE/'formalize.py'),audit_source_sha256=sha(__file__),actor_jobs_sha256=sha(RUN/'jobs.json'),limitations=['No automatic semantic theorem equivalence proof; all 24 given-to-predicate mappings manually inspected.','Circle center variables merely name existing given circles.','DSL lacks several specialized conditions; original English retained.'])
    write(HERE/'input-audit.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('lens','manual_reviews')}))

if __name__=='__main__':main()
