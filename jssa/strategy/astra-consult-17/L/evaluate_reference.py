"""Post-experiment grader only. Official answers never feed back into the worker."""
from pathlib import Path
import json,sys,re
import sympy as sp
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(ROOT/'jssa/difficulty'))
from probe_basins import _ascii_expr

def main():
 refs={c['id']:c['answer'] for c in (json.loads(l) for l in (ROOT/'benchmarks/cases.jsonl').read_text().splitlines())}
 rows=[]
 for f in sorted((HERE/'runs').glob('*/result.json')):
  r=json.loads(f.read_text())
  if r['status']!='certified':continue
  if r['arm']=='C3':Q=sp.sympify(r['eliminant']);root=r['root_check']
  else:Q=sp.sympify(r['Q']);root=next(a['root_check'] for a in reversed(r['attempts']) if a['candidate_status']=='certified')
  t=sp.Symbol(r['target_symbol']);lo,hi=map(sp.sympify,root['range'][:2]);lop,hip=root['range'][2:]
  answer=refs[r['id']];items=answer if isinstance(answer,list) else [answer]
  values=[]
  for a in items:
   for q in str(a).split(','):values.append(sp.sympify(_ascii_expr(q),rational=True))
  exact=[]
  for v in values:
   exact.append(bool(sp.simplify(Q.subs(t,v))==0 and (v>lo if lop else v>=lo) and (v<hi if hip else v<=hi)))
  match=len(values)==1 and exact[0]
  rows.append({'trial':f.parent.name,'reference_count':len(values),'exact_reference_root_and_range':exact,'unique_answer_matches':match})
  assert match,(f,values,root)
 result={'only_posthoc_grader_loads_official_answer':True,'certified_trials':len(rows),'matched':sum(r['unique_answer_matches'] for r in rows),'rows':rows}
 (HERE/'reference-evaluation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
if __name__=='__main__':main()
