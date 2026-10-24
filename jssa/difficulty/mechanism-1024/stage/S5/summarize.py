"""Report only frozen-reference Jacobian classifications; never run refinement."""
from collections import Counter
import csv
from datetime import datetime,timezone
import json
from pathlib import Path
import re
from select_targets import save,sha

OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
T=json.loads((OUT/'targets.json').read_text())
for p,h in {**M['files'],**M['source_files']}.items(): assert sha(Path(p))==h,p
FIELDS=['case_id','type','status','reference_status','reference_absolute_digits',
        'T1_sigma','T1_sigma_check','T1_judgment','T1_spectra_agree',
        'T2_sigma','T2_sigma_check','T2_judgment','T2_spectra_agree',
        'prediction','reason','elapsed_seconds','existing_diagram','initial_points_saved',
        'initial_selected_count','initial_provenance_complete','measurement_type','normalization_status','fresh_solve_count','dsl_path','dsl_sha256']
rows=[]
for target in T['targets']:
    key=target['case_id'];folder=OUT/'results'/key
    result=json.loads((folder/'result.json').read_text())
    item=json.loads((OUT/'inputs'/(key+'.json')).read_text())
    refpath=folder/'reference.json'
    ref=json.loads(refpath.read_text()) if refpath.exists() else {}
    initial=item['selection']
    if initial is None and (folder/'initial.json').exists():
        points=json.loads((folder/'initial.json').read_text())['points']
        saved,total=len(points),len(points)
    elif initial is not None:
        saved,total=len(initial.get('initial_points',[])),initial.get('initial_selected_count')
    else: saved,total=0,None
    row={k:result.get(k,'') for k in FIELDS}
    row.update(existing_diagram=item['selection'] is not None,
        reference_status=ref.get('status','reference_unavailable'),
        initial_points_saved=saved,initial_selected_count=total,
        initial_provenance_complete=saved==total and saved>0,
        fresh_solve_count=int((folder/'solve-started.json').exists()),
        dsl_path=target['dsl_path'],dsl_sha256=target['sha256'])
    row['measurement_type']=row['type']
    row['normalization_status']='complete' if row['initial_provenance_complete'] else 'incomplete'
    if row['reference_status']=='ok' and not row['initial_provenance_complete']:
        row.update(type='不定',prediction='',status='normalization_provenance_incomplete',
            reason='保存初期座標が探索時の全候補に足りず、S4と同じ固定除数を完全再現できない。σとmeasurement_typeは保存分による補助測定で、登録の予測には使わない。')
    assert row['fresh_solve_count']<=1
    if initial is not None: assert row['fresh_solve_count']==0
    for method in ['T1','T2']:
        for suffix in ['_sigma','_sigma_check']:
            value=row[method+suffix]
            assert not value or re.fullmatch(r'[+-]?\d+(?:\.\d*)?e[+-]?\d+',value),value
    assert result['elapsed_seconds']<=600
    if result['type'] in ['P','N','B']:assert ref['status']=='ok'
    if ref.get('status')=='ok':
        from decimal import Decimal
        assert Decimal(ref['absolute_error'])<=Decimal('1e-300')
        assert Decimal(ref['relative_error'])<=Decimal('1e-300')
        assert ref['refinement_dps']==620 and ref['hard_feasible']
        assert Decimal(ref['original_residual_norm'])<=Decimal('1e-580')
    rows.append(row)
with (OUT/'classification.csv').open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=FIELDS);w.writeheader();w.writerows(rows)
counts=Counter(r['type'] for r in rows)
lines=['# S5：参照解と事前分類（段階(0)(1)完了）','',
    f'対象は{len(rows)}問。S1/S3の12問を除外し、同一問題を重複排除。凍結版 `60db4b6`、`{M["source_hash"]}`。',
    '','精密化比較(2)は未実行。以下は参照解でのσに基づく予測であり、U1–U3の成否はまだ評価していない。git commit/pushも実行していない。','',
    '| 型 | 件数 | 予測 |','|---|---:|---|']
for kind,text in [('P','U1：T2がT1より40桁以上良い'),('N','U2：T1とT2が20桁以内'),('B','U3：T2が300桁未満'),('不定','予測しない'),('参照解なし','予測しない')]:
    lines.append(f'| {kind} | {counts[kind]} | {text} |')
lines+=['','| 予測 | 対象型 | 対象問題数 | 将来の80%基準の判定可能性 |','|---|---|---:|---|']
for u,k in [('U1','P'),('U2','N'),('U3','B')]:
    lines.append(f'| {u} | {k} | {counts[k]} | '+('判定不能（2問未満）' if counts[k]<2 else '2問以上。成否判定は(2)後')+' |')
indeterminate=[k for k in ['P','N','B'] if counts[k]<2]
lines+=['','2問未満のため将来の集団予測が判定不能な型：'+('、'.join(indeterminate) if indeterminate else 'なし')+'。',
    f'参照解なし：{counts["参照解なし"]}問。参照解を確保したが測定・閾値分類が不定：{counts["不定"]}問。これらはU1–U3の対象数に含めない。','',
    '## 問題別分類','',
    'σ1=T1、σ2=T2。主幅1e-70、照合幅1e-60。σ<1e-60を特異、σ>1e-10を非特異とし、両幅で同じ閾値分類を要求する。全特異値の相対一致1e-40の成否はCSVと詳細JSONに別記。表は8有効桁、CSVと詳細JSONは200桁演算で得た値を保存する。',
    '', '| 問題 | 型 | σ1 | σ1（照合幅） | σ2 | σ2（照合幅） | 備考 |','|---|---|---|---|---|---|---|']
for r in rows:
    note=r['reason']
    if not r['initial_provenance_complete'] and r['initial_points_saved']:
        note+=(('; ' if note else '')+f'固定除数用の保存初期座標{r["initial_points_saved"]}/{r["initial_selected_count"]}候補（保存分全数を使用）')
    note=note.replace('|','\\|').replace('\n',' ')
    from decimal import Decimal
    display=dict(r)
    for k in ['T1_sigma','T1_sigma_check','T2_sigma','T2_sigma_check']:
        if display[k]: display[k]=format(Decimal(display[k]),'.7E').lower()
    lines.append('| '+' | '.join(str(display[k] or '—') for k in ['case_id','type','T1_sigma','T1_sigma_check','T2_sigma','T2_sigma_check'])+' | '+(note or '—')+' |')
lines+=['','## 実行・検証','',
    f'- 既存検証済み図：{sum(r["existing_diagram"] for r in rows)}問。通常solve(seed 0)を新規に一度だけ実行：{sum(r["fresh_solve_count"] for r in rows)}問。別seed・再試行なし。',
    '- 参照解は620桁で作り、元の全残差ノルム1e-580以下・hard feasible・独立参照値との絶対および相対誤差1e-300以下を確認。参照作成のclosureは一度のみ。',
    '- 固定除数は保存初期座標だけから決め、T1/T2で共用。既存artifactに探索時の全候補が残らない2問は、保存分での補助測定値だけを残し、最終分類は不定・予測なしとした（元の閾値分類はCSVのmeasurement_type）。対象問題の追加・除外はしていない。参照座標からの尺度作成は行っていない。',
    '- 未知数0の2問はS4と同じclosureが空ベクトルに対してNoneを返すため、参照解なしと記録する。別方式で参照解を補わない。',
    '- HMMT-2020-FEB-GEO-04はDSLと正規化IRの空白差で行対応が失敗したため、保存済み参照解・固定除数を用いてAST一致で対応を修正しσだけ計測した。接点式のないDistance形式で指定T2がT1に戻る一方、凍結版平滑化は元のDistance-rを保持する差は、診断値として保存した（登録の残差定義は変更なし）。solve・参照closureの再実行なし。',
    '- 指数0でmpmathが指数を省略する場合はe+0を追記した。σの値は変更していない。sigma-formatting-audit.jsonに記録。',
    '- 最初の起動はmkdirの競合で全プロセスがstarted記録前に停止した。solve・closure・σ計測は0回。startup-audit.jsonとstartup-failure-hashes.jsonに保存し、修正後のハッシュを再固定して実行した。',
    f'- 最大並列{M["parallel"]}、各1コア・内部1スレッド。全工程1問600秒以内。実測最大{max(r["elapsed_seconds"] for r in rows):.3f}秒。',
    '- targets.json、classification.csv、参照座標・両幅の全Jacobianと特異値・使用コードと入力のハッシュをS5内に保存。各ファイル3,000,000 bytes未満。','']
(OUT/'classification.md').write_text('\n'.join(lines))
# Verify the unchanged selector reproduces exactly the frozen targets and input inventory.
import subprocess
before={n:sha(OUT/n) for n in ['targets.json','selection-audit.json']}
subprocess.run([M['python'],'-B',str(OUT/'select_targets.py')],check=True,stdout=subprocess.DEVNULL)
assert before=={n:sha(OUT/n) for n in before}
allfiles=[p for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='used-hashes.json']
assert all(p.stat().st_size<3_000_000 for p in allfiles)
save(OUT/'used-hashes.json',dict(completed_utc=datetime.now(timezone.utc).isoformat(),
    frozen_commit=M['frozen_commit'],source_hash=M['source_hash'],pre_run_manifest_sha256=sha(OUT/'pre-run-hashes.json'),
    pre_run_files_unchanged=True,selection_reproduced=True,stage_2_executed=False,git_commit_push_executed=False,
    problem_count=len(rows),counts=dict(counts),file_count=len(allfiles),max_file_bytes=max(p.stat().st_size for p in allfiles),
    files={str(p.relative_to(OUT)):dict(sha256=sha(p),bytes=p.stat().st_size) for p in allfiles}))
print(json.dumps(dict(targets=len(rows),counts=dict(counts),fresh_solves=sum(r['fresh_solve_count'] for r in rows),
    max_seconds=max(r['elapsed_seconds'] for r in rows),stage_2_executed=False),ensure_ascii=False))
