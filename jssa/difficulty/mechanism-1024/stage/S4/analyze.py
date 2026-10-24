"""Apply the preregistered inequalities and retain every missing problem."""
import csv
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
M=json.loads((OUT/'pre-run-hashes.json').read_text())
ROOT=Path(M['scratch'])
old={r['case_id']:r for r in csv.DictReader((OUT.parent/'S1/per-problem.csv').open())}
conditions=[]; problems=[]; raw_hashes={}
for task in M['items']:
    key=task['case_id']; folder=ROOT/key
    p=folder/'result.json'
    result=json.loads(p.read_text()) if p.exists() else dict(status='reference_unavailable',reason='外側時間切れまたはプロセス失敗',conditions=[])
    rows=result['conditions']
    if not rows:
        item=json.loads(Path(task['input']).read_text())
        rows=[dict(index=i,condition=str(c),t2_source=None) for i,c in enumerate(item['dsl']['conditions']) if 'IsTangent(' in str(c)]
    ok=result['status']=='ok'
    r_indices=[str(r['index']) for r in rows if r.get('g1_judgment')=='重根型' and r.get('g2_judgment')=='単根型'] if ok else []
    all_simple=bool(rows) and all(r.get('g1_judgment')=='単根型' for r in rows) if ok else False
    typ='R' if r_indices else ('S' if all_simple else 'U')
    reason='T1重根型→T2単根型：条件'+','.join(r_indices) if r_indices else ('全接条件のT1が単根型' if all_simple else
        ('参照解を作れず：'+result.get('reason','') if not ok else 'R/Sの要件を満たさず：'+
        '; '.join(f"条件{r['index']} T1={r.get('g1_judgment','不定')}, T2={r.get('g2_judgment','接点なし')}" for r in rows)))
    ref=result.get('reference',{})
    s1=old[key]
    problem=dict(case_id=key,type=typ,status='ok' if ok else '参照解を作れず',reason=reason,
        condition_count=len(rows),T1_double=sum(r.get('g1_judgment')=='重根型' for r in rows) if ok else '',
        T1_simple=sum(r.get('g1_judgment')=='単根型' for r in rows) if ok else '',
        T2_available=sum(bool(r.get('t2_source')) for r in rows),reference_absolute_digits=ref.get('absolute_digits',''),
        reference_absolute_error=ref.get('absolute_error',''),S1_large_improvement=s1['p1_met']=='True',
        S1_original_P2=s1['p1_group']=='False',S1_BASE_digits=s1['BASE_best_error_digits'],
        S1_no_rewrite_digits=s1['NO_RESIDUAL_REWRITE_best_error_digits'])
    problems.append(problem)
    for r in rows:
        conditions.append(dict(case_id=key,condition_index=r['index'],condition=r['condition'],
            g1=r.get('g1','') if ok else '',g2=r.get('g2','') if ok else '',
            g1_judgment=r.get('g1_judgment','') if ok else '',g2_judgment=r.get('g2_judgment','') if ok else '',
            status='ok' if ok else '参照解を作れず',t1_branch=r.get('branch',''),t2_source=r.get('t2_source') or '',
            g1_check=r.get('g1_check','') if ok else '',g2_check=r.get('g2_check','') if ok else '',
            scale_divisor=result.get('scale_divisor',''),reason='' if ok else result.get('reason','')))
    for p in sorted(folder.rglob('*')):
        if p.is_file(): raw_hashes[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
for name,rows in [('per-condition.csv',conditions),('per-problem.csv',problems)]:
    with (OUT/name).open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
large=[p for p in problems if p['S1_large_improvement']]
small=[p for p in problems if p['S1_original_P2']]
assert len(large)==len(small)==5
def met(p,group):
    return p['type']=='R' if group=='large' else p['type']=='S' or (p['type']=='R' and float(p['S1_no_rewrite_digits'])>=100)
counter=[p for group,ps in [('large',large),('small',small)] for p in ps if p['status']=='ok' and not met(p,group)]
missing=[p for p in large+small if p['status']!='ok']
k1='外れ' if counter else ('判定不能' if missing else '当たり')
text='| 問題 | 分類 | T1重根 / 単根 | 参照値との一致桁数 |\n|---|---|---:|---:|\n'
for p in problems:
    digits=f"{float(p['reference_absolute_digits']):.1f}" if p['reference_absolute_digits'] else '参照解を作れず'
    counts=f"{p['T1_double']} / {p['T1_simple']}" if p['status']=='ok' else '—'
    text+=f"| {p['case_id']} | 型{p['type']}{'（欠測）' if p['status']!='ok' else ''} | {counts} | {digits} |\n"
text+=f'\nK1：**{k1}**。S1に対する**事後の確認**であり、未見の予測ではない。'
text+=f"大改善5問のうち型Rは{sum(p['type']=='R' for p in large)}/5問。差20桁以内の元の5問で条件を満たすのは{sum(p['status']=='ok' and met(p,'small') for p in small)}/5問。\n"
text+='\nK2・K3：**未判定（S3後）**。S3の結果は読んでいない。\n'
text+='\nK1から外れた問題と機械的な根拠：\n\n'
for p in counter: text+=f"- {p['case_id']}：{p['reason']}。\n"
if missing:
    text+='\nK1に必要な欠測：'+', '.join(p['case_id'] for p in missing)+'。\n'
text+='\n参照解を作れなかった問題：\n\n'
for p in problems:
    if p['status']!='ok': text+=f"- {p['case_id']}：{p['reason']}。\n"
text+='\n微分計測は200桁演算の中央有限差分。固定した2つの幅で判定を照合した。参照図の作成だけに凍結版の620桁精密化を使い、T1/T2の精密化比較は実行していない。表の一致桁数は保存座標で評価した目標値の絶対誤差の−log10で、座標全成分の正しい桁数を保証する値ではない。\n'
text+='\nこの分類は指定された探索変数での1次微分の大小である。勾配ゼロだけでは真の二重根を証明できず、恒等的な条件も含む。別の等式に沿った方向への微分ではないため、接点が他の条件によって円周上・直線上に拘束される場合の重根構造を捉えないことがある。12問の結果から一般性能や因果を断定しない。\n'
text+=f'\n規則と入力・コードhashはrules.mdとpre-run-hashes.json、条件値と分類根拠は2つのCSVに保存。全座標・勾配成分・照合値・参照作成記録は `{ROOT}` に保存した。並列最大2、各1コア・内部1スレッド。凍結版srcの編集、昇格、導入、commit/pushは行っていない。\n'
(OUT/'answer.md').write_text(text)
(OUT/'raw-hashes.json').write_text(json.dumps(raw_hashes,indent=2)+'\n')
print(k1,[(p['case_id'],p['type'],p['status']) for p in problems])
