"""Summarize stage (1) only; restrict reads to S7 outputs."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    rows=[]
    for task in M['items']:
        p=OUT/'results'/task['case_id']/'result.json'
        assert p.exists(),p
        row=json.loads(p.read_text())
        assert row['stage_2_executed'] is False
        if row.get('failed_phase'):
            row['reason']=row['failed_phase']+': '+row['reason']
        if row['status']=='ok' and ('不定' in (row.get('base_judgment'),row.get('raw_judgment'))):
            row['reason']+='; 不定のmodeは閾値間[1e-60,1e-10]または幅間の区分不一致'
        if row.get('base_frozen_original_fallback'):
            row['reason']+='; 凍結版の元残差fallbackを保持'
        if row['status']=='ok' and (not row.get('base_relative_agreement') or not row.get('raw_relative_agreement')):
            row['reason']+='; ゼロ近傍を含む相対差1e-40検査は不一致（各幅の数値はJSON参照）'
        rows.append(row)
    fields=['case_id','status','n_variables','has_tangency','sigma_base','sigma_base_check','base_judgment','sigma_raw','sigma_raw_check','raw_judgment','base_width_agreement','raw_width_agreement','base_relative_agreement','raw_relative_agreement','base_rows','raw_rows','base_frozen_original_fallback','type','W3_target','reason','failed_phase','elapsed_seconds']
    import mpmath as mm
    with (OUT/'classification.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for original in rows:
            row=dict(original)
            for field in ['sigma_base','sigma_base_check','sigma_raw','sigma_raw_check']:
                if field in row:
                    with mm.mp.workdps(200):
                        v=mm.mp.mpf(row[field]);row[field]=mm.mp.nstr(v,18,min_fixed=0,max_fixed=0) if v else '0.0e+0'
                    if 'e' not in row[field]: row[field] += 'e+0'
                    assert 'e' in row[field]
            writer.writerow(row)
    counts=Counter(r['status'] for r in rows)
    types=Counter(r['type'] for r in rows if r['status']=='ok')
    targets=[r['case_id'] for r in rows if r.get('W3_target')]
    text=['# 事前登録14・段階(1) 特異値計測','',f"対象323問。状態別: {dict(counts)}。",'','段階(2)は実行していない。精密化成績との結合・W1/W2/W4の評価は行わない。','', '## 型別件数','', '| σ_base / σ_raw / 接する条件 | 件数 |','|---|---:|']
    text += [f'| {k} | {v} |' for k,v in sorted(types.items())]
    text += ['', '## W3対象（raw特異・base非特異・接する条件なし）','',f'{len(targets)}問。','']
    text += ['- '+k for k in targets] if targets else ['該当なし。']
    text += ['', '## 全問題の判定理由','', '| 問題 | 状態 | 型 | 理由 |','|---|---|---|---|']
    for r in rows:
        reason=r['reason'].replace('|','/').replace('\n',' ')
        text.append(f"| {r['case_id']} | {r['status']} | {r['type']} | {reason} |")
    (OUT/'classification.md').write_text('\n'.join(text)+'\n')
    bad=[]
    for path,expected in M['files'].items():
        # Manifest permits only these explicitly frozen input files.
        if sha(Path(path))!=expected: bad.append(path)
    for path,expected in M['source_files'].items():
        if sha(Path(path))!=expected: bad.append(path)
    assert not bad,bad
    paths=[p for p in OUT.rglob('*') if p.is_file() and p.name!='used-hashes.json']
    assert all(p.stat().st_size<3_000_000 for p in paths)
    audit=dict(stage_2_executed=False,all_323_accounted=True,parallel_limit=8,all_pre_run_hashes_unchanged=True,status_counts=dict(counts),type_counts=dict(types),W3_targets=targets,max_file_bytes=max(p.stat().st_size for p in paths),files={str(p.relative_to(OUT)):sha(p) for p in sorted(paths)})
    data=json.dumps(audit,ensure_ascii=False,indent=2)+'\n';assert len(data.encode())<3_000_000
    (OUT/'used-hashes.json').write_text(data)
    print(json.dumps({k:audit[k] for k in ['status_counts','type_counts','W3_targets','max_file_bytes']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
