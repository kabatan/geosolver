"""Apply the frozen min/max token rule only after the complete screen."""
import json,sys,time
from pathlib import Path
from signal_analysis import analyze,sha,write

def main():
    run=Path(sys.argv[1]).resolve()
    jobs=json.loads((run/'jobs.json').read_text())
    for name in ('freeze.json','implementation-freeze.json'):
        for p,h in json.loads((run/name).read_text())['sha256'].items():
            if p.endswith('/test_probe.py'):
                validation=json.loads((run/'cpu-validation.json').read_text())
                if sha(p)!=h and sha(p)!=validation['test_source_sha256']:
                    raise ValueError('test revision unrecorded')
            elif sha(p)!=h:raise ValueError('frozen source changed: '+p)
    s,rows,extensions=analyze(run)
    if len(s)!=len(jobs):raise ValueError('screen incomplete')
    for directory in ['screen16384']+(['screen32768'] if extensions else []):
        if json.loads((run/directory/'receipt.json').read_text())['status']!='complete':
            raise ValueError('unfinished generation process')
    for id in extensions:
        if not (run/'screen32768'/(id+'.json')).exists():raise ValueError('missing extension')
    for j in jobs:
        rs=[r for r in rows if r['id']==j['id']]
        assert len(rs)==4 and sorted(r['sample'] for r in rs)==list(range(4))
        assert all(r['messages']==j['messages'] and r['seed']==j['seed'] for r in rs)
        assert all(r['policy_adapter_sha256'] is None and len(r['completion_ids'])==len(r['rollout_logps']) for r in rs)
    mixed=sorted((g for g in s if g['eligible'] and g['mixed']),key=lambda g:(g['total_tokens'],g['id']))
    chosen=[('short',mixed[0]),('long',mixed[-1])] if mixed else []
    if len(chosen)==2 and chosen[0][1]['id']==chosen[1][1]['id']:chosen=chosen[:1]
    selections=[]
    for label,g in chosen:
        path=run/('rows-'+label+'.json')
        if path.exists():raise ValueError('selection already saved')
        rr=[r for r in rows if r['id']==g['id']];write(path,rr)
        selections.append(dict(label=label,group=g,rows=str(path),rows_sha256=sha(path)))
    write(run/'selection.json',dict(unix=time.time(),rule='min/max total completion tokens among final naturally completed mixed groups; independent base updates',screen_sha256=sha(run/'screen-scores.json'),summary_sha256=sha(run/'signal-summary.json'),extensions=extensions,selections=selections))
    print(json.dumps(selections,indent=2))
if __name__=='__main__':main()
