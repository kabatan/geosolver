"""Materialize a post-exploration 180-second check and score it unchanged."""
from __future__ import annotations
import argparse
from common import *
from analyze import expected_keys, extract

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare','analyze'))
    args=parser.parse_args()
    selection=read(BASE/'selection.json');cases={r['id']:r for r in selection['cases']}
    if args.mode=='prepare':
        assert (BASE/'completed-jobs.json').exists()
        assert not (BASE/'followup-jobs.json').exists()
        design=read(BASE/'followup-design.json');jobs=[]
        for item in design['comparisons']:
            case=cases[item['id']]
            for arm in item['arms']:
                variant=case['variants'][arm]
                assert not variant.get('alias')
                for seed in design['seeds']:
                    key=f'{case["id"]}__{arm}__s{seed}__t180'
                    jobs.append({'key':key,'id':case['id'],'pool':case['pool'],'stratum':case['stratum'],
                                 'arm':arm,'seed':seed,'limit':180,'input':variant['path'],
                                 'input_hash':variant['sha256']})
        assert len({j['key'] for j in jobs})==len(jobs)
        jobs.sort(key=lambda j:rank(j['key'],'followup_execution_order'))
        save(BASE/'followup-jobs.json',{'jobs':jobs,'design_hash':sha(design)})
        print(canonical({'jobs':len(jobs),'worst_wall_hours':len(jobs)*205/3/3600}))
    else:
        assert (BASE/'completed-followup-jobs.json').exists()
        jobs=read(BASE/'followup-jobs.json')['jobs'];expected=expected_keys(selection);rows=[]
        for job in jobs:
            raw=read(EXTERNAL/'runs'/f'{job["key"]}.json');assert raw['job']==job
            rows.append(extract(raw,cases[job['id']],expected[job['id']]))
        save(EXTERNAL/'followup-cache.json',{r['key']:r for r in rows})
        small=[{k:v for k,v in r.items() if k!='projected_coordinates'} for r in rows]
        save(BASE/'followup-per-run.json',small)
        for r in rows:
            print(canonical({k:r[k] for k in ('id','arm','seed','matched','status','wall_seconds','cpu_seconds','diagram_count')}))

if __name__=='__main__':main()
