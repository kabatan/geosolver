"""Aggregate preregistered trials, without changing any trial or threshold."""
from pathlib import Path
import json,csv,statistics,hashlib,copy
HERE=Path(__file__).resolve().parent
import sys
sys.path.insert(0,str(HERE));sys.path.insert(0,str(HERE/'vendor'))
from verify_certificate import verify
def save(path,obj):path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def main():
    lock=json.loads((HERE/'registration-lock.json').read_text())
    assert hashlib.sha256((HERE/'preregistration.md').read_bytes()).hexdigest()==lock['preregistration_sha256']
    trials=[];pairs=[];checks=[]
    for cid in lock['ids']:
        rr={}
        for arm in ['A','B']:
            d=HERE/'runs'/f'{cid}__{arm}';r=json.loads((d/'result.json').read_text());p=json.loads((d/'process.json').read_text())
            assert r['status']!='running'
            assert not r['official_answer_loaded'] and not r['existing_P_loaded']
            success=r['status']=='certified'
            row=dict(id=cid,arm=arm,status=r['status'],seconds=r['seconds'],cold_seconds=p['cold_seconds'],success=success,
                PAR2_seconds=r['seconds'] if success else 240,variables=r.get('variables'),equations=r.get('equations'),
                P=r.get('P',''),Q=r.get('Q',''),certificate_kind=r.get('certificate_kind',''),
                candidate_Ps='; '.join(dict.fromkeys(a['P'] for a in r['attempts'] if 'P' in a)),
                root_count=r.get('root_check',{}).get('allowed_root_count',''),attempts=len(r['attempts']),
                input_sha256=r['input_sha256'],error=r.get('error',''))
            trials.append(row);rr[arm]=row
            for f in d.glob('certificate*.json'):
                cert=json.loads(f.read_text());assert verify(cert)
                damaged=copy.deepcopy(cert);n=len(cert['variables'])
                constant=[0]*n
                found=False
                for term in damaged['Q']:
                    if term[0]==constant:
                        from fractions import Fraction
                        term[1]=str(Fraction(term[1])+1);found=True;break
                if not found:damaged['Q'].append([constant,'1'])
                assert not verify(damaged)
                checks.append(dict(path=str(f.relative_to(HERE)),verified=True,wrong_Q_rejected=True,sha256=hashlib.sha256(f.read_bytes()).hexdigest(),bytes=f.stat().st_size))
        a,b=rr['A'],rr['B'];assert a['input_sha256']==b['input_sha256']
        sa=(HERE/'runs'/f'{cid}__A/system.json');sb=(HERE/'runs'/f'{cid}__B/system.json')
        assert json.loads(sa.read_text())==json.loads(sb.read_text()),cid
        pairs.append(dict(id=cid,trivial=cid=='AIME-2015-II-07',A_status=a['status'],B_status=b['status'],A_seconds=a['seconds'],B_seconds=b['seconds'],
                          B_over_A=b['seconds']/a['seconds'] if a['success'] and b['success'] else None,
                          B_only=b['success'] and not a['success'],A_only=a['success'] and not b['success'],
                          B_3x_win=b['success'] and (not a['success'] or b['seconds']<=a['seconds']/3),
                          strong_win=b['success'] and ((a['success'] and b['seconds']<=a['seconds']/3) or (not a['success'] and b['seconds']<=40))))
    for name,rows in [('per-run.csv',trials),('comparison.csv',pairs)]:
        with (HERE/name).open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    summary={}
    for population,ids in [('all16',lock['ids']),('nontrivial15',[x for x in lock['ids'] if x!='AIME-2015-II-07'])]:
        sub=[r for r in trials if r['id'] in ids];ps=[p for p in pairs if p['id'] in ids]
        s={arm:dict(success=sum(r['success'] for r in sub if r['arm']==arm),total=len(ids),
                    mean_PAR2=statistics.mean(r['PAR2_seconds'] for r in sub if r['arm']==arm),
                    mean_actual_seconds=statistics.mean(r['seconds'] for r in sub if r['arm']==arm)) for arm in ['A','B']}
        s.update(B_only=sum(p['B_only'] for p in ps),A_only=sum(p['A_only'] for p in ps),B_3x_wins=sum(p['B_3x_win'] for p in ps),strong_wins=sum(p['strong_win'] for p in ps),
                 median_B_over_A_common_success=statistics.median(p['B_over_A'] for p in ps if p['B_over_A'] is not None))
        summary[population]=s
    main=summary['nontrivial15'];summary['Q1_supported']=main['B_3x_wins']<=3
    summary['central_claim_threshold_met']=main['B']['success']>=10 and main['strong_wins']>=8
    summary['identities_verified']=len(checks)
    summary['total_artifact_bytes']=sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file())
    summary['largest_file_bytes']=max(p.stat().st_size for p in HERE.rglob('*') if p.is_file())
    save(HERE/'summary.json',summary);save(HERE/'certificate-validation.json',checks)
    md=['| ID | A:直接消去 | 秒 | B:数値候補→証明 | 秒 | B/A（双方成功） |','|---|---|---:|---|---:|---:|']
    for p in pairs:
        ratio=f"{p['B_over_A']:.2f}" if p['B_over_A'] is not None else '—'
        md.append(f"| {p['id']} | {p['A_status']} | {p['A_seconds']:.3f} | {p['B_status']} | {p['B_seconds']:.3f} | {ratio} |")
    (HERE/'comparison.md').write_text('\n'.join(md)+'\n')
    print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
