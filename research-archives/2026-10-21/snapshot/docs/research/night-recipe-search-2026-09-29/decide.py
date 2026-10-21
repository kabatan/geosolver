"""Join completed blind grades and apply the frozen exploratory gate."""
from pathlib import Path
import json
from score import RUN,read,write,sha
ARMS=['Base','S128','X128','S512','X512','D512','DX512']
def main():
    rows=read(RUN/'scores/current.json');mapping=read(RUN/'review/mapping.researcher-only.json');grades=read(RUN/'review/grades.json')
    grades={g['review_id']:g for g in grades};mapped={}
    for r in mapping:
        g=grades[r['review_id']];assert g['verdict'] in ('valid','invalid','unclear') and g['rationale']
        assert r['file_sha256']==sha(r['file'])
        mapped[(r['arm'],r['id'])]=g
    rr=[r for r in rows if r['kind']=='main' and r['training_seed']==2026093001 and r['replicate']==1 and r['arm'] in ARMS]
    common={arm:{r['id']:r for r in rr if r['arm']==arm} for arm in ARMS}
    expected={r['id'] for r in read(RUN/'jobs/main12.json')}
    for arm in ARMS:
        assert set(common[arm])==expected,('incomplete arm',arm)
        assert all(r['finish_reason']=='stop' for r in common[arm].values()),('censored',arm)
        for ident,r in common[arm].items():
            r['primary_success']=r['observed_success'] and mapped[(arm,ident)]['verdict']=='valid'
            r['lenient_success']=r['observed_success'] and mapped[(arm,ident)].get('lenient_valid',False)
    totals={}
    for arm in ARMS:
        retention=[r for r in rows if r['kind']=='retention' and r['arm']==arm and r['training_seed']==2026093001]
        assert len(retention)==4 and all(r['finish_reason']=='stop' for r in retention)
        totals[arm]=dict(n=12,numeric=sum(r['observed_success'] for r in common[arm].values()),primary=sum(r['primary_success'] for r in common[arm].values()),lenient=sum(r['lenient_success'] for r in common[arm].values()),retention=sum(r['observed_success'] for r in retention))
    gates={};eligible=[]
    for arm,control in [('S128','X128'),('S512','X512'),('D512','DX512')]:
        improves=[r['source_id'] for ident,r in common[arm].items() if r['primary_success'] and not common['Base'][ident]['primary_success']]
        gates[arm]=dict(base_plus_two=totals[arm]['primary']>=totals['Base']['primary']+2,beats_shuffle=totals[arm]['primary']>totals[control]['primary'],two_families=len(set(improves))>=2,numeric_not_lower=totals[arm]['numeric']>=totals['Base']['numeric'],retention_ok=totals[arm]['retention']>=3,improved_families=sorted(set(improves)),control=control)
        if all(gates[arm][k] for k in ['base_plus_two','beats_shuffle','two_families','numeric_not_lower','retention_ok']):eligible.append(arm)
    eligible.sort(key=lambda a:(totals[a]['primary'],totals[a]['primary']-totals[gates[a]['control']]['primary'],totals[a]['numeric'],-int(a[1:] if a.startswith('S') else 512)),reverse=True)
    result=dict(status='complete',summary=totals,gates=gates,eligible_ranked=eligible,branch='A' if eligible else 'B',selected=eligible[0] if eligible else None,note='Exploratory selection rule; no significance claim. Branch execution also requires adequate remaining budget.')
    write(RUN/'decision.json',result);write(RUN/'scores/main-reviewed.json',rr);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
