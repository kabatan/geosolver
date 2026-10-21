"""Freeze this campaign's datasets and jobs before any model generation."""
from pathlib import Path
import collections,copy,hashlib,json,math,random,runpy
from independent_geometry import check
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
RUN=ROOT/'qwen/.runtime/night_recipe_search_20260929'
OLD=ROOT/'docs/research/program-self-training-2026-09-26'
FAMILIES=['H01','H04','H07','H13','H15','DA01','DA05']
N=runpy.run_path(str(OLD/'numeric_cases.py'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,obj):
    p=RUN/name;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
    return p
def row_from(w):
    return dict(id=w['case_id'],source_id=w['source_id'],kind='numeric',messages=[dict(role='user',content=
        'Solve the following numerical geometry problem. Give only the requested numerical value, with at least 10 significant digits when appropriate. Do not give a proof or explanation.\n\n'+
        N['NUMERIC_EN'][w['source_id']].format(**{k:format(v,'.17g') for k,v in w['givens'].items()}))],target=format(w['answer'],'.17g'))
def shuffle(rows,seed):
    result=copy.deepcopy(rows);mapping={};rng=random.Random(seed)
    for cid in FAMILIES:
        indices=[i for i,r in enumerate(rows) if r['source_id']==cid]
        perm=indices[:]
        for attempt in range(10000):
            rng.shuffle(perm)
            if all(rows[i]['target']!=rows[j]['target'] for i,j in zip(indices,perm)):break
        else:raise AssertionError('derangement failed')
        for i,j in zip(indices,perm):result[i]['target']=rows[j]['target'];mapping[rows[i]['id']]=rows[j]['id']
        assert collections.Counter(rows[i]['target'] for i in indices)==collections.Counter(result[i]['target'] for i in indices)
    assert all(a['messages']==b['messages'] and a['id']==b['id'] and a['target']!=b['target'] for a,b in zip(rows,result))
    return result,mapping
def main():
    RUN.mkdir(parents=True,exist_ok=False)
    write('clock.json',dict(start_utc='2026-09-28T17:30:45+00:00',experimental_cutoff_utc='2026-09-29T05:00:45+00:00',deadline_utc='2026-09-29T06:30:45+00:00'))
    oldpath=ROOT/'qwen/.runtime/program_self_training_20260926/selection/train-numeric.json'
    small=json.loads(oldpath.read_text());oldw=[json.loads(x) for x in (OLD/'numeric_cases_private.jsonl').read_text().splitlines()]
    byid={w['case_id']:w for w in oldw};trainw=[byid[r['id']] for r in small]
    dense=copy.deepcopy(small);hold=[];witness=copy.deepcopy(trainw);attempts={}
    for ci,cid in enumerate(FAMILIES):
        original=[byid[r['id']] for r in small if r['source_id']==cid];assert len(original)==8
        key='AB' if cid in ('H07','H15') else 'BC';baselines=[w['givens'][key] for w in original]
        seen={(w['private_witness']['shape_signature']['kind'],tuple(w['private_witness']['shape_signature']['normalized'])) for w in oldw if w['source_id']==cid}
        rng=random.Random(2026093003+ci);accepted=0;attempt=0
        while accepted<72:
            attempt+=1;assert attempt<250000
            try:
                res=N['BUILDERS'][cid](N['_sample_shape'](cid,rng))
                factor=baselines[accepted%8]/res['givens'][key]
                points={k:z*factor for k,z in res['points'].items()}
                N['_validate_construction'](cid,points)
                givens,answer=N['_values_from_points'](cid,points)
                kind,sig=N['_signature_from_points'](cid,points)
                if (kind,tuple(sig)) in seen:continue
                assert math.isclose(answer,res['answer']*factor**(2 if cid=='H07' else 1),rel_tol=1e-7,abs_tol=1e-9)
                assert math.isclose(givens[key],baselines[accepted%8],rel_tol=1e-12)
            except (N['Reject'],ZeroDivisionError,ValueError):continue
            seen.add((kind,tuple(sig)))
            split='dense' if accepted<56 else 'holdout'
            res.update(points=points,givens=givens,answer=answer,signature_kind=kind,shape_signature=sig)
            w=N['_serialize_private'](res,cid,split,accepted+1,2026093003+ci,attempt)
            w['private_witness']['provenance'].update(scale_factor=factor,baseline_source=original[accepted%8]['case_id'],label_basis='measure original geometric construction; no target theorem; no geosolver.solve')
            witness.append(w);(dense if accepted<56 else hold).append(row_from(w));accepted+=1
        attempts[cid]=attempt
    assert len(dense)==448 and len(hold)==112
    # Independently check every original and generated row, exceeding 8/family.
    validations=[check(w) for w in witness]
    for w in witness:N['_validate_construction'](w['source_id'],N['_points_from_witness'](w))
    write('construction-witnesses.researcher-only.json',witness)
    write('independent-validation.json',dict(status='pass',precision_digits=60,rows=validations,attempts=attempts))
    paths={}
    for name,data,seed in [('S',small,2026093101),('D',dense,2026093102)]:
        paths[name]=write('data/'+name+'.json',data)
        shuffled,mapping=shuffle(data,seed)
        control='X' if name=='S' else 'DX'
        paths[control]=write('data/'+control+'.json',shuffled)
        write('data/'+control+'-mapping.json',mapping)
    six=copy.deepcopy(dense)
    for r in six:
        previous=float(r['target']);r['target']=format(previous,'.6g')
        r['messages'][0]['content']=r['messages'][0]['content'].replace('at least 10 significant digits when appropriate','6 significant digits')
        assert abs(float(r['target'])-previous)<=max(1e-4,1e-5*abs(previous))
    paths['D6']=write('data/D6.json',six)
    dx6=copy.deepcopy(six);mapping=json.loads((RUN/'data/DX-mapping.json').read_text());six_by={r['id']:r['target'] for r in six}
    for r in dx6:r['target']=six_by[mapping[r['id']]]
    assert all(a['target']!=b['target'] for a,b in zip(six,dx6))
    paths['DX6']=write('data/DX6.json',dx6)
    write('data/holdout.json',hold)
    transfer=ROOT/'docs/research/transfer-reanalysis-2026-09-26'
    order=['H02','H03','H08','H12','DA03','DA06','DA07','DA11','DA15','DB01','DB08','DB16']
    oldjobs=json.loads((transfer/'eval-jobs-v2.json').read_text())
    mainjobs=sorted(oldjobs,key=lambda j:(j['replicate'],order.index(j['source_id'])))
    write('jobs/main12.json',mainjobs[:12]);write('jobs/main24.json',mainjobs)
    write('keys/main.json',json.loads((transfer/'answer-key.researcher-only.json').read_text()))
    retention=json.loads((transfer/'retention-jobs.json').read_text())
    for r in retention:r.pop('provenance',None)
    write('jobs/retention.json',retention)
    write('keys/retention.json',[dict(id=r['id'],source_id=r['source_id'],answer_exact=a) for r,a in zip(retention,['2*sqrt(7)','15/2','5','6'])])
    short=[];shortkey=[]
    for split,rows in [('trained',small),('holdout',hold)]:
        for r in rows:
            short.append(dict(id=r['id'],source_id=r['source_id'],split=split,seed=2026093201,messages=r['messages']))
            shortkey.append(dict(id=r['id'],source_id=r['source_id'],split=split,answer_exact=r['target']))
    write('jobs/short.json',short);write('keys/short.json',shortkey)
    confirmation=copy.deepcopy(mainjobs[:12])
    for i,r in enumerate(confirmation):r.update(id='confirm-'+r['source_id'].lower(),seed=2026093301+i,replicate=3)
    write('jobs/confirm-old.json',confirmation)
    mainkey={r['source_id']:r['answer_exact'] for r in json.loads((RUN/'keys/main.json').read_text())}
    write('keys/confirm-old.json',[dict(id=r['id'],source_id=r['source_id'],answer_exact=mainkey[r['source_id']]) for r in confirmation])
    template=json.loads((OLD/'config-numeric.json').read_text())
    for key in ['selection_receipt','selection_receipt_sha256','generation_length_amendment_sha256']:template.pop(key,None)
    for family,path in paths.items():
        for seed in [2026093001,2026093002]:
            for update,prior in [(32,None),(128,32),(512,128)]:
                name=f'{family}-{seed}-{update}'
                cfg=dict(template,dataset=str(path),dataset_sha256=sha(path),seed=seed,updates=update,save_checkpoints=[],protocol_sha256=sha(HERE/'PROTOCOL.md'))
                if prior:cfg['prior_checkpoint']=str(RUN/f'train/{family}-{seed}-{prior}/final')
                write('configs/'+name+'.json',cfg)
    write('preparation-receipt.json',dict(status='data_validated',original_dataset_sha256=sha(oldpath),generator_sha256=sha(OLD/'numeric_cases.py'),independent_validator_sha256=sha(HERE/'independent_geometry.py'),protocol_sha256=sha(HERE/'PROTOCOL.md'),datasets={k:dict(path=str(v),sha256=sha(v),rows=len(json.loads(v.read_text()))) for k,v in paths.items()},short_rows=168))
    print(json.dumps({'status':'pass','dense':448,'holdout':112,'independently_reconstructed':len(validations),'attempts':attempts}))
if __name__=='__main__':main()
