"""Aggregate frozen measurements and explicitly labelled interpretation.

The interpretation does not alter the numerical acceptance criteria or files.
"""
import collections
import csv
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]

MOTION={
 'aime-2000-2-6':'台形の高さと上底の横ずれ（2自由度）',
 'aime-2001-1-9':'固定三角形の辺上点 D,E,F が動く',
 'aime-2003-1-12':'等角四角形の辺長配分が動く',
 'AIME-2011-II-04':'AB=20,AC=11 の間の角が動く',
 'AIME-2015-II-07':'内接長方形が動く。ただし目標は固定三角形だけの式',
 'AIME-2016-I-06':'LI=2,LD=3 を保って三角形が変形',
 'AIME-2021-I-13':'外接する第三の円の中心・半径が動く',
 'HMMT-2006-FEB-GEO-03':'割線の角度と円が動くが PQ 上の弦長は一定',
 'HMMT-2008-FEB-GEO-06':'A が固定弦 BC を見込む円弧上を動く',
 'HMMT-2013-FEB-GEO-02':'等脚台形の高さが動く',
 'HMMT-2013-FEB-GEO-03':'面積条件を保つ六角形の変形（2自由度）',
 'HMMT-2013-FEB-GEO-08':'角 g が動く',
 'HMMT-2022-FEB-GEO-01':'U,V と投影先の直線が平行移動',
 'HMMT-2023-FEB-GEO-01':'六角形内の P が水平に動く',
 'JMO-2013-PRE-05':'二本の半直線の間の角 theta が動く',
 'JMO-2014-PRE-09':'OP,OQ,OR を保って外側の正方形の辺長が動く',
}
GAUGE={
 'AIME-2009-I-05':'C を中心とする回転',
 'AIME-2010-II-09':'正六角形全体の一様拡大',
 'AIME-2012-I-12':'全点の一様拡大（数値ランクは閾値感度あり）',
 'AIME-2013-I-03':'正方形と辺上点の一様拡大',
 'AIME-2020-I-01':'全点の一様拡大（数値ランクは刻み感度あり）',
 'AIME-2022-II-11':'A を中心とする回転',
 'HMMT-2011-FEB-ALGGEO-18':'全点の一様拡大。L1,L2 は同じ直線のまま',
 'HMMT-2013-FEB-GEO-04':'二円と交点の一様拡大',
 'HMMT-2013-FEB-GEO-05':'全点の一様拡大',
 'HMMT-2019-FEB-GEO-05':'O を中心とする回転',
 'HMMT-2021-FEB-GEO-06':'B を中心とする回転',
 'HMMT-2023-FEB-GEO-04':'正方形と P,Q の一様拡大',
 'HMMT-2025-FEB-GEO-02':'4点の水平並進。中点一致は実数では座標2本',
}
SPECIAL={
 'AIME-2008-I-10':('R0','逆三角不等式と二乗和の等号から唯一の実配置。analytic-notes.md'),
 'AIME-2018-II-14':('R0','接点 Y の接線条件から u=21/5 のみ。analytic-notes.md'),
 'AIME-2015-II-11':('AUX','V は直線 OV の表現点。V を除く形の変化は 4.64e-15'),
}
DETAIL={
 'AIME-2009-I-12':'旧分解でも I が AB に落ちる退化成分を確認',
 'AIME-2013-II-04':'Distance(P,Centroid)=0 を実数上の座標差2本として診断',
 'HMMT-2006-FEB-GEO-01':'Distance(A,Aclose)=0 の実数上の閉鎖条件',
 'HMMT-2008-FEB-GEO-09':'旧非退化飽和でも0次元',
 'HMMT-2009-FEB-GEO-01':'Distance(U,V)=0 の実数上の座標一致',
 'JMO-2013-PRE-08':'旧 r!=0 の飽和でも0次元',
 'JMO-2014-PRE-01':'接触の重根を平滑な接条件で診断',
}


def main():
    comparison=list(csv.DictReader((HERE/'sources/comparison-cases.csv').open()))
    selected=[r for r in comparison if r['msolve_class'] in ('positive_dimensional','free_parameter')]
    assert len(selected)==68
    prior={r['id']:r for r in csv.DictReader((HERE/'sources/prior-batch-summary.csv').open())}
    certs={r['id']:r for r in json.loads((HERE/'certificates/summary.json').read_text())}
    rows=[]
    for c in selected:
        cid=c['id']; d=json.loads((HERE/'diagnostic'/f'{cid}.json').read_text())
        initial=json.loads((HERE/'numerical'/f'{cid}.json').read_text())
        if cid in MOTION:
            code='G'; reason=MOTION[cid]; dimension=d['nullity']; broad='genuine_shape_motion'
            assert d['status']=='shape_motion_constant_target'
        elif cid in GAUGE:
            code='GAUGE'; reason=GAUGE[cid]; dimension=0; broad='apparent_positive_dimension'
        elif cid in SPECIAL:
            code,reason=SPECIAL[cid]; dimension=0; broad='apparent_positive_dimension'
        else:
            assert d['status']=='locally_isolated',cid
            code='L0'; reason='許容点で局所ランク満杯（3刻み・3閾値）。'+DETAIL.get(cid,'余剰複素成分の大域的な所在は未同定')
            dimension=0; broad='apparent_positive_dimension'
        accepted=[q for q in d['samples'] if q['accepted']]
        rows.append(dict(id=cid,comparison_class=c['msolve_class'],classification=broad,evidence_code=code,
            physical_dimension=dimension,n_vars=d['n_vars'],numeric_nullity=d.get('nullity'),
            initial_status=initial['status'],diagnostic_status=d['status'],
            rank_stable=d.get('rank_stable'),rank_threshold_stable=d.get('rank_threshold_stable'),
            accepted_samples=len(accepted),attempted_samples=len(d['samples']),
            max_shape_change=d.get('max_shape_change'),max_target_relative_change=d.get('max_target_relative_change'),
            max_accepted_original_residual=max([q['state']['residual'] for q in accepted],default=None),
            base_source=next((r['source'] for r in d['rank_at_saved_points'] if 'x' in r),'none'),
            reason=reason,prior_certificate=prior.get(cid,{}).get('status','outside_old_63'),
            new_derived_chart_certificate=cid in certs,
            comparison_elimination=c['elim_status'],comparison_geo_matched=c['geo_matched']))
    rows.sort(key=lambda r:r['id'])
    with (HERE/'classification.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    counts=collections.Counter(r['evidence_code'] for r in rows)
    assert counts=={'G':16,'GAUGE':13,'AUX':1,'L0':36,'R0':2},counts
    initial_counts=collections.Counter(r['initial_status'] for r in rows)
    diag_counts=collections.Counter(r['diagnostic_status'] for r in rows)
    newids=[r['id'] for r in rows if certs.get(r['id'],{}).get('new_among_old_63')]
    genuine=[r for r in rows if r['evidence_code']=='G']
    stats=dict(n=68,evidence_counts=counts,initial_status_counts=initial_counts,diagnostic_status_counts=diag_counts,
        genuine_dimensions=collections.Counter(str(r['physical_dimension']) for r in genuine),
        new_certificate_ids=newids,prior_status_counts=collections.Counter(r['status'] for r in prior.values()),
        comparison_elimination_counts=collections.Counter(c['elim_status'] for c in selected),
        comparison_geo_at_least_one=sum(int(c['geo_matched'])>0 for c in selected),
        comparison_geo_all_three=sum(int(c['geo_matched'])==3 for c in selected),
        genuine_max_target_change=max(r['max_target_relative_change'] for r in genuine),
        genuine_max_original_residual=max(r['max_accepted_original_residual'] for r in genuine),
        genuine_samples=sum(r['accepted_samples'] for r in genuine),
        analytic_seed_ids=[r['id'] for r in rows if r['base_source']=='analytic-witnesses.json'],
        caveat='L0 and G are local numerical evidence, not a certified global real decomposition; analytic seeds are not solver hits.')
    (HERE/'summary.json').write_text(json.dumps(stats,indent=2,ensure_ascii=False)+'\n')
    intro='''# 68問の全行分類

相似変換（並進・回転・一様拡大）と補助表現の冗長性を除く。
G=実際の形の変形を局所数値確認、GAUGE=相似変換、AUX=補助点だけ、
L0=許容点の局所ランクが満杯、R0=実数の議論で孤立を確認。
G と L0 は全実成分の厳密分解ではない。「物理次元」はこの区別の下の局所判定。
GAUGE のうち AIME-2012-I-12 と AIME-2020-I-01 はランク感度があるが、
明示的な尺度対称性と全補正点の形の不変性を別の根拠にした。
aime-2000-2-6 の第二方向は形変化6.91e-6で検出閾値未満。
その2次元という解釈は、analytic-notes.md の高さ・横ずれを自由に選ぶ議論も使う。
初回の判定は numerical/、事後診断は diagnostic/ にそのまま保存。
分類CSVは両方の判定、試行数、元残差、入力出所、旧証明書の成否も含む。

| ID | 分類 | 物理次元 | 根拠・動く量 |
|---|---|---:|---|
'''
    table=''.join(f"| {r['id']} | {r['evidence_code']} | {r['physical_dimension']} | {r['reason']} |\n" for r in rows)
    (HERE/'classification.md').write_text(intro+table)
    table='| ID | 次元 | 合格点数 | 最大形変化 | 最大目標相対変化 | 動く量 |\n|---|---:|---:|---:|---:|---|\n'
    for r in genuine:
        table+=f"| {r['id']} | {r['physical_dimension']} | {r['accepted_samples']}/{r['attempted_samples']} | {r['max_shape_change']:.3g} | {r['max_target_relative_change']:.3g} | {r['reason']} |\n"
    (HERE/'genuine-table.md').write_text(table)
    # Record content hashes for compact inputs. Large historical run files stay in the repo.
    sources=[]
    for p in sorted((HERE/'sources').iterdir()):
        if p.is_file(): sources.append(dict(path=str(p.relative_to(HERE)),bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    for relative in ['benchmarks/cases.jsonl','jssa/difficulty/probe_basins.py']:
        p=ROOT/relative
        sources.append(dict(path=relative,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
    (HERE/'input-hashes.json').write_text(json.dumps(sources,indent=2)+'\n')
    print(json.dumps(stats,indent=2,ensure_ascii=False))


if __name__=='__main__': main()
