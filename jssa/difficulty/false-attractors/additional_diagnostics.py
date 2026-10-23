"""Descriptive audits specified as exploratory; never overwrite primary labels."""
from pathlib import Path
from collections import Counter,defaultdict
import csv,gzip,json,math
HERE=Path(__file__).resolve().parent

def main():
    summaries=[json.loads(p.read_text()) for p in sorted((HERE/'classified').glob('*.json'))]
    primary_tie=['e','c','d','a','b','unknown']
    cause=lambda c:next(k for k in primary_tie if c.get(k,0)==max(c.values())) if c else 'no_failure'
    source_rows=[];source_main=defaultdict(Counter);alt=defaultdict(Counter);exclusive=Counter();native=defaultdict(Counter)
    for s in summaries:
        for source,st in s['source_stats'].items():
            ct=s['variants']['primary'].get(source,{})
            votes={k:ct.get('vote_'+k,0) for k in primary_tie} if ct.get('failed_records',0) else {}
            main=cause(votes);source_main[source][main]+=1
            source_rows.append({'id':s['id'],'source_arm':source,'records':st['records'],'failures':st.get('failed_records',0),
                'finite_failed':ct.get('finite_failed',0),'ab':ct.get('ab',0),'main_cause':main,
                **{k:ct.get(k,0) for k in ('a','b','c','d','e')},'unknown':ct.get('vote_unknown',0)})
    for p in sorted((HERE/'classified').glob('*.jsonl.gz')):
        for r in map(json.loads,gzip.decompress(p.read_bytes()).splitlines()):
            key=r['source']+'/'+r['arm']
            if 'native_joint' in r:
                native[key]['failed_with_saved_native']+=1
                native[key]['with_joint']+=r['native_joint']>0
                native[key]['joint_and_c']+=r['native_joint']>0 and bool(r.get('c'))
                native[key]['joint_and_ab']+=r['native_joint']>0 and bool(r.get('ab'))
            if r['source']!='raw0':continue
            vote=next((k for k in ('c','b','a','d','e') if r.get(k)),'unknown')
            alt[r['id']][vote]+=1
            if r.get('ab') and not r.get('c'):exclusive['ab_without_c']+=1
            if r.get('ab') and r.get('c'):exclusive['ab_and_c']+=1
    alt_causes=Counter(cause(alt[s['id']]) for s in summaries)
    with (HERE/'per-problem-by-source.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(source_rows[0]));w.writeheader();w.writerows(source_rows)
    result={'exploratory':True,'source_main_causes':{k:dict(v) for k,v in source_main.items()},
       'alternative_priority':'c>b>a>d>e; fixed original tie rule','alternative_main_causes':dict(alt_causes),
       'alternative_main_ab':alt_causes['a']+alt_causes['b'],'exclusive':dict(exclusive),
       'native_joint_evidence':{k:dict(v) for k,v in native.items()},
       'note':'Overlap and priority checks are descriptive and do not replace preregistered stop criterion.'}
    (HERE/'additional-diagnostics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
