import hashlib,json,math,statistics,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(ROOT))
from qwen.answer_check import extract_answer,parse_numeric
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n');tmp.replace(p)
def score(raw,key):
    if raw['finish_reason']!='stop':return dict(reward=None,parsed=None,value=None,status='censored',relative_error=None)
    parsed=extract_answer(raw['raw_text']);value=None;error=None
    if parsed is not None:
        try:value=float(parse_numeric(parsed))
        except (ValueError,OverflowError,TypeError):pass
    want=float(parse_numeric(key['answer']))
    if value is not None and math.isfinite(value):error=abs(value-want)
    return dict(reward=int(error is not None and error<=max(1e-4,1e-5*abs(want))),parsed=parsed,value=value,status='parsed' if error is not None else 'unparsed',relative_error=error/max(abs(want),1e-30) if error is not None else None)
def group(rows):
    if any(r['reward'] is None for r in rows):return dict(eligible=False,mixed=None,advantages=None)
    mean=sum(r['reward'] for r in rows)/len(rows)
    return dict(eligible=True,mixed=0<mean<1,advantages=[r['reward']-mean for r in rows])
def analyze(run):
    jobs=json.loads((run/'jobs.json').read_text());keys=json.loads((run/'keys.researcher-only.json').read_text());summary=[];allrows=[];extensions=[]
    for j in jobs:
        p=run/'screen16384'/(j['id']+'.json')
        if not p.exists():continue
        r16=json.loads(p.read_text())
        if any(r['finish_reason']!='stop' for r in r16):extensions.append(j['id'])
        p32=run/'screen32768'/(j['id']+'.json')
        if p32.exists():p=p32
        raw=json.loads(p.read_text());rr=[dict(r,**score(r,keys[j['id']]),raw_file=str(p),raw_file_sha256=sha(p)) for r in raw]
        g=group(rr)
        for i,r in enumerate(rr):r['advantage']=g['advantages'][i] if g['eligible'] else None
        allrows.extend(rr);summary.append(dict(id=j['id'],source_id=j['source_id'],stratum=j['stratum'],cap=rr[0]['cap'],rewards=[r['reward'] for r in rr],statuses=[r['status'] for r in rr],tokens=[len(r['completion_ids']) for r in rr],total_tokens=sum(len(r['completion_ids']) for r in rr),seconds=rr[0]['generation_seconds_group'],eligible=g['eligible'],mixed=g['mixed']))
    write(run/'screen-scores.json',allrows);write(run/'signal-summary.json',dict(groups=summary,extension_ids=extensions,completed_groups=len(summary),mixed_groups=sum(g['mixed'] is True for g in summary),censored_groups=sum(not g['eligible'] for g in summary)))
    return summary,allrows,extensions
if __name__=='__main__':
    run=Path(sys.argv[1]);s,r,e=analyze(run);print(json.dumps(dict(groups=s,extension_ids=e),indent=2))
