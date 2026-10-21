"""Small post-hoc strategy diagnostic, after the fixed primary run finishes."""
import json
from pathlib import Path
import random
import time

from run_remaining import OUT,SHARED,HERE,read,write,digest,generate


def prepare():
    prompt=read(OUT/'proof-jobs.json')[0]['messages'][0]['content']
    addition=('Use an analytic proof: choose coordinates or vectors, derive the defining '
              'equations for D, E, and F from the premises, and verify a circle equation '
              'or a concyclicity determinant. Carry out the algebra rather than citing '
              'a configuration-specific theorem. Do not use numerical examples.')
    jobs=[{'id':f'AP01-coordinate-{i:02d}','source_id':'AP01','seed':2026092850+i,
           'messages':[{'role':'user','content':prompt+'\n\n'+addition}],
           'split':'coordinate_diagnostic'} for i in range(2)]
    target=OUT/'coordinate-jobs.json';assert not target.exists();write(target,jobs)
    write(OUT/'coordinate-freeze.json',{'frozen_unix':time.time(),'sha256':{str(p):digest(p) for p in
          [target,Path(__file__),HERE/'AMENDMENT-COORDINATE-DIAGNOSTIC.md']}})


def main():
    prepare()
    deadline=time.monotonic()+7200
    while not (OUT/'completion.json').exists():
        if time.monotonic()>deadline:raise RuntimeError('primary run not complete; inspect')
        time.sleep(5)
    # Main completion is after all GPU guards have returned, not just the last model receipt.
    jobs_path=OUT/'coordinate-jobs.json';jobs=read(jobs_path)
    for arm in ['base','sft']:generate(arm,'coordinate',jobs_path)
    selected=[j for j in jobs if any(read(OUT/f'{arm}-coordinate'/f"{j['id']}-0.json")['finish_reason']=='length'
                                   for arm in ['base','sft'])]
    extension=OUT/'coordinate-extension-jobs.json'
    if selected:
        write(extension,selected)
        for arm in ['base','sft']:generate(arm,'coordinate',extension,extended=True)
    folder=OUT/'coordinate-review';folder.mkdir(exist_ok=False)
    entries=[(arm,j) for arm in ['base','sft'] for j in jobs];random.Random(2026092898).shuffle(entries)
    index=[];private={}
    for idx,(arm,job) in enumerate(entries):
        extended=any(j['id']==job['id'] for j in selected)
        source=OUT/(f'{arm}-coordinate'+('-81k' if extended else ''))/f"{job['id']}-0.json"
        r=read(source);cid=f'coordinate-{idx:02d}'
        row={'case_id':cid,'messages':r['messages'],'raw_text':r['raw_text'],'final_text':r['final_text'],
             'finish_reason':r['finish_reason'],'tokens':len(r['completion_ids'])}
        path=folder/f'{cid}.json';write(path,row)
        index.append({'case_id':cid,'file':str(path),'tokens':row['tokens'],'sha256':digest(path)})
        private[cid]={'arm':arm,'job_id':job['id'],'source':str(source),'source_sha256':digest(source),
                      'cap':81920 if extended else 32768}
    write(folder/'index.json',index);write(OUT/'coordinate-private-key.json',private)
    write(OUT/'coordinate-completion.json',{'status':'generated_and_blinded','end_unix':time.time(),'outputs':4})


if __name__=='__main__':main()
