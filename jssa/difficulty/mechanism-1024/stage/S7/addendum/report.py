"""Deterministic stage-(1)-only summary, CSV and detailed W3 analysis."""
from common import *
from collections import Counter
from mpmath import mp

LABELS = {'distance_zero_coordinates':'距離0の座標差','distance_radius_contact':'距離=半径の接点',
          'contact_line_circle':'接点(line-circle)','contact_circle_circle':'接点(circle-circle)',
          'signed_tangency_line_circle':'signed tangency(line-circle)',
          'signed_tangency_circle_circle':'signed tangency(circle-circle)','radius_auxiliary':'半径の補助式'}
def labels(types):
    return ' / '.join(LABELS.get(x,x) for x in types) or 'なし'
def fmt(x):
    with mp.workdps(200):
        value=mp.mpf(x)
        s=mp.nstr(value,8,min_fixed=0,max_fixed=0) if value else '0.0e+0'
        return s if 'e' in s else s+'e+0'
def group(n):
    return '0種類' if n==0 else ('1種類' if n==1 else '複数種類')
def table(headers,rows):
    return ['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,r))+' |' for r in rows]

def main():
    manifest=check_manifest()
    source={r['case_id']:r for r in selected()}
    records=[load(OUT/'results'/f'{k}.json') for k in manifest['case_ids']]
    assert all(r['status']=='ok' for r in records)
    output=[]
    for r in records:
        k=r['case_id']; old=source[k]; inv=r['inventory']
        row=dict(case_id=k,stage1_base=old['base_judgment'],stage1_raw=old['raw_judgment'],one_sided_class=r['classification'],
                 width_70_class=r['samples'][0]['classification'],width_60_class=r['samples'][1]['classification'],
                 base_rows=r['m_base'],raw_rows=r['m_raw'],n_variables=r['n'],base_shape=f'{r["m_base"]}x{r["n"]}',raw_shape=f'{r["m_raw"]}x{r["n"]}',
                 base_rewrite_types=';'.join(inv['base_types']),base_rewrite_names=labels(inv['base_types']),base_type_count=r['base_type_count'],
                 base_type_group=group(r['base_type_count']),raw_T1_types=';'.join(inv['raw_types']),combined_type_count=r['combined_type_count'],
                 base_fallback=inv['base_fallback'],W3=k in manifest['protocol']['w3'])
        for sample in r['samples']:
            exp=sample['step_exponent']
            for side in ('plus','minus','central'):
                row[f'sigma_raw_{side}_{exp}']=sample[side]['sigma']
            row[f'sigma_raw_stage1_{exp}']=old['sigma_raw' if exp==70 else 'sigma_raw_check']
            row[f'sigma_base_stage1_{exp}']=old['sigma_base' if exp==70 else 'sigma_base_check']
            row[f'matrix_gap_{exp}']=sample['normalized_matrix_gap']
            row[f'nonsmooth_rows_{exp}']=';'.join(str(x['raw_row']) for x in sample['nonsmooth_rows'])
        row['rewrite_details_json']=json.dumps(inv['changes'],ensure_ascii=False,separators=(',',':'))
        row['raw_T1_details_json']=json.dumps([x for x in inv['raw'] if x['type']!='original'],ensure_ascii=False,separators=(',',':'))
        output.append(row)
    with (OUT/'per-problem.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(output[0]));writer.writeheader();writer.writerows(output)
    counts=Counter(r['classification'] for r in records)
    lines=['# 事前登録14 補遺：片側差分・書き換え・W3','',
           f'対象はraw特異 {sum(s["raw_judgment"]=="特異" for s in source.values())}問、base特異 {sum(s["base_judgment"]=="特異" for s in source.values())}問の和集合 {len(records)}問。base特異はすべてraw特異に含まれる。',
           '同じ保存参照解・固定除数・200桁・h=10^-70/10^-60で比較。新規solve・精密化なし。閾値と判定順は結果計算前にREADME.md/protocol.jsonへ固定した。','',
           'σ>1e-10 の片側行列がある、または正規化Frobenius片側差>1e-20なら微分不能。そうでなく両片側σ<1e-60なら特異。二幅の不一致・中間は不定。詳細はREADME.md。','']
    lines+=table(['片側差分後の分類','件数'],[(k,counts[k]) for k in ('微分不能','特異','不定')])
    lines+=['','微分不能と診断された問題は、中央差分のσが小さくても「特異」には加算しない。この診断は指定の座標方向と二幅での操作的分類である。','',
            '## 書き換え種類数別（base適用種類が主集計）','']
    for scope,title in [(records,'raw特異全問'),([r for r in records if source[r['case_id']]['base_judgment']=='特異'],'base特異全問')]:
        lines += [title,'']
        lines+=table(['base書き換え種類数','対象数','微分不能','特異','不定'],[
            (g,len(sub:= [r for r in scope if group(r['base_type_count'])==g]),
             *[sum(r['classification']==c for r in sub) for c in ('微分不能','特異','不定')])
            for g in ('0種類','1種類','複数種類')])
        lines+=['']
    type_counts=Counter(labels(r['inventory']['base_types']) for r in records)
    lines+=table(['base適用種類の組合せ','件数'],sorted(type_counts.items()))
    combined=Counter(group(r['combined_type_count']) for r in records)
    lines+=['','rawのT1を別の種類として含めた参考集計：'+ '、'.join(f'{g} {combined[g]}問' for g in ('0種類','1種類','複数種類'))+'。base種類とraw T1はCSVで分離した。',
            '複数種類の同時適用がある問題から、接点以外の効果は主張しない。','',
            '## 問題別の形状と片側差分','',
            'σ欄は k=70 の値。k=60と200桁の全値・書き換え条件はper-problem.csv、行列と全特異値はresults/*.json。行番号は0始まり。','']
    lines+=table(['問題','base m×n','raw m×n','base書き換え','σ(+)','σ(−)','σ(中央)','片側後'],[
        (r['case_id'],f'{r["m_base"]}×{r["n"]}',f'{r["m_raw"]}×{r["n"]}',labels(r['inventory']['base_types']),
         fmt(r['samples'][0]['plus']['sigma']),fmt(r['samples'][0]['minus']['sigma']),fmt(r['samples'][0]['central']['sigma']),r['classification']) for r in records])
    lines+=['','## 読み方と証跡','',
            '開発群であり開発外の検証ではない。σは参照解を使うので解く前の予測には使えない。微分不能を除外すると、段階(1)のW3の解釈は別途必要になる。書き換えの局所的な階数回復は、精密化の到達桁数の改善を示すものではない。',
            'D_base/D_rawおよび他段階の精密化記録・桁数表は読んでいない。git commit/pushなし。最大4並列。',
            f'事前manifest SHA-256: `{sha(OUT/"pre-run-hashes.json")}`。README/protocol/スクリプト/入力/凍結ソースのhashはpre-run-hashes.json、完成成果物hashはhashes.sha256。',
            'W3の条件・行単位の検査は[w3-analysis.md](w3-analysis.md)。検証結果はverification.json。','']
    (OUT/'addendum.md').write_text('\n'.join(lines))
    w=['# W3指定5問：効いた書き換えと微分可能性','',
       '各条件のbase行群をその条件のraw中央行へ1組ずつ戻し、他のbase行を維持したままσを再計算した。行番号は0始まり。幅は両方ともh_j=10^-k max(1,|x_j|)、200桁、固定除数は段階(1)と同一。',
       'base→rawの行数の減少と微分不能を区別する。片側差分行列が特異でもm<nなら列数に対して0を補っているため、片側行列の差が大きいかを併せて確認する。','']
    for r in records:
        if r['case_id'] not in manifest['protocol']['w3']:continue
        inv=r['inventory']
        w += [f'## {r["case_id"]}','',f'base {r["m_base"]}×{r["n"]}、raw {r["m_raw"]}×{r["n"]}。変数：`{", ".join(r["var_names"])}`。',
              f'適用種類：{labels(inv["base_types"])}（{r["base_type_count"]}種類）。接する条件/T1：{labels(inv["raw_types"])}。',
              f'二幅を合わせたraw診断：**{r["classification"]}**。','']
        w+=table(['k','σ_base中央','σ_raw(+)','σ_raw(−)','σ_raw中央','行列片側差g','分類'],[
            (s['step_exponent'],fmt(s['base']['sigma']),fmt(s['plus']['sigma']),fmt(s['minus']['sigma']),fmt(s['central']['sigma']),fmt(s['normalized_matrix_gap']),s['classification']) for s in r['samples']])
        w+=['','条件と行の対応：','']
        for change in inv['changes']:
            ri=change['bundle_index']
            w += [f'- 元条件 / raw行 {ri}: `{change["condition"]}`。base行 {change["base_rows"]}：'+ '; '.join(f'`{x} = 0`' for x in change['expressions'])+'。']
        w+=['','1条件ずつ戻す検査：','']
        ab=[]
        for s in r['samples']:
            for rev in s['single_condition_reversions']:
                ch=rev['change']
                ab.append((s['step_exponent'],ch['bundle_index'],str(ch['base_rows']),f'{rev["rows"]}×{r["n"]}',fmt(rev['sigma']),rev['classification']))
        w+=table(['k','戻すraw条件行','除くbase行','形状','σ（一条件を戻す）','分類'],ab)
        w+=['','片側差が大きいraw行（k=70）：','']
        for row in r['samples'][0]['nonsmooth_rows']:
            w += [f'- 行 {row["raw_row"]} `{row["condition"]}`：g_row={fmt(row["normalized_gap"])}、差が検出された変数 `{", ".join(row["affected_variables"])}`。']
        influential=[rev['change']['bundle_index'] for rev in r['samples'][0]['single_condition_reversions'] if rev['classification']=='特異']
        w+=['',f'baseの非特異性を失わせる単条件の復帰（k=70）：{influential if influential else "なし"}。k=60の結果は上表に併記。',
            '距離0のraw残差は解でノルムの尖点になる。中央差分の相殺と、座標差の2行をノルム1行にまとめることの両方が関与するため、σ_raw中央だけを滑らかな系の特異性とは解釈しない。' if r['classification']=='微分不能' else '片側差分の判定は上表のとおり。','']
    w+=['## 結論の範囲','',
        '指定5問は同じ参照図での書き換えと局所行列の比較であり、到達桁数についての証拠ではない。開発群内の診断で、開発外検証でも解く前の予測でもない。複数種類の同時適用例から接点以外の効果を主張しない。','']
    (OUT/'w3-analysis.md').write_text('\n'.join(w))
    save(OUT/'summary.json',dict(cases=len(records),classifications=dict(counts),base_type_combinations=dict(type_counts),
         w3={r['case_id']:r['classification'] for r in records if r['case_id'] in manifest['protocol']['w3']},stage_2_executed=False))
    print(json.dumps(load(OUT/'summary.json'),ensure_ascii=False))

if __name__=='__main__':main()
