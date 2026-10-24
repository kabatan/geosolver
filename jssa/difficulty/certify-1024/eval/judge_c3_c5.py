#!/usr/bin/env python3
"""Read-only C3-C5 join; no solving, no changes to preregistered thresholds.

Normal CLI reads the official stageB CSV. --snapshot-records captures existing
stageB raw records into eval only when its final CSV is not yet available.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import median
import sys

E = Path(__file__).resolve().parent
DEFAULT_STAGE = E.parent.parent/'exact-strong-1024/stageB/per-problem.csv'
SOLVED = {'verified_complete', 'direct_verified'}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def write(p, obj):
    Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')

def as_poly(text):
    import sympy as sp
    expression=sp.sympify(text.replace('^','**'))
    symbols=list(expression.free_symbols)
    if len(symbols)!=1:
        raise ValueError('NOT_UNIVARIATE')
    T=sp.Symbol('T')
    return sp.Poly(expression.subs(symbols[0],T),T,domain=sp.QQ)

def relation(polynomial, elimination):
    import sympy as sp
    if not polynomial or not elimination:
        return 'missing'
    p,q=as_poly(polynomial),as_poly(elimination)
    if p.degree()<1 or q.degree()<1:
        return 'missing'
    if p.monic()==q.monic():
        return 'equal'
    if not q.rem(p).is_zero:
        return 'other'
    pf={str(f.monic().as_expr()) for f,_ in sp.factor_list(p)[1]}
    qf={str(f.monic().as_expr()) for f,_ in sp.factor_list(q)[1]}
    return 'extra_irreducible_factors' if qf-pf else 'multiplicity_only'

def load_stage(path):
    if not path.exists():
        return {}, {'path':str(path),'exists':False}
    rows=list(csv.DictReader(path.open()))
    result={}
    for row in rows:
        cid=row.get('id') or row.get('problem_id')
        if not cid:
            raise ValueError('MISSING_ID_COLUMN')
        if cid in result:
            raise ValueError('DUPLICATE_STAGE_ID:'+cid)
        raw_path=Path(row['raw_result']) if row.get('raw_result') else None
        if raw_path and raw_path.exists():
            if row.get('raw_result_sha256') and sha(raw_path)!=row['raw_result_sha256']:
                raise ValueError('RAW_RESULT_HASH_MISMATCH:'+cid)
            raw=json.loads(raw_path.read_text())
            assert raw['id']==cid
            row['target_polynomial_factored']=raw.get('target_polynomial_factored') or ''
            row['raw_result_sha256_checked']=sha(raw_path)
        result[cid]=row
    return result, {'path':str(path),'exists':True,'sha256':sha(path),'rows':len(rows)}

def judge(rows, stage):
    joined=[]
    for r in rows:
        s=stage.get(r['id'],{})
        elimination=s.get('target_polynomial_factored') or s.get('elimination_polynomial') or ''
        try:
            rel=relation(r.get('polynomial',''),elimination)
        except (ValueError,TypeError,KeyError) as exc:
            rel='missing'
        status=s.get('status') or s.get('strong_status') or ''
        seconds=s.get('wall_seconds') or s.get('strong_wall_seconds')
        certified=r['category_ja']=='認証'
        joined.append({'id':r['id'],'certified':certified,'relation':rel,
                       'stage_present':bool(s),'strong_status':status,
                       'strong_solved':status in SOLVED if status else None,
                       'certify_wall_seconds':float(r['wall_seconds']) if r.get('wall_seconds') else None,
                       'strong_wall_seconds':float(seconds) if seconds not in (None,'') else None,
                       'elimination_polynomial':elimination,'polynomial':r.get('polynomial')})
    strata={}
    for rel,threshold,op in [('equal',.8,'>='),('extra_irreducible_factors',.3,'<=')]:
        group=[r for r in joined if r['relation']==rel]
        n=len(group); hits=sum(r['certified'] for r in group)
        rate=hits/n if n else None
        passed=None if not n else rate>=threshold if op=='>=' else rate<=threshold
        strata[rel]={'n':n,'certified':hits,'rate':rate,'threshold':threshold,'comparison':op,
                     'judgment':'未判定' if passed is None else '的中' if passed else '外れ'}
    cert=[r for r in joined if r['certified']]
    missing_status=[r['id'] for r in cert if r['strong_solved'] is None]
    c4_count=sum(r['strong_solved'] is False for r in cert)
    # Missing rows cannot establish a failure, but >=5 observed successes suffices.
    c4='的中' if c4_count>=5 else '未判定' if missing_status else '外れ'
    paired=[r for r in cert if r['strong_wall_seconds'] is not None and r['certify_wall_seconds'] is not None]
    a=median(r['certify_wall_seconds'] for r in paired) if paired else None
    b=median(r['strong_wall_seconds'] for r in paired) if paired else None
    c5='未判定' if not paired else '的中' if a<b else '外れ'
    judgments=[x['judgment'] for x in strata.values()]
    c3='外れ' if '外れ' in judgments else '未判定' if '未判定' in judgments else '的中'
    return {'scope':'開発外29問のみ。開発群・dev5を含まない。',
            'C3':{'judgment':c3,'strata':strata,'missing_or_unclassified':[r['id'] for r in joined if r['relation'] not in strata]},
            'C4':{'judgment':c4,'certified_not_solved':c4_count,'threshold':5,'missing_status':missing_status},
            'C5':{'judgment':c5,'paired_n':len(paired),'certify_median_seconds':a,'strong_median_seconds':b,
                  'paired_ids':[r['id'] for r in paired],
                  'missing_certified_ids':[r['id'] for r in cert if r not in paired]},
            'joined':joined}

def snapshot(directory, output):
    import sympy as sp
    ids=json.loads((E/'pre-run-hashes.json').read_text())['order']
    rows=[]; provenance=[]
    for cid in ids:
        path=directory/(cid+'.json')
        if not path.exists():
            continue
        r=json.loads(path.read_text())
        assert r['id']==cid
        expr=r.get('target_polynomial_factored')
        if not expr and r.get('elimination_polynomials'):
            polys=[as_poly(e) for e in r['elimination_polynomials'] if as_poly(e).degree()>0]
            if polys:
                q=polys[0]
                for p in polys[1:]: q=sp.gcd(q,p)
                expr=str(q.as_expr())
        rows.append({'id':cid,'status':r['status'],'wall_seconds':r.get('wall_seconds',''),
                     'target_polynomial_factored':expr or '', 'source':str(path),'source_sha256':sha(path)})
        provenance.append({'path':str(path),'sha256':sha(path)})
    with output.open('w') as f:
        w=csv.DictWriter(f,['id','status','wall_seconds','target_polynomial_factored','source','source_sha256'])
        w.writeheader();w.writerows(rows)
    write(output.with_suffix('.provenance.json'), {'source_directory':str(directory),'raw_record_hashes':provenance,
          'note':'stageBの既存開発外29問結果を読み取り専用で抽出。新たな求解・消去なし。元stageBファイルは変更しない。',
          'snapshot_sha256':sha(output)})

def self_test():
    assert relation('2*T-2','4*x-4')=='equal'
    assert relation('T-1','(x-1)*(x+1)')=='extra_irreducible_factors'
    assert relation('T-1','(x-1)**2')=='multiplicity_only'
    assert relation('T-1','x+1')=='other'
    rows=[{'id':str(i),'category_ja':'認証' if i<4 else '非所属','polynomial':'T-1','wall_seconds':'1'} for i in range(5)]
    stage={str(i):{'status':'verified_subset','wall_seconds':'2','target_polynomial_factored':'x-1'} for i in range(5)}
    r=judge(rows,stage)
    assert r['C3']['strata']['equal']['judgment']=='的中'  # exactly 80%
    assert r['C3']['judgment']=='未判定'                 # empty extra stratum
    assert r['C4']['judgment']=='外れ'                  # 4 < 5
    assert r['C5']['judgment']=='的中'
    rows[4]['category_ja']='認証'
    assert judge(rows,stage)['C4']['judgment']=='的中'
    assert judge(rows,{})['C4']['judgment']=='未判定'
    assert judge(rows,{})['C5']['judgment']=='未判定'
    extra=[{'id':str(i),'category_ja':'認証' if i<3 else '非所属','polynomial':'T-1','wall_seconds':'2'} for i in range(10)]
    es={str(i):{'status':'verified_complete','wall_seconds':'2','target_polynomial_factored':'(x-1)*(x+1)'} for i in range(10)}
    assert judge(extra,es)['C3']['strata']['extra_irreducible_factors']['judgment']=='的中' # 30%
    extra[3]['category_ja']='認証'
    assert judge(extra,es)['C3']['strata']['extra_irreducible_factors']['judgment']=='外れ'
    assert judge(extra,es)['C5']['judgment']=='外れ'       # strict less, not <=
    print('C3-C5 self-test passed')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--certify',type=Path,default=E/'per-problem.csv')
    p.add_argument('--stageb',type=Path,default=DEFAULT_STAGE)
    p.add_argument('--output',type=Path,default=E/'c3-c5.json')
    p.add_argument('--self-test',action='store_true')
    p.add_argument('--snapshot-records',type=Path)
    p.add_argument('--snapshot-output',type=Path,default=E/'stageB-unseen29-snapshot.csv')
    a=p.parse_args()
    if a.self_test:
        self_test()
    elif a.snapshot_records:
        snapshot(a.snapshot_records,a.snapshot_output)
    else:
        stage,source=load_stage(a.stageb)
        result=judge(list(csv.DictReader(a.certify.open())),stage)
        result['stageb_source']=source
        result['certify_csv_sha256']=sha(a.certify)
        result['judge_script_sha256']=sha(__file__)
        write(a.output,result)
        print(json.dumps({k:result[k] for k in ('C3','C4','C5')},ensure_ascii=False,indent=2))
