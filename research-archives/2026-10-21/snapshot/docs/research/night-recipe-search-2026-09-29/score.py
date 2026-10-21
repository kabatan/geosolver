"""Score preserved outputs, build condition-hidden review packets, audit gates.

Does not generate output or change training. Final cap choices are shared by
job across compared arms; missing shared-cap output is explicitly incomplete.
"""
import argparse,collections,datetime,hashlib,importlib.util,json,math,random,statistics,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];RUN=ROOT/'qwen/.runtime/night_recipe_search_20260929'
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('previous_numeric_scorer',ROOT/'docs/research/related-numeric-sft-2026-09-28/analyze.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix('.tmp');temp.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n');temp.replace(p)
def score():
    keys={r['id']:r for p in (RUN/'keys').glob('*.json') for r in read(p)}
    rows=[]
    for directory in sorted((RUN/'outputs').glob('*')):
        if not (directory/'receipt.json').exists():continue
        receipt=read(directory/'receipt.json');arm,seed,kind,*_=directory.name.split('-')
        for path in sorted(directory.glob('*-0.json')):
            r=read(path);key=keys[r['id']];parsed,method,excerpt=module.parse(r['raw_text']);want=float(module.parse_numeric(key['answer_exact']));value=None;error=None;correct=False
            if parsed is not None:
                try:
                    value=float(module.parse_numeric(parsed))
                    if math.isfinite(value):error=abs(value-want);correct=error<=max(1e-4,1e-5*abs(want))
                    else:value=None
                except (ValueError,TypeError,OverflowError,ZeroDivisionError):pass
            rows.append(dict(arm=arm,training_seed=int(seed),kind=kind,id=r['id'],source_id=r['source_id'],split=r.get('split'),replicate=r.get('replicate',1),file=str(path),file_sha256=sha(path),cap=receipt['cap'],finish_reason=r['finish_reason'],tokens=len(r['completion_ids']),value=value,expected=key['answer_exact'],numeric_correct=correct,observed_success=correct and r['finish_reason']=='stop',absolute_error=error,relative_error=error/max(abs(want),1e-30) if error is not None else None,parse_method=method,answer_excerpt=excerpt[-500:]))
    # Select only a common cap. A later extension of any compared arm raises the
    # required cap of that job across the comparison (conservatively all seeds).
    maxcaps={}
    for r in rows:
        key=(r['kind'],r['id']);maxcaps[key]=max(maxcaps.get(key,0),r['cap'])
    final=[r for r in rows if r['cap']==maxcaps[(r['kind'],r['id'])]]
    assert len({(r['arm'],r['training_seed'],r['kind'],r['id']) for r in final})==len(final),'Ambiguous same-cap output; explicitly resolve attempts'
    summary={}
    for r in final:
        group=f"{r['arm']}:{r['training_seed']}:{r['kind']}"+((':'+r['split']) if r['split'] else '')
        summary.setdefault(group,[]).append(r)
    totals={}
    for group,rr in summary.items():
        errs=[r['relative_error'] for r in rr if r['relative_error'] is not None]
        totals[group]=dict(n=len(rr),numeric_success=sum(r['observed_success'] for r in rr),length=sum(r['finish_reason']=='length' for r in rr),unparsed=sum(r['value'] is None for r in rr),median_relative_error=statistics.median(errs) if errs else None,total_tokens=sum(r['tokens'] for r in rr))
    write(RUN/'scores/all-stages.json',rows);write(RUN/'scores/current.json',final);write(RUN/'scores/summary.json',totals)
    print(json.dumps(totals,indent=2));return final
def blind(rows,review_name='review',kind='main',arms=None):
    cases=[r for r in rows if r['observed_success'] and r['kind']==kind and (not arms or r['arm'] in arms)]
    random.Random(2026093501).shuffle(cases)
    packets=[];mapping=[];duplicates={}
    for r in cases:
        output=read(r['file']);content=output['final_text'];h=hashlib.sha256(json.dumps([output['messages'],content],ensure_ascii=False).encode()).hexdigest()
        if h not in duplicates:
            ident=f'case-{len(packets)+1:03d}';duplicates[h]=ident
            packets.append(dict(review_id=ident,source_id=r['source_id'],messages=output['messages'],answer_expected=r['expected'],final_text=content,content_sha256=h))
        mapping.append(dict(review_id=duplicates[h],**r))
    assert '/' not in review_name and review_name not in ('.','..')
    out=RUN/review_name;out.mkdir(exist_ok=True)
    packetpath=out/'blind-packets.json';mappath=out/'mapping.researcher-only.json'
    # Once created, IDs are stable. Subsequent branch reviews get separate packs.
    if packetpath.exists():
        assert read(packetpath)==packets,'Use a separate review packet for new phase'
    else:
        write(packetpath,packets);write(mappath,mapping)
        write(out/'receipt.json',dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),packet_sha256=sha(packetpath),mapping_sha256=sha(mappath),rubric_sha256=sha(HERE/'REVIEW.md'),protocol_sha256=sha(HERE/'PROTOCOL.md'),scorer_sha256=sha(__file__),kind=kind,arms=arms,reviewer='Executing assistant; condition-hidden packet, not an independent human reviewer'))
    for packet in packets:
        p=out/(packet['review_id']+'.md')
        content='# '+packet['review_id']+' / '+packet['source_id']+'\n\n'+packet['messages'][0]['content']+'\n\nExpected numeric answer: '+packet['answer_expected']+'\n\n## Model output\n\n'+packet['final_text']+'\n'
        if p.exists():assert p.read_text()==content
        else:p.write_text(content)
    print(json.dumps(dict(blind_cases=len(packets),numeric_correct_outputs=len(cases))))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--blind',action='store_true');ap.add_argument('--review-name',default='review');ap.add_argument('--kind',default='main');ap.add_argument('--arms',nargs='+');a=ap.parse_args();rows=score()
    if a.blind:blind(rows,a.review_name,a.kind,a.arms)
if __name__=='__main__':main()
