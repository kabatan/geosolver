"""Run exactly the common-cap extensions required by completed initial output.

First-sample and second-sample subsets are separate calls, ensuring identical
batch composition across the seven-arm and three-arm comparisons respectively.
"""
import argparse,json
from campaign import RUN,read,write,generate,status
ARMS=['Base','S128','X128','S512','X512','D512','DX512']
BOUNDS=[(32768,40960),(81920,98304),(131072,147456)]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--execute',action='store_true');a=ap.parse_args()
    groups=[('main','common',ARMS,read(RUN/'jobs/main12.json')),
            ('main','rep2',ARMS[:3],read(RUN/'jobs/main24.json')[12:]),
            ('retention','all',ARMS,read(RUN/'jobs/retention.json')),
            ('short','all',ARMS,read(RUN/'jobs/short.json'))]
    for kind,name,arms,jobs in groups:
        active=jobs
        for index,(cap,context) in enumerate(BOUNDS):
            hits=set()
            for arm in arms:
                matches=list((RUN/'outputs').glob(f'{arm}-2026093001-{kind}-{cap}*'))
                records={p.name[:-7]:p for d in matches for p in d.glob('*-0.json')}
                for job in active:
                    p=records.get(job['id']);assert p is not None,('missing comparison',arm,kind,cap,job['id'])
                    r=read(p);assert r['messages']==job['messages'] and r['seed']==job['seed']
                    if r['finish_reason']=='length':hits.add(job['id'])
            if not hits:break
            if index==len(BOUNDS)-1:
                write(RUN/f'extensions/censored-{kind}-{name}.json',dict(ids=sorted(hits),cap=cap,arms=arms));break
            nextcap,nextcontext=BOUNDS[index+1];active=[j for j in jobs if j['id'] in hits]
            path=RUN/f'extensions/jobs-{kind}-{name}-{nextcap}.json'
            if path.exists():assert read(path)==active
            else:write(path,active)
            print(json.dumps(dict(kind=kind,group=name,arms=arms,cap=nextcap,ids=[j['id'] for j in active])),flush=True)
            if not a.execute:return
            for arm in arms:generate(arm,kind,path,cap=nextcap,context=nextcontext,suffix='-'+name)
    status(state='initial_cap_checks_complete')
if __name__=='__main__':main()
