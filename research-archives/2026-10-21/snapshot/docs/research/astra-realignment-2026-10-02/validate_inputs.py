import json,sys
import sympy as s
from transformers import AutoTokenizer
from prepare_diagnostic import HERE,ROOT,RUN,load,sha,write
def main():
    frozen=load(HERE/'freeze.json');jobs=load(RUN/'jobs.json');keys=load(RUN/'keys.researcher-only.json')
    assert frozen['jobs_sha256']==sha(RUN/'jobs.json') and frozen['keys_sha256']==sha(RUN/'keys.researcher-only.json')
    assert frozen['protocol_sha256']==sha(HERE/'PROTOCOL.md')
    assert frozen['prepare_sha256']==sha(HERE/'prepare_diagnostic.py')
    for p,h in frozen['sources'].items():assert sha(p)==h
    meta=load(ROOT/'docs/research/geometryzero-stage1-2026-09-30/model.json')
    tok=AutoTokenizer.from_pretrained(meta['snapshot'],local_files_only=True);lens={}
    for j in jobs:
        assert j['group']=='main' and not set(j)&{'answer','answer_exact','target','reference'}
        t=j['messages'][0]['content'];assert 'Tangent(Line(P,X)' not in t and 'UseTheorem' not in t
        ids=tok.encode(tok.apply_chat_template(j['messages'],tokenize=False,add_generation_prompt=True),add_special_tokens=False)
        lens[j['id']]=len(ids);assert len(ids)<=2048
    checks=[]
    for c in keys:
        if c['problem_id']!='DB08':continue
        w=c['witness'];p={k:s.Matrix([s.sympify(v) for v in xy]) for k,xy in w['points'].items()}
        length=lambda a,b:s.sqrt(s.factor((p[a]-p[b]).dot(p[a]-p[b])))
        assert s.simplify(length('P','X')-s.sympify(c['answer_exact']))==0
        assert s.simplify(length('P','Y')-s.sympify(c['givens']['PY']))==0
        assert s.simplify(length('Y','Z')-s.sympify(c['givens']['YZ']))==0
        py,yz=(s.sympify(c['givens'][name]) for name in ['PY','YZ']);want=s.sympify(c['answer_exact'])
        true_res=s.simplify(py*(py+yz)-want**2);assert true_res==0
        wrongs={name:dict(value=str(s.N(value,18)),relative_error=float(abs(value-want)/want),accepted_2pct=bool(abs(float((value-want)/want))<=.02)) for name,value in [('PZ/2',(py+yz)/2),('2PY',2*py)]}
        assert all(not r['accepted_2pct'] for r in wrongs.values())
        checks.append(dict(case_id=c['case_id'],target=str(want),true_rule_squared_residual=str(true_res),wrong_rules=wrongs,given_ratio_YZ_PY=float(yz/py),independent_prior_error=w['independent_absolute_error']))
    write(HERE/'input-audit.json',dict(status='pass',prompt_tokens=lens,max_prompt_tokens=max(lens.values()),jobs_sha256=sha(RUN/'jobs.json'),cpu_rule_diagnostic=checks,limitations=['Given-to-predicate numerical substitutions checked; no formal equivalence proof.','DB08 exact radical arithmetic is harder than the original integer givens.','New claims are researcher-side diagnosis only, never actor/reward input.']))
    print(json.dumps(dict(status='pass',max_prompt_tokens=max(lens.values()),cpu_rule_diagnostic=checks)))
if __name__=='__main__':main()
