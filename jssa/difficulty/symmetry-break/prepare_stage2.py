"""Immutable receipt, complete slot ledger, lowering audit and common starts."""
from __future__ import annotations
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from collections import Counter
import numpy as np
from stage2_common import *


def main():
    from geosolver.runtime.integrity import installed_dependencies
    from geosolver.engine.standard.problem.infer_problem_bounds import infer_problem_bounds
    assert not (OUT / 'execution/receipt.json').exists(), 'Do not repeat setup silently'
    source_hash = assert_identity()
    assert subprocess.check_output(['git', '-C', str(CLEAN), 'rev-parse', 'HEAD'], text=True).strip() == FROZEN
    assert not subprocess.check_output(['git', '-C', str(CLEAN), 'status', '--porcelain'], text=True).strip()
    for name, expected in json.loads((OUT / 'prediction.lock.json').read_text())['files'].items():
        blob = subprocess.check_output(['git', '-C', str(OUT), 'show', f'{PREDICTION_COMMIT}:jssa/difficulty/symmetry-break/{name}'])
        assert hashlib.sha256(blob).hexdigest() == expected
    RAW.mkdir(exist_ok=False)
    for name in ('tmp', 'prepared', 'local', 'full', 'jacobian', 'logs'):
        (RAW / name).mkdir()
    selection = json.loads((OUT / 'selection.json').read_text())
    receipt = dict(task='Q41', started_utc=utc(), frozen_commit=FROZEN, source_hash=source_hash,
                   clean_checkout=str(CLEAN), python=sys.version, executable=sys.executable,
                   dependencies=installed_dependencies(), platform=platform.platform(),
                   cpu=Path('/proc/cpuinfo').read_text().split('model name')[1].split('\n')[0].strip(': \t'),
                   cpu_count=os.cpu_count(), affinity=sorted(os.sched_getaffinity(0)),
                   load=os.getloadavg(), maximum_parallel=2, maximum_command_seconds=210,
                   authorization={'prediction_commit': PREDICTION_COMMIT, 'push_confirmed_utc':'2026-10-23T17:43:24Z',
                                  'basis':'User confirms Claude commit/push and explicitly authorizes Q41 stage 2 and this resumption.'},
                   interruption={'prior_stage2':'Interrupted before first tool call or implementation',
                                 'active_q41_processes_at_resumption':0, 'previous_trials':0,
                                 'lost_trials':0, 'retries':0},
                   prediction_lock_sha256=digest(OUT/'prediction.lock.json'), raw_directory=str(RAW))
    save(OUT/'execution/receipt.json', receipt)
    # Enumerate all 56,000 local and 840 full slots BEFORE inspecting feasibility.
    with (RAW/'slots.jsonl').open('x') as f:
        for item in selection:
            cid=item['id']
            for k in range(200):
                for arm in sorted(ARMS, key=lambda a: order(cid, 410241, a, k)):
                    f.write(json.dumps(dict(kind='local',id=cid,arm=arm,k=k,seed=410241,stage1=item['arms'][arm]['status']))+'\n')
            for seed in SEEDS:
                for arm in sorted(ARMS, key=lambda a: order(cid, seed, a)):
                    f.write(json.dumps(dict(kind='full',id=cid,arm=arm,seed=seed,stage1=item['arms'][arm]['status']))+'\n')
    save(OUT/'execution/slots.json',dict(file=str(RAW/'slots.jsonl'),sha256=digest(RAW/'slots.jsonl'),local=56000,full=840))
    audit=[]
    for i,item in enumerate(selection):
        cid=item['id']; loaded={}; info={'id':cid,'i':i,'family':item['family'],'arms':{}}
        for arm in ARMS:
            src=item['arms'][arm]
            if src['status']!='syntax_checked':
                info['arms'][arm]={'status':'not_generated','reason':src['reason']};continue
            try:
                problem,b,e,j=load_case(cid,arm)
                loaded[arm]=(problem,b,e,j)
                info['arms'][arm]=dict(status='ready',variables=b.var_names,
                    raw_equations=list(zip(j.bundle.spec.constraints,j.bundle.targets)),
                    lowered_equations=list(zip(b.spec.constraints,b.targets)),
                    guards=b.spec.guards,
                    n=len(b.var_names),m_raw=len(j.bundle.targets),m_search=len(b.targets),
                    method='Powell' if len(b.var_names)>len(b.targets) else 'LM',
                    input_sha256=digest(OUT/src['file']))
            except Exception as err:
                info['arms'][arm]={'status':'invalid','reason':f'{type(err).__name__}: {err}'}
        if 'original' in loaded:
            ob=loaded['original'][1]
            bounds=infer_problem_bounds(ob)
            if len(bounds)!=len(ob.var_names) or not all(np.isfinite([a,b]).all() and b>a for a,b in bounds):
                for a in loaded: info['arms'][a].update(status='invalid',reason='invalid_common_bounds')
            else:
                info['bounds']=bounds
                info['starts']=[np.random.default_rng([410241,i,k]).uniform(np.array(bounds)[:,0],np.array(bounds)[:,1]).tolist() for k in range(200)]
                for arm,(_,b,_,_) in loaded.items():
                    if b.var_names!=ob.var_names or len(b.targets)!=len(ob.targets):
                        info['arms'][arm].update(status='invalid',reason='lowering_correspondence_failed')
                        continue
                    # Source row positions retain identity; only the registered
                    # condition row can change for E/W; M changes constructions.
                    changed=[q for q,(x,y) in enumerate(zip(info['arms']['original']['lowered_equations'],info['arms'][arm]['lowered_equations'])) if x!=y]
                    allowed=set()
                    for change in item['arms'][arm].get('changes',[]):
                        if change['path'][0]=='conditions':
                            cond_index=change['path'][1]
                            allowed.add(sum(c.get('operator')=='=' for c in json.loads((OUT/'dsl'/cid/'original.json').read_text())['conditions'][:cond_index]))
                    if not set(changed)<=allowed:
                        info['arms'][arm].update(status='invalid',reason='unmapped_lowered_rows',changed_rows=changed)
                    else:
                        info['arms'][arm]['row_map']=list(range(len(b.targets)))
        else:
            for arm in loaded: info['arms'][arm].update(status='invalid',reason='original_cannot_define_common_starts')
        save(RAW/'prepared'/f'{cid}.json',info)
        audit.append({k:v for k,v in info.items() if k not in ('starts',)})
        print(cid,Counter(x['status'] for x in info['arms'].values()),flush=True)
    save(OUT/'execution/lowering-audit.json',audit)
    save(OUT/'execution/prepared-manifest.json',{p.name:digest(p) for p in sorted((RAW/'prepared').glob('*.json'))})


if __name__=='__main__':main()
